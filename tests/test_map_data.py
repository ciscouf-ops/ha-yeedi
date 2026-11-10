"""Tests for the map data collected for the card."""

from __future__ import annotations

import asyncio

from deebot_client.events import (
    MapSetType,
    MapSubsetEvent,
    PositionsEvent,
    RoomsEvent,
    StateEvent,
)
from deebot_client.events.map import Position
from deebot_client.models import Room, State
from deebot_client.rs.map import PositionType
import pytest

from custom_components.yeedi.map_data import YeediMapData, _parse_outline

SQUARE = "0,0;1000,0;1000,1000;0,1000"


def test_parse_outline() -> None:
    assert _parse_outline(SQUARE) == [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]
    assert _parse_outline("") == []
    assert _parse_outline(None) == []
    assert _parse_outline("12.5, -3;4,5") == [[12.5, -3], [4, 5]]


async def test_rooms_and_outlines(hass, device) -> None:
    data = YeediMapData(hass, device)
    await data.async_start()

    await device.events.emit(RoomsEvent("m1", [Room("Living Room", 2, SQUARE), Room("Default", 1, "")]))
    rooms = {r["id"]: r for r in data.as_dict()["rooms"]}
    assert rooms[2]["name"] == "Living Room"
    assert len(rooms[2]["outline"]) == 4
    assert rooms[1]["outline"] == []
    assert data.as_dict()["map_id"] == "m1"

    # An empty answer later must not erase a known outline (yeedi does that a lot).
    await device.events.emit(RoomsEvent("m1", [Room("Living Room", 2, ""), Room("Default", 1, "")]))
    assert len({r["id"]: r for r in data.as_dict()["rooms"]}[2]["outline"]) == 4

    # Outlines also arrive through MapSubsetEvent, rooms only.
    await device.events.emit(MapSubsetEvent(1, MapSetType.ROOMS, SQUARE, "Default"))
    await device.events.emit(MapSubsetEvent(9, MapSetType.VIRTUAL_WALLS, "0,0;500,0"))
    await device.events.emit(MapSubsetEvent(3, MapSetType.NO_MOP_ZONES, SQUARE))
    d = data.as_dict()
    rooms = {r["id"]: r for r in d["rooms"]}
    assert len(rooms[1]["outline"]) == 4
    assert 9 not in rooms
    assert d["walls"] == [{"id": 9, "points": [[0, 0], [500, 0]]}]
    assert d["no_mop"][0]["id"] == 3 and len(d["no_mop"][0]["points"]) == 4

    # A room that disappears from the robot's list is dropped.
    await device.events.emit(RoomsEvent("m1", [Room("Living Room", 2, SQUARE)]))
    assert [r["id"] for r in data.as_dict()["rooms"]] == [2]
    data.stop()


async def test_trace_follows_cleaning(hass, device) -> None:
    data = YeediMapData(hass, device)
    await data.async_start()

    def pos(x, y, kind=PositionType.DEEBOT):
        return PositionsEvent([Position(kind, x, y, 0)])

    # Docked: the position is kept, the trace is not.
    await device.events.emit(StateEvent(State.DOCKED))
    await device.events.emit(pos(10, 10))
    await device.events.emit(pos(500, 500, PositionType.CHARGER))
    d = data.as_dict()
    assert d["robot"] == {"x": 10, "y": 10, "a": 0}
    assert d["dock"] == {"x": 500, "y": 500, "a": 0}
    assert d["trace"] == []

    # Cleaning: a new trace, points closer than 40 mm are skipped.
    await device.events.emit(StateEvent(State.CLEANING))
    await device.events.emit(pos(0, 0))
    await device.events.emit(pos(20, 20))
    await device.events.emit(pos(100, 0))
    assert data.as_dict()["trace"] == [[0, 0], [100, 0]]
    assert data.as_dict()["state"] == "cleaning"

    # Pause keeps the trace; a brand-new cleaning (from docked) starts another one.
    await device.events.emit(StateEvent(State.PAUSED))
    await device.events.emit(StateEvent(State.CLEANING))
    assert data.as_dict()["trace"] == [[0, 0], [100, 0]]
    await device.events.emit(StateEvent(State.DOCKED))
    await device.events.emit(StateEvent(State.CLEANING))
    assert data.as_dict()["trace"] == []
    data.stop()


async def test_outlines_requested_when_cleaning_starts(hass, device) -> None:
    data = YeediMapData(hass, device)
    await data.async_start()
    await device.events.emit(RoomsEvent("m1", [Room("Default", 1, "")]))
    await device.events.emit(StateEvent(State.CLEANING))
    await asyncio.sleep(0)  # let the refresh task start
    assert RoomsEvent in device.events.refreshed
    data.stop()


async def test_outlines_are_persisted(hass, device, hass_storage) -> None:
    data = YeediMapData(hass, device)
    await data.async_start()
    await device.events.emit(RoomsEvent("m1", [Room("Study", 4, SQUARE)]))
    await device.events.emit(PositionsEvent([Position(PositionType.CHARGER, 7, 8, 0)]))
    await data.async_stop()  # writes the pending save

    saved = hass_storage["yeedi.map_did123"]["data"]
    assert saved["map_id"] == "m1"
    assert saved["walls"] == [] and saved["no_mop"] == []
    assert saved["dock"] == {"x": 7, "y": 8, "a": 0}
    assert saved["rooms"][0]["id"] == 4 and len(saved["rooms"][0]["outline"]) == 4

    # A fresh instance (Home Assistant restart) starts from the saved outlines.
    again = YeediMapData(hass, device)
    await again.async_start()
    d = again.as_dict()
    assert d["dock"] == {"x": 7, "y": 8, "a": 0}
    assert [r["id"] for r in d["rooms"]] == [4]
    again.stop()


async def test_damaged_storage_starts_empty(hass, device, hass_storage) -> None:
    hass_storage["yeedi.map_did123"] = {"version": 1, "data": {"rooms": [{"id": "x"}, {"id": 3}]}}
    data = YeediMapData(hass, device)
    await data.async_start()
    assert [r["id"] for r in data.as_dict()["rooms"]] == [3]
    data.stop()


def test_listeners(hass, device) -> None:
    data = YeediMapData(hass, device)
    calls = []
    remove = data.async_add_listener(lambda: calls.append(1))
    data._notify()
    remove()
    data._notify()
    assert calls == [1]
