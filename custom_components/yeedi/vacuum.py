"""Vacuum entity for Yeedi robots."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from deebot_client.capabilities import Capabilities, DeviceType
from deebot_client.device import Device
from deebot_client.events import (
    CachedMapInfoEvent,
    ErrorEvent,
    RoomsEvent,
    StateEvent,
)
from deebot_client.events.map import Map
from deebot_client.models import CleanAction, CleanMode, State

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .controller import YeediConfigEntry
from .entity import YeediEntity
from .suction import YeediSuction

_LOGGER = logging.getLogger(__name__)
_SEGMENTS_SEPARATOR = "_"
ATTR_ROOMS = "rooms"
ATTR_ERROR = "error"

_STATE_TO_ACTIVITY = {
    State.IDLE: VacuumActivity.IDLE,
    State.CLEANING: VacuumActivity.CLEANING,
    State.RETURNING: VacuumActivity.RETURNING,
    State.DOCKED: VacuumActivity.DOCKED,
    State.ERROR: VacuumActivity.ERROR,
    State.PAUSED: VacuumActivity.PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the vacuums."""
    controller = entry.runtime_data
    async_add_entities(
        YeediVacuum(device, controller.suction[device.device_info["did"]])
        for device in controller.devices
        if device.capabilities.device_type is DeviceType.VACUUM
    )


class YeediVacuum(YeediEntity[Capabilities], StateVacuumEntity, RestoreEntity):
    """A Yeedi robot vacuum."""

    _unrecorded_attributes = frozenset({ATTR_ROOMS})
    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )
    entity_description = StateVacuumEntityDescription(
        key="vacuum", translation_key="vacuum", name=None
    )

    def __init__(self, device: Device, suction: YeediSuction) -> None:
        """Initialize the vacuum."""
        super().__init__(device, device.capabilities)
        self._suction = suction
        self._rooms: RoomsEvent | None = None
        self._maps: dict[str, Map] = {}
        self._error: str | None = None
        if suction.supported:
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED
            self._attr_fan_speed_list = suction.options
        if self._capability.map and self._capability.clean.action.area:
            self._attr_supported_features |= VacuumEntityFeature.CLEAN_AREA

    async def async_added_to_hass(self) -> None:
        """Subscribe to the robot's events."""
        await super().async_added_to_hass()

        # The robot does not report the mop-only setting: keep the last one set from HA.
        if (last := await self.async_get_last_state()) is not None:
            self._suction.restore(last.attributes.get("fan_speed"))

        async def on_state(event: StateEvent) -> None:
            self._attr_activity = _STATE_TO_ACTIVITY[event.state]
            self.async_write_ha_state()

        self._subscribe(self._capability.state.event, on_state)

        async def on_error(event: ErrorEvent) -> None:
            self._error = event.description if event.code else None
            self.async_write_ha_state()

        self._subscribe(self._capability.error.event, on_error)

        if self._suction.supported:

            @callback
            def on_suction() -> None:
                self._attr_fan_speed = self._suction.current
                self.async_write_ha_state()

            self.async_on_remove(self._suction.add_listener(on_suction))
            self._attr_fan_speed = self._suction.current

        if map_caps := self._capability.map:

            async def on_rooms(event: RoomsEvent) -> None:
                self._rooms = event
                self.async_write_ha_state()

            self._subscribe(map_caps.rooms.event, on_rooms)

            async def on_map_info(event: CachedMapInfoEvent) -> None:
                self._maps = {m.id: m for m in event.maps}

            self._subscribe(map_caps.cached_info.event, on_map_info)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Expose rooms and the current error."""
        rooms: dict[str, Any] = {}
        if self._rooms is not None:
            for room in self._rooms.rooms:
                key = slugify(room.name) or f"room_{room.id}"
                if key in rooms:
                    current = rooms[key]
                    rooms[key] = (current if isinstance(current, list) else [current]) + [room.id]
                else:
                    rooms[key] = room.id
        return {ATTR_ROOMS: rooms, ATTR_ERROR: self._error}

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the suction power, or mop only (vacuum motor off)."""
        await self._suction.async_set(fan_speed)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return to the dock."""
        await self._device.execute_command(self._capability.charge.execute())

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop cleaning."""
        await self._clean_command(CleanAction.STOP)

    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self._clean_command(CleanAction.PAUSE)

    async def async_start(self) -> None:
        """Start (or resume) cleaning."""
        if self._attr_activity is VacuumActivity.PAUSED:
            await self._clean_command(CleanAction.RESUME)
        else:
            await self._clean_command(CleanAction.START)

    async def _clean_command(self, action: CleanAction) -> None:
        await self._device.execute_command(self._capability.clean.action.command(action))

    async def async_locate(self, **kwargs: Any) -> None:
        """Make the robot play a sound."""
        await self._device.execute_command(self._capability.play_sound.execute())

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command: spot_area (rooms), custom_area (coordinates) or raw."""
        if params is None:
            params = {}
        elif isinstance(params, list):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="params_dict"
            )
        area = self._capability.clean.action.area
        if command in ("spot_area", "custom_area"):
            if area is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="area_not_supported"
                )
            if command == "spot_area":
                rooms = params.get("rooms")
                if rooms is None:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN, translation_key="rooms_required"
                    )
                if isinstance(rooms, list):
                    rooms = ",".join(str(r) for r in rooms)
                await self._device.execute_command(
                    area(CleanMode.SPOT_AREA, str(rooms), int(params.get("cleanings", 1)))
                )
            else:
                await self._device.execute_command(
                    area(
                        CleanMode.CUSTOM_AREA,
                        str(params["coordinates"]),
                        int(params.get("cleanings", 1)),
                    )
                )
            return
        await self._device.execute_command(self._capability.custom.set(command, params))

    def _get_segments(self) -> list[Segment]:
        if self._rooms is None:
            return list(self.last_seen_segments or [])
        map_id = getattr(self._rooms, "map_id", None) or next(iter(self._maps), "0")
        map_name = self._maps[map_id].name if map_id in self._maps else None
        return [
            Segment(
                id=f"{map_id}{_SEGMENTS_SEPARATOR}{room.id}",
                name=room.name,
                group=map_name,
            )
            for room in self._rooms.rooms
        ]

    async def async_get_segments(self) -> list[Segment]:
        """Return the rooms as cleanable segments."""
        return self._get_segments()

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean the given rooms, in the order given."""
        # segment id = "<map id>_<room id>"; the room id never contains "_".
        room_ids = [cid.rpartition(_SEGMENTS_SEPARATOR)[2] for cid in segment_ids]
        room_ids = [r for r in room_ids if r != ""]
        if not room_ids:
            _LOGGER.warning("No valid room to clean in %s", segment_ids)
            return
        if TYPE_CHECKING:
            assert self._capability.clean.action.area is not None
        await self._device.execute_command(
            self._capability.clean.action.area(CleanMode.SPOT_AREA, ",".join(room_ids), 1)
        )
