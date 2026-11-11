"""Live map data of a robot, for the yeedi map card.

Yeedi robots do not send a ready-made map image the way recent Deebots do, but they do
report everything a card needs to draw one:

- the outline of every room (``getMapSubSet``, already requested by deebot-client),
- the position of the robot and of the dock (``onPos`` / ``getPos``),
- the cleaning state, used here to start a new trace when a cleaning begins.

The trace is built from the robot positions received while it cleans, so it is lost
when Home Assistant restarts during a cleaning.

Yeedi robots only send the outline of the rooms now and then, mostly while cleaning (the
rest of the time ``getMapSubSet`` answers with an empty value). Outlines are therefore
asked again when a cleaning starts, and kept in Home Assistant's storage once received.
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
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

_NUMBER_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
_MIN_STEP_MM = 40  # ignore positions closer than this to the last trace point
_MAX_TRACE_POINTS = 4000
_POLL_INTERVAL = 3.0  # seconds, while the robot moves
_NOTIFY_DELAY = 0.5  # seconds, to group bursts of events
_MOVING = (State.CLEANING, State.RETURNING)
_ROOMS_RETRY_DELAYS = (0, 45, 150, 400)  # seconds after a cleaning starts
_STORAGE_VERSION = 1
# Progress and estimated end of a cleaning (see ``estimate``).
_MAX_POSITION_GAP = 20.0  # seconds: a longer silence is not counted as time in a room
_DEFAULT_RATE = 1.2  # min/m² before anything is learned (a first-pass robot)
_MIN_ROOM_MINUTES = 2.0
_LEARN_MIN_MINUTES = 1.0  # a shorter stay is a room merely crossed
_LEARN_MIN_RATE = 0.3  # min/m²: below this the room was crossed, not cleaned
_DONE_FRACTION = 0.5  # a planned room with this share of its estimate is done
_MAX_CLEANING_HOURS = 4


def _parse_outline(coordinates: str | None) -> list[list[float]]:
    """Return the points of an outline given as 'x,y;x,y;...'."""
    if not coordinates:
        return []
    return [[float(x), float(y)] for x, y in _NUMBER_PAIR.findall(coordinates)]


def _point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    """Ray casting: is (x, y) inside the polygon?"""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _polygon_area_m2(polygon: list[list[float]]) -> float:
    """Area of an outline given in millimetres, in square metres (shoelace)."""
    n = len(polygon)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2 / 1_000_000


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
        # Virtual walls and no-mop zones set in the yeedi app: {id: points}.
        self._walls: dict[int, list[list[float]]] = {}
        self._no_mop: dict[int, list[list[float]]] = {}
        self._robot: dict[str, float] | None = None
        self._dock: dict[str, float] | None = None
        self._trace: list[list[float]] = []
        self._trace_start: float | None = None
        self._state: State | None = None
        # Progress of the current cleaning: the rooms asked for (None = the whole
        # home, [] = a zone: no room estimate), the room the robot is in, the time
        # spent in each room and the order they were entered.
        self._plan: list[int] | None = None
        self._room_id: int | None = None
        self._room_time: dict[int, float] = {}
        self._room_order: list[int] = []
        self._last_position_at: float | None = None
        self._learned = False
        # What a cleaning taught: minutes per room and the order of a full cleaning.
        self._durations: dict[int, float] = {}
        self._full_order: list[int] = []
        self._listeners: list[Callable[[], None]] = []
        self._unsubscribers: list[Callable[[], None]] = []
        self._notify_handle: asyncio.TimerHandle | None = None
        self._poll_task: asyncio.Task | None = None
        self._rooms_task: asyncio.Task | None = None
        self._updated = time.time()
        self._store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, f"yeedi.map_{device.device_info['did']}"
        )
        self._save_handle: asyncio.TimerHandle | None = None

    # ------------------------------------------------------------------ setup

    async def async_start(self) -> None:
        """Load the saved outlines and subscribe to the robot's events."""
        try:
            saved = await self._store.async_load()
        except Exception:  # a damaged file must not stop the integration
            _LOGGER.warning("Saved map of %s unreadable, starting empty", self._store.key)
            saved = None
        if saved:
            self._map_id = saved.get("map_id")
            self._dock = saved.get("dock")
            for key, target in (("walls", self._walls), ("no_mop", self._no_mop)):
                for item in saved.get(key) or []:
                    try:
                        target[int(item["id"])] = list(item.get("points") or [])
                    except (KeyError, TypeError, ValueError):
                        continue
            for room in saved.get("rooms", []):
                try:
                    room_id = int(room["id"])
                except (KeyError, TypeError, ValueError):
                    continue
                self._rooms[room_id] = {
                    "id": room_id,
                    "name": room.get("name", ""),
                    "outline": room.get("outline") or [],
                }
            for key, value in (saved.get("durations") or {}).items():
                try:
                    self._durations[int(key)] = float(value)
                except (TypeError, ValueError):
                    continue
            self._full_order = [
                int(i) for i in saved.get("full_order") or [] if str(i).lstrip("-").isdigit()
            ]
        events = self._device.events
        self._unsubscribers += [
            events.subscribe(StateEvent, self._on_state),
            events.subscribe(PositionsEvent, self._on_positions),
            events.subscribe(RoomsEvent, self._on_rooms),
            events.subscribe(MapSubsetEvent, self._on_map_subset),
            events.subscribe(CachedMapInfoEvent, self._on_map_info),
        ]

    def stop(self) -> None:
        """Unsubscribe from everything (a pending save is written with a short delay)."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        if self._notify_handle is not None:
            self._notify_handle.cancel()
        if self._poll_task is not None:
            self._poll_task.cancel()
        if self._rooms_task is not None:
            self._rooms_task.cancel()
        if self._save_handle is not None:
            self._save_handle.cancel()
            self._save_now()

    async def async_stop(self) -> None:
        """Unsubscribe from everything and write a pending save right away."""
        pending = self._save_handle is not None
        if pending:
            self._save_handle.cancel()
            self._save_handle = None
        self.stop()
        if pending:
            await self._store.async_save(self._to_save())

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
                if outline != entry["outline"]:
                    entry["outline"] = outline
                    self._schedule_save()
        for room_id in set(self._rooms) - seen:
            self._rooms.pop(room_id)
            self._schedule_save()
        self._schedule_notify()

    async def _on_map_subset(self, event: MapSubsetEvent) -> None:
        if event.type in (MapSetType.VIRTUAL_WALLS, MapSetType.NO_MOP_ZONES):
            target = self._walls if event.type is MapSetType.VIRTUAL_WALLS else self._no_mop
            points = _parse_outline(event.coordinates)
            if points and target.get(event.id) != points:
                target[event.id] = points
                self._schedule_save()
                self._schedule_notify()
            return
        if event.type is not MapSetType.ROOMS:
            return
        entry = self._rooms.setdefault(event.id, {"id": event.id, "outline": []})
        if event.name:
            entry.setdefault("name", event.name)
        if outline := _parse_outline(event.coordinates):
            if outline != entry["outline"]:
                entry["outline"] = outline
                self._schedule_save()
        self._schedule_notify()

    async def _on_state(self, event: StateEvent) -> None:
        previous, self._state = self._state, event.state
        if event.state is State.CLEANING and previous not in (
            State.CLEANING,
            State.PAUSED,
            State.RETURNING,
        ):
            # A new cleaning: start a new trace and a new progress record.
            self._trace = []
            self._trace_start = time.time()
            self._room_id = None
            self._room_time = {}
            self._room_order = []
            self._last_position_at = None
            self._learned = False
            if any(not r["outline"] for r in self._rooms.values()) or not self._rooms:
                self._start_rooms_refresh()
        if event.state in _MOVING:
            self._start_polling()
        else:
            self._last_position_at = None
        if event.state is State.DOCKED and previous in _MOVING + (State.PAUSED,):
            self._learn()
        self._schedule_notify()

    async def _on_positions(self, event: PositionsEvent) -> None:
        for position in event.positions:
            kind = _position_kind(position)
            point = {"x": position.x, "y": position.y, "a": position.a}
            if kind == "dock":
                if point != self._dock:
                    self._dock = point
                    self._schedule_save()
            elif kind == "robot":
                self._robot = point
                if self._state in (State.CLEANING, State.RETURNING):
                    self._add_to_trace(position.x, position.y)
                if self._state is State.CLEANING:
                    self._track_room(position.x, position.y)
        self._schedule_notify()

    # -------------------------------------------------------------- progress

    def set_plan(self, rooms: list[int] | None) -> None:
        """Remember what the next cleaning covers: room ids, None (all) or [] (a zone)."""
        self._plan = None if rooms is None else [int(r) for r in rooms]

    def _room_at(self, x: float, y: float) -> int | None:
        """The room containing the point, the current one first (no flicker on an edge)."""
        if self._room_id is not None:
            current = self._rooms.get(self._room_id)
            if current and _point_in_polygon(x, y, current["outline"]):
                return self._room_id
        for room in self._rooms.values():
            if _point_in_polygon(x, y, room["outline"]):
                return room["id"]
        return None

    def _track_room(self, x: float, y: float) -> None:
        now = time.time()
        room_id = self._room_at(x, y)
        if room_id is not None and self._last_position_at is not None:
            elapsed = min(now - self._last_position_at, _MAX_POSITION_GAP)
            if elapsed > 0:
                self._room_time[room_id] = self._room_time.get(room_id, 0.0) + elapsed
        self._last_position_at = now
        if room_id is not None:
            if room_id != self._room_id:
                self._room_id = room_id
            if room_id not in self._room_order:
                self._room_order.append(room_id)

    def _learn(self) -> None:
        """Back on the dock: remember how long each room took (once per cleaning)."""
        if self._learned or not self._room_time:
            return
        self._learned = True
        changed = False
        for room_id, seconds in self._room_time.items():
            minutes = seconds / 60
            area = self._room_area(room_id)
            if minutes < _LEARN_MIN_MINUTES or (area and minutes / area < _LEARN_MIN_RATE):
                continue  # only crossed, not cleaned
            old = self._durations.get(room_id)
            self._durations[room_id] = round((old + minutes) / 2 if old else minutes, 1)
            changed = True
        if self._plan is None and len(self._room_order) >= 2:
            if self._room_order != self._full_order:
                self._full_order = list(self._room_order)
                changed = True
        if changed:
            self._schedule_save()

    def _room_area(self, room_id: int) -> float:
        room = self._rooms.get(room_id)
        return _polygon_area_m2(room["outline"]) if room else 0.0

    def _estimate_minutes(self, room_id: int) -> float:
        """Minutes to clean a room: learned, else from its area and the learned rate."""
        if (learned := self._durations.get(room_id)) is not None:
            return max(_MIN_ROOM_MINUTES, learned)
        known = [(self._room_area(i), m) for i, m in self._durations.items()]
        known = [(a, m) for a, m in known if a > 0]
        rate = sum(m for _, m in known) / sum(a for a, _ in known) if known else _DEFAULT_RATE
        area = self._room_area(room_id)
        return max(_MIN_ROOM_MINUTES, area * rate) if area else 8.0

    def estimate(self) -> dict[str, Any] | None:
        """Where the cleaning stands: room, minutes left, estimated end; None when idle."""
        if self._state is not State.CLEANING or self._trace_start is None:
            return None
        if self._plan == []:
            planned: list[int] = []  # a zone: no room to count
        elif self._plan is not None:
            planned = [i for i in self._plan if i in self._rooms]
        elif self._full_order:
            planned = [i for i in self._full_order if i in self._rooms]
            planned += [i for i in sorted(self._rooms) if i not in planned]
        else:
            planned = sorted(self._rooms)
        now = time.time()
        elapsed = (now - self._trace_start) / 60
        remaining: float | None = None
        if planned:
            remaining = 0.0
            for room_id in planned:
                est = self._estimate_minutes(room_id)
                spent = self._room_time.get(room_id, 0.0) / 60
                if room_id == self._room_id:
                    remaining += max(1.0, est - spent)
                elif spent >= est * _DONE_FRACTION:
                    continue  # done
                else:
                    remaining += est
        room = self._rooms.get(self._room_id) if self._room_id is not None else None
        result: dict[str, Any] = {
            "room_id": self._room_id,
            "room": (room or {}).get("name") or None,
            "started": self._trace_start,
            "elapsed_minutes": round(elapsed, 1),
            "remaining_minutes": None if remaining is None else round(remaining),
            "end": None if remaining is None else now + remaining * 60,
            "progress": None,
            "planned": planned,
        }
        if remaining is not None and elapsed + remaining > 0:
            result["progress"] = min(99, round(elapsed / (elapsed + remaining) * 100))
        return result

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

    def _start_rooms_refresh(self) -> None:
        if self._rooms_task is None or self._rooms_task.done():
            self._rooms_task = self._hass.async_create_background_task(
                self._refresh_rooms(), name="yeedi_map_rooms"
            )

    async def _refresh_rooms(self) -> None:
        """Ask for the room outlines a few times while the robot cleans."""
        for i, delay in enumerate(_ROOMS_RETRY_DELAYS):
            if i:
                await asyncio.sleep(delay - _ROOMS_RETRY_DELAYS[i - 1])
            if self._rooms and all(r["outline"] for r in self._rooms.values()):
                return
            if self._state not in (State.CLEANING, State.PAUSED):
                return
            self._device.events.request_refresh(RoomsEvent)

    # --------------------------------------------------------------- storage

    def _schedule_save(self) -> None:
        if self._save_handle is None:
            self._save_handle = self._hass.loop.call_later(5, self._save_now)

    def _to_save(self) -> dict[str, Any]:
        return {
            "map_id": self._map_id,
            "dock": self._dock,
            "rooms": [
                {"id": r["id"], "name": r.get("name", ""), "outline": r["outline"]}
                for r in self._rooms.values()
            ],
            "walls": [{"id": i, "points": p} for i, p in self._walls.items()],
            "no_mop": [{"id": i, "points": p} for i, p in self._no_mop.items()],
            "durations": {str(i): m for i, m in self._durations.items()},
            "full_order": list(self._full_order),
        }

    @callback
    def _save_now(self) -> None:
        self._save_handle = None
        self._store.async_delay_save(self._to_save, 1)

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
            "walls": [{"id": i, "points": p} for i, p in sorted(self._walls.items())],
            "no_mop": [{"id": i, "points": p} for i, p in sorted(self._no_mop.items())],
            "robot": self._robot,
            "dock": self._dock,
            "trace": self._trace,
            "trace_start": self._trace_start,
            "state": self._state.name.lower() if self._state is not None else None,
            "progress": self.estimate(),
            "updated": self._updated,
        }
