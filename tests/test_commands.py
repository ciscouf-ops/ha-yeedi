"""Tests for the yeedi-specific messages."""

from __future__ import annotations

import base64
import json
import lzma
from unittest.mock import MagicMock

from deebot_client.events import MapSetType
from deebot_client.events.map import MapInfoEvent, MapSubsetEvent
from deebot_client.message import HandlingState
from deebot_client.messages.json import MESSAGES

from custom_components.yeedi.commands import OnYeediMapInfoV2
from custom_components.yeedi.hardware import register_yeedi_models
from custom_components.yeedi.map_data import YeediMapData


def _info(sections: list) -> str:
    """Compress like the robot: LZMA with a 4-byte length, in base64."""
    data = json.dumps(sections).encode()
    raw = lzma.compress(data, format=lzma.FORMAT_ALONE)
    return base64.b64encode(raw[:5] + len(data).to_bytes(4, "little") + raw[13:]).decode()


def _handle(data: dict) -> tuple[HandlingState, list]:
    bus = MagicMock()
    result = OnYeediMapInfoV2.handle(bus, {"header": {}, "body": {"data": data}})
    return result.state, [call.args[0] for call in bus.notify.call_args_list]


INFO = _info(
    [
        ["1", "0;0,0,1;1000,0,2;1000,1000,3-0-1;0,1000,1", "7;0,0,1;50,0,1;50,50,1"],
        ["2", "0;100,100;900,100;900,900;100,900"],
        ["3"],
    ]
)


def test_registered_for_the_message() -> None:
    register_yeedi_models()
    assert MESSAGES["onMapInfo_V2"] is OnYeediMapInfoV2


def test_room_outlines_from_map_info() -> None:
    state, events = _handle({"mid": "m1", "using": 1, "type": "0", "info": INFO})
    assert state == HandlingState.SUCCESS
    assert events == [
        MapSubsetEvent(0, MapSetType.ROOMS, "100,100;900,100;900,900;100,900"),
        # No outline in section "2": the walls of the room are used, without their kind.
        MapSubsetEvent(7, MapSetType.ROOMS, "0,0;50,0;50,50"),
    ]


def test_other_map_and_garbage_are_ignored() -> None:
    assert _handle({"mid": "m2", "using": 0, "info": INFO}) == (HandlingState.SUCCESS, [])
    assert _handle({"mid": "m1", "using": 1, "info": "AAAA"}) == (
        HandlingState.ANALYSE_LOGGED,
        [],
    )
    assert _handle({"mid": "m1", "using": 1, "info": _info({"no": "list"})})[1] == []


def test_ecovacs_message_is_left_to_deebot_client() -> None:
    state, events = _handle({"mid": "m1", "outlineVer": "1", "info": "abc"})
    assert state == HandlingState.SUCCESS
    assert events == [MapInfoEvent(map_id="m1", info="abc")]


async def test_outlines_reach_the_map(hass, device) -> None:
    data = YeediMapData(hass, device)
    await data.async_start()
    for event in _handle({"mid": "m1", "using": 1, "info": INFO})[1]:
        await device.events.emit(event)
    rooms = {r["id"]: r["outline"] for r in data.as_dict()["rooms"]}
    assert rooms[0] == [[100, 100], [900, 100], [900, 900], [100, 900]]
    data.stop()
