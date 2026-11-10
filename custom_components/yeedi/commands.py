"""Commands specific to Yeedi robots.

Yeedi robots (at least the vac max, class 04z443) never answer ``getCachedMapInfo``, the
command deebot-client uses to discover the current map. They do answer
``getMapInfo_V2`` with the current map id, and the usual ``getMapSet`` / ``getMapSubSet``
pair for the rooms. ``GetMapInfoV2`` plugs that into deebot-client's map handling by
emitting the same ``CachedMapInfoEvent`` and requesting the rooms right after.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.commands.json.common import JsonCommandWithMessageHandling
from deebot_client.commands.json.map import GetMapSet
from deebot_client.events import MapSetType
from deebot_client.events.map import CachedMapInfoEvent, Map
from deebot_client.message import HandlingResult, HandlingState, MessageBodyDataDict
from deebot_client.rs.map import RotationAngle

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus


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
