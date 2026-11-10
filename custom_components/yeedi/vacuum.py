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
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import voluptuous as vol
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
ATTR_CLEANINGS = "cleanings"
ATTR_ZONE = "zone"
SERVICE_CLEAN_ROOMS = "clean_rooms"
SERVICE_CLEAN_ZONE = "clean_zone"
MIN_ZONE_SIDE_M = 1.0  # the robot does a thinner zone in one straight line


def _min_side(a: float, b: float, minimum: float) -> tuple[float, float]:
    """Return (low, high), widened around the middle to at least `minimum`."""
    low, high = min(a, b), max(a, b)
    if high - low >= minimum:
        return low, high
    mid = (low + high) / 2
    return mid - minimum / 2, mid + minimum / 2

_CLEANINGS = vol.All(vol.Coerce(int), vol.Range(min=1, max=2))
CLEAN_ROOMS_SCHEMA = {
    vol.Required(ATTR_ROOMS): vol.All(cv.ensure_list, [vol.Any(cv.positive_int, cv.string)]),
    vol.Optional(ATTR_CLEANINGS, default=1): _CLEANINGS,
}
CLEAN_ZONE_SCHEMA = {
    vol.Required(ATTR_ZONE): vol.All(
        cv.ensure_list, [vol.Coerce(float)], vol.Length(min=4, max=4)
    ),
    vol.Optional(ATTR_CLEANINGS, default=1): _CLEANINGS,
}

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
    """Set up the vacuums and their actions."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CLEAN_ROOMS, CLEAN_ROOMS_SCHEMA, "async_clean_rooms"
    )
    platform.async_register_entity_service(
        SERVICE_CLEAN_ZONE, CLEAN_ZONE_SCHEMA, "async_clean_zone"
    )
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

    def _room_id(self, room: int | str) -> int:
        """Resolve a room given by number or by name (as shown on the map)."""
        if isinstance(room, int) or str(room).isdigit():
            return int(room)
        wanted = slugify(str(room))
        for r in self._rooms.rooms if self._rooms else []:
            if slugify(r.name) == wanted:
                return r.id
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_room",
            translation_placeholders={"room": str(room)},
        )

    def _area_capability(self) -> Any:
        area = self._capability.clean.action.area
        if area is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="area_not_supported"
            )
        return area

    async def async_clean_rooms(self, rooms: list[int | str], cleanings: int = 1) -> None:
        """Action yeedi.clean_rooms: clean rooms by number or name, in the given order."""
        area = self._area_capability()
        ids = ",".join(str(self._room_id(r)) for r in rooms)
        await self._device.execute_command(area(CleanMode.SPOT_AREA, ids, cleanings))

    async def async_clean_zone(self, zone: list[float], cleanings: int = 1) -> None:
        """Action yeedi.clean_zone: clean a rectangle given in metres [x1, y1, x2, y2]."""
        area = self._area_capability()
        x1, y1, x2, y2 = zone
        # The robot wants millimetres, min corner first. It cleans a zone in ~30 cm
        # strips and does a thin rectangle in one straight line: like the yeedi app,
        # widen each side to at least 1 m, around the rectangle given.
        min_x, max_x = _min_side(x1, x2, MIN_ZONE_SIDE_M)
        min_y, max_y = _min_side(y1, y2, MIN_ZONE_SIDE_M)
        coords = ",".join(str(round(v * 1000)) for v in (min_x, min_y, max_x, max_y))
        await self._device.execute_command(area(CleanMode.CUSTOM_AREA, coords, cleanings))

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
        # segment id = "<map id>_<room id>"; the room id is a number.
        room_ids = []
        for cid in segment_ids:
            _, sep, room_id = str(cid).rpartition(_SEGMENTS_SEPARATOR)
            if sep and room_id.isdigit():
                room_ids.append(room_id)
        if not room_ids:
            _LOGGER.warning("No valid room to clean in %s", segment_ids)
            return
        if TYPE_CHECKING:
            assert self._capability.clean.action.area is not None
        await self._device.execute_command(
            self._capability.clean.action.area(CleanMode.SPOT_AREA, ",".join(room_ids), 1)
        )
