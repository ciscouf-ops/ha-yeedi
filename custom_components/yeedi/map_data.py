"""Live map data of a robot, for the yeedi map card.

Yeedi robots do not send a ready-made map image the way recent Deebots do, but they do
report everything a card needs to draw one:

- the outline of every room (``getMapSubSet``, already requested by deebot-client),
- the position of the robot and of the dock (``onPos`` / ``getPos``),
- the cleaning state, used here to start a new trace when a cleaning begins.

The trace is built from the robot positions received while it cleans, so it is lost
when Home Assistant restarts during a cleaning.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import re
import time
from typing import Any

from deebot_client.device import Device
from deebot_client.events import (
    CachedMapInfoEvent,
    MapSetType,
    MapSubsetEvent,
    PositionsEvent,
    RoomsEvent,
    StateEvent,
)
from deebot_client.models import State

from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

_NUMBER_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
_MIN_STEP_MM = 40  # ignore positions closer than this to the last trace point
_MAX_TRACE_POINTS = 4000
_POLL_INTERVAL = 3.0  # seconds, while the robot moves
_NOTIFY_DELAY = 0.5  # seconds, to group bursts of events
_MOVING = (State.CLEANING, State.RETURNING)


def _parse_outline(coordinates: str | None) -> list[list[float]]:
    """Return the points of an outline given as 'x,y;x,y;...'."""
    if not coordinates:
        return []
    return [[float(x), float(y)] for x, y in _NUMBER_PAIR.findall(coordinates)]


def _position_kind(position: Any) -> str:
    """Return 'robot', 'dock' or '' for a deebot-client position."""
    name = str(getattr(position.type, "name", position.type)).upper()
    if "CHARGER" in name:
        return "dock"
    if "DEEBOT" in name:
        return "robot"
    return ""


class YeediMapData:
    """Collects the map data of one robot and tells listeners when it changes."""

    def __init__(self, hass: HomeAssistant, device: Device) -> None:
        """Initialize."""
        self._hass = hass
        self._device = device
        self._map_id: str | None = None
        self._rooms: dict[int, dict[str, Any]] = {}
        self._robot: dict[str, float] | None = None
        self._dock: dict[str, float] | None = None
        self._trace: list[list[float]] = []
        self._trace_start: float | None = None
        self._state: State | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsubscribers: list[Callable[[], None]] = []
        self._notify_handle: asyncio.TimerHandle | None = None
        self._poll_task: asyncio.Task | None = None
        self._updated = time.time()

    # ------------------------------------------------------------------ setup

    def start(self) -> None:
        """Subscribe to the robot's events."""
        events = self._device.events
        self._unsubscribers += [
            events.subscribe(StateEvent, self._on_state),
            events.subscribe(PositionsEvent, self._on_positions),
            events.subscribe(RoomsEvent, self._on_rooms),
            events.subscribe(MapSubsetEvent, self._on_map_subset),
            events.subscribe(CachedMapInfoEvent, self._on_map_info),
        ]

    def stop(self) -> None:
        """Unsubscribe from everything."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        if self._notify_handle is not None:
            self._notify_handle.cancel()
        if self._poll_task is not None:
            self._poll_task.cancel()

    # ---------------------------------------------------------------- events

    async def _on_map_info(self, event: CachedMapInfoEvent) -> None:
        current = next((m for m in event.maps if m.using), None)
        if current is not None and current.id != self._map_id:
            self._map_id = current.id
            self._schedule_notify()

    async def _on_rooms(self, event: RoomsEvent) -> None:
        if getattr(event, "map_id", None):
            self._map_id = str(event.map_id)
        seen = set()
        for room in event.rooms:
            seen.add(room.id)
            entry = self._rooms.setdefault(room.id, {"id": room.id, "outline": []})
            entry["name"] = room.name
            if outline := _parse_outline(getattr(room, "coordinates", "")):
                entry["outline"] = outline
        for room_id in set(self._rooms) - seen:
            self._rooms.pop(room_id)
        self._schedule_notify()

    async def _on_map_subset(self, event: MapSubsetEvent) -> None:
        if event.type is not MapSetType.ROOMS:
            return
        entry = self._rooms.setdefault(event.id, {"id": event.id, "outline": []})
        if event.name:
            entry.setdefault("name", event.name)
        if outline := _parse_outline(event.coordinates):
            entry["outline"] = outline
        self._schedule_notify()

    async def _on_state(self, event: StateEvent) -> None:
        previous, self._state = self._state, event.state
        if event.state is State.CLEANING and previous not in (
            State.CLEANING,
            State.PAUSED,
            State.RETURNING,
        ):
            # A new cleaning: start a new trace.
            self._trace = []
            self._trace_start = time.time()
        if event.state in _MOVING:
            self._start_polling()
        self._schedule_notify()

    async def _on_positions(self, event: PositionsEvent) -> None:
        for position in event.positions:
            kind = _position_kind(position)
            point = {"x": position.x, "y": position.y, "a": position.a}
            if kind == "dock":
                self._dock = point
            elif kind == "robot":
                self._robot = point
                if self._state in (State.CLEANING, State.RETURNING):
                    self._add_to_trace(position.x, position.y)
        self._schedule_notify()

    def _add_to_trace(self, x: float, y: float) -> None:
        if self._trace:
            last_x, last_y = self._trace[-1]
            if abs(last_x - x) < _MIN_STEP_MM and abs(last_y - y) < _MIN_STEP_MM:
                return
        self._trace.append([x, y])
        if len(self._trace) > _MAX_TRACE_POINTS:
            # Keep the whole shape: drop every other point of the oldest half.
            half = len(self._trace) // 2
            self._trace = self._trace[:half:2] + self._trace[half:]

    # --------------------------------------------------------------- polling

    def _start_polling(self) -> None:
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = self._hass.async_create_background_task(
                self._poll_positions(), name="yeedi_map_positions"
            )

    async def _poll_positions(self) -> None:
        """Ask for the position while the robot moves (not every model pushes it)."""
        while self._state in _MOVING:
            self._device.events.request_refresh(PositionsEvent)
            await asyncio.sleep(_POLL_INTERVAL)
        # One last time, to get the robot back on its dock.
        self._device.events.request_refresh(PositionsEvent)

    # ------------------------------------------------------------- listeners

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call ``listener`` when the data changes; return the remover."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def _schedule_notify(self) -> None:
        self._updated = time.time()
        if self._notify_handle is None:
            self._notify_handle = self._hass.loop.call_later(
                _NOTIFY_DELAY, self._notify
            )

    @callback
    def _notify(self) -> None:
        self._notify_handle = None
        for listener in list(self._listeners):
            listener()

    # ------------------------------------------------------------------ data

    def as_dict(self) -> dict[str, Any]:
        """Return the map data, as sent to the card."""
        return {
            "map_id": self._map_id,
            "rooms": [
                {"id": r["id"], "name": r.get("name") or "", "outline": r["outline"]}
                for r in sorted(self._rooms.values(), key=lambda r: r["id"])
            ],
            "robot": self._robot,
            "dock": self._dock,
            "trace": self._trace,
            "trace_start": self._trace_start,
            "state": self._state.name.lower() if self._state is not None else None,
            "updated": self._updated,
        }
