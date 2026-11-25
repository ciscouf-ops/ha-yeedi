"""Commands specific to Yeedi robots.

Yeedi robots (at least the vac max, class 04z443) never answer ``getCachedMapInfo``, the
command deebot-client uses to discover the current map. They do answer
``getMapInfo_V2`` with the current map id, and the usual ``getMapSet`` / ``getMapSubSet``
pair for the rooms. ``GetMapInfoV2`` plugs that into deebot-client's map handling by
emitting the same ``CachedMapInfoEvent`` and requesting the rooms right after.

Some models (seen on the vac station, class mnx7f4) answer ``getMapSubSet`` with an empty
outline, always. They send the outlines in an ``onMapInfo_V2`` message instead, pushed
after every ``getMapInfo_V2``. ``OnYeediMapInfoV2`` reads them.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from deebot_client.commands import StationAction as _StationAction
from deebot_client.commands.json import station_action
from deebot_client.commands.json.clean import Clean, CleanArea, CleanAreaV2, CleanV2
from deebot_client.commands.json.common import (
    ExecuteCommand,
    JsonCommandWithMessageHandling,
)
from deebot_client.commands.json.map import GetMapSet
from deebot_client.events import MapSetType
from deebot_client.events.map import CachedMapInfoEvent, Map, MapSubsetEvent
from deebot_client.message import HandlingResult, HandlingState, MessageBodyDataDict
from deebot_client.messages.json.map import OnMapInfoV2
from deebot_client.rs.map import RotationAngle
from deebot_client.rs.util import decompress_base64_data

if TYPE_CHECKING:
    from deebot_client.command import Command
    from deebot_client.commands import StationAction
    from deebot_client.event_bus import EventBus
    from deebot_client.models import CleanAction, CleanMode

_LOGGER = logging.getLogger(__name__)


class GetMapInfoV2(JsonCommandWithMessageHandling, MessageBodyDataDict):
    """Get the current map id (Yeedi replacement for getCachedMapInfo)."""

    NAME = "getMapInfo_V2"

    def __init__(self) -> None:
        super().__init__({"type": "0"})

    @classmethod
    def _handle_body_data_dict(
        cls, event_bus: EventBus, data: dict[str, Any]
    ) -> HandlingResult:
        map_id = str(data.get("mid", "") or "")
        if not map_id or map_id == "0":
            return HandlingResult.analyse()

        current = Map(
            id=map_id,
            name=data.get("name") or "standard",
            using=True,
            built=True,
            angle=RotationAngle.from_int(0),
        )
        event_bus.notify(CachedMapInfoEvent(maps={current}))
        return HandlingResult(HandlingState.SUCCESS, {"map_id": map_id})

    def _handle_response(
        self, event_bus: EventBus, response: dict[str, Any]
    ) -> HandlingResult:
        result = super()._handle_response(event_bus, response)
        if result.state == HandlingState.SUCCESS and result.args:
            result.requested_commands.append(
                GetMapSet(result.args["map_id"], MapSetType.ROOMS)
            )
        return result


def _room_outlines(info: str) -> dict[int, str]:
    """Return {room id: "x,y;x,y;..."} from the ``info`` of a yeedi ``onMapInfo_V2``.

    Once decompressed, ``info`` is a list of sections, ``[name, item, item, ...]``, each
    item being ``"<room id>;<point>;<point>;..."``. Section "2" holds the outlines
    ``getMapSubSet`` gives on other models (points ``x,y``); section "1" holds the walls of
    each room (points ``x,y,kind``) and is used for a room section "2" does not have.
    """
    sections = {
        str(section[0]): section[1:]
        for section in json.loads(decompress_base64_data(info))
        if section
    }
    outlines: dict[int, str] = {}
    for name in ("2", "1"):
        for item in sections.get(name, ()):
            room_id, _, points = str(item).partition(";")
            xy = [",".join(p.split(",")[:2]) for p in points.split(";") if p.count(",")]
            if xy and room_id.isdigit():
                outlines.setdefault(int(room_id), ";".join(xy))
    return outlines


class OnYeediMapInfoV2(OnMapInfoV2):
    """``onMapInfo_V2`` as yeedi robots send it: the outline of every room.

    The message has no ``outlineVer`` field, which is how it is told apart from the
    Ecovacs one (left to deebot-client, the registry of messages being shared with it).
    """

    @classmethod
    def _handle_body_data_dict(
        cls, event_bus: EventBus, data: dict[str, Any]
    ) -> HandlingResult:
        if "outlineVer" in data or not data.get("info"):
            return super()._handle_body_data_dict(event_bus, data)
        if data.get("using") == 0:  # a map the robot is not using
            return HandlingResult.success()
        try:
            outlines = _room_outlines(data["info"])
        except (ValueError, TypeError, IndexError):
            return HandlingResult.analyse()
        for room_id, coordinates in outlines.items():
            event_bus.notify(MapSubsetEvent(room_id, MapSetType.ROOMS, coordinates))
        return HandlingResult.success()


class EmptyDustbin(ExecuteCommand):
    """Empty the dustbin into the station (yeedi vac station, class mnx7f4).

    This robot does not know ``stationAction``: emptying is ``setAutoEmpty`` with
    ``act: start``.
    """

    NAME = "setAutoEmpty"

    def __init__(self, _action: StationAction) -> None:
        super().__init__({"act": "start"})


# A robot answers ``{"code": 20003, "msg": "rcp not support"}`` to a command it does not
# know. The commands below then run their fallback instead, so a model declared on a
# best-effort basis adapts by itself (seen on the M16 Infinity for ``clean``).
_NOT_SUPPORTED = 20003


def _not_supported(response: dict[str, Any]) -> bool:
    if response.get("ret") != "ok":
        return False
    resp = response.get("resp", response)
    body = resp.get("body") if isinstance(resp, dict) else None
    return isinstance(body, dict) and body.get("code") == _NOT_SUPPORTED


class _WithFallback:
    """Mixin, before an ``ExecuteCommand``: run ``_fallback()`` when the robot does not
    support the command."""

    NAME: str

    def _fallback(self) -> Command | None:
        raise NotImplementedError

    @classmethod
    def _handle_body(cls, event_bus: EventBus, body: dict[str, Any]) -> HandlingResult:
        if body.get("code") == _NOT_SUPPORTED:
            _LOGGER.debug('"%s" not supported by the robot, using the fallback', cls.NAME)
            return HandlingResult(HandlingState.FAILED)
        return super()._handle_body(event_bus, body)  # type: ignore[misc]

    def _handle_response(
        self, event_bus: EventBus, response: dict[str, Any]
    ) -> HandlingResult:
        result = super()._handle_response(event_bus, response)  # type: ignore[misc]
        if (
            result.state == HandlingState.FAILED
            and _not_supported(response)
            and (fallback := self._fallback()) is not None
        ):
            # SUCCESS so that deebot-client runs the requested command.
            return HandlingResult(HandlingState.SUCCESS, requested_commands=[fallback])
        return result


class StationActionOrEmptyDustbin(_WithFallback, station_action.StationAction):
    """``stationAction``, or ``setAutoEmpty act:start`` (yeedi vac station way)."""

    def __init__(self, action: StationAction) -> None:
        super().__init__(action)
        self._action = action

    def _fallback(self) -> Command | None:
        # Only emptying has a known other way; washing or drying the mop has none.
        if self._action is _StationAction.EMPTY_DUSTBIN:
            return EmptyDustbin(self._action)
        return None


class CleanOrCleanV2(_WithFallback, Clean):
    """``clean``, or ``clean_V2`` on the robots that only know the latter."""

    def __init__(self, action: CleanAction) -> None:
        super().__init__(action)
        self._action = action

    def _fallback(self) -> Command:
        return CleanV2(self._action)


class CleanAreaOrCleanAreaV2(_WithFallback, CleanArea):
    """Area cleaning with ``clean``, or with ``clean_V2``."""

    def __init__(
        self, mode: CleanMode, area: list[int | float], cleanings: int = 1
    ) -> None:
        super().__init__(mode, area, cleanings)
        self._area_args = (mode, list(area), cleanings)

    def _fallback(self) -> Command:
        return CleanAreaV2(*self._area_args)
