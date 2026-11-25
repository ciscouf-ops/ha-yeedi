"""Commands that fall back to another one when the robot answers "rcp not support"."""

from __future__ import annotations

from deebot_client.commands import StationAction
from deebot_client.models import CleanAction, CleanMode
from deebot_client.message import HandlingState

from custom_components.yeedi.commands import (
    CleanAreaOrCleanAreaV2,
    CleanAreaV2OrCleanArea,
    CleanOrCleanV2,
    CleanV2OrClean,
    StationActionOrEmptyDustbin,
)

from .conftest import FakeEventBus


def _response(code: int, msg: str) -> dict:
    return {"ret": "ok", "resp": {"header": {}, "body": {"code": code, "msg": msg}}}


NOT_SUPPORTED = _response(20003, "rcp not support")
OK = _response(0, "ok")


def test_clean_falls_back_to_clean_v2() -> None:
    result = CleanOrCleanV2(CleanAction.START)._handle_response(FakeEventBus(), NOT_SUPPORTED)
    assert result.state == HandlingState.SUCCESS
    (fallback,) = result.requested_commands
    assert fallback.NAME == "clean_V2"
    assert fallback._args == {"act": "start", "content": {"type": "auto"}}


def test_clean_ok_or_other_error_has_no_fallback() -> None:
    command = CleanOrCleanV2(CleanAction.PAUSE)
    assert command.NAME == "clean"
    ok = command._handle_response(FakeEventBus(), OK)
    assert ok.state == HandlingState.SUCCESS
    assert not ok.requested_commands
    busy = command._handle_response(FakeEventBus(), _response(30000, "busy"))
    assert busy.state == HandlingState.FAILED
    assert not busy.requested_commands


def test_clean_area_falls_back_to_clean_area_v2() -> None:
    command = CleanAreaOrCleanAreaV2(CleanMode.SPOT_AREA, [1, 3], 2)
    assert command._args["content"] == "1,3"
    result = command._handle_response(FakeEventBus(), NOT_SUPPORTED)
    (fallback,) = result.requested_commands
    assert fallback.NAME == "clean_V2"
    assert fallback._args["content"]["value"] == "1,3"


def test_station_action_falls_back_to_set_auto_empty() -> None:
    command = StationActionOrEmptyDustbin(StationAction.EMPTY_DUSTBIN)
    assert command.NAME == "stationAction"
    result = command._handle_response(FakeEventBus(), NOT_SUPPORTED)
    (fallback,) = result.requested_commands
    assert fallback.NAME == "setAutoEmpty"
    assert fallback._args == {"act": "start"}


async def test_fallback_runs_through_deebot_client(monkeypatch) -> None:
    """End to end: deebot-client sends the fallback after a "not supported" answer."""
    sent: list[str] = []

    async def fake_request(self, authenticator, device_info):
        sent.append(self.NAME)
        return NOT_SUPPORTED if self.NAME == "clean" else OK

    from deebot_client.command import Command

    monkeypatch.setattr(Command, "_execute_api_request", fake_request)
    bus = FakeEventBus()
    bus.get_last_event = lambda _event: None  # robot idle: start, not resume
    result = await CleanOrCleanV2(CleanAction.START).execute(
        None, {"class": "h041es", "did": "x"}, bus
    )
    assert sent == ["clean", "clean_V2"]
    assert result.device_reached


def test_clean_v2_first_falls_back_to_clean() -> None:
    """Unknown models: clean_V2 first, clean if the robot does not know it."""
    command = CleanV2OrClean(CleanAction.START)
    assert command.NAME == "clean_V2"
    (fallback,) = command._handle_response(FakeEventBus(), NOT_SUPPORTED).requested_commands
    assert fallback.NAME == "clean"
    assert fallback._args == {"act": "start", "type": "auto"}
    area = CleanAreaV2OrCleanArea(CleanMode.SPOT_AREA, [4], 1)
    assert area.NAME == "clean_V2"
    (fallback,) = area._handle_response(FakeEventBus(), NOT_SUPPORTED).requested_commands
    assert (fallback.NAME, fallback._args["content"]) == ("clean", "4")

