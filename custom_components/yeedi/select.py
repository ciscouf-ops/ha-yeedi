"""Select entities for Yeedi robots: water level, suction power, auto-empty frequency."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import CapabilitySetTypes
from deebot_client.device import Device
from deebot_client.events import Event
from deebot_client.events.auto_empty import AutoEmptyEvent, Frequency
from deebot_client.events.map import CachedMapInfoEvent
from deebot_client.events.water_info import WaterAmountEvent
from deebot_client.events.work_mode import WorkMode, WorkModeEvent

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .commands import UseMap
from .const import CONF_STATION
from .controller import YeediConfigEntry
from .entity import (
    YeediCapabilityEntityDescription,
    YeediDescriptionEntity,
    YeediEntity,
    get_supported_entities,
)
from .suction import YeediSuction


@dataclass(kw_only=True, frozen=True)
class YeediSelectEntityDescription[EventT: Event](
    YeediCapabilityEntityDescription, SelectEntityDescription
):
    """Select description."""

    current_option_fn: Callable[[EventT], str | None]
    options_fn: Callable[[CapabilitySetTypes], list[str]]
    # How an option becomes the arguments of the set command (default: the option itself).
    set_args_fn: Callable[[str], tuple] = lambda option: (option,)


def _name_key(value: Any) -> str:
    return str(value.name).lower()


ENTITY_DESCRIPTIONS: tuple[YeediSelectEntityDescription, ...] = (
    # Recent models: vacuum, mop, both at once, or mop after vacuuming.
    YeediSelectEntityDescription[WorkModeEvent](
        key="work_mode",
        translation_key="work_mode",
        capability_fn=lambda caps: caps.clean.work_mode,
        current_option_fn=lambda e: _name_key(e.mode),
        options_fn=lambda cap: [_name_key(t) for t in cap.types],
        set_args_fn=lambda option: (WorkMode[option.upper()],),
        entity_category=EntityCategory.CONFIG,
    ),
    YeediSelectEntityDescription[WaterAmountEvent](
        key="water_amount",
        translation_key="water_amount",
        # Recent models (M16 Infinity) set the water flow with a number instead: see number.py.
        capability_fn=lambda caps: (
            caps.water.amount
            if caps.water and isinstance(caps.water.amount, CapabilitySetTypes)
            else None
        ),
        current_option_fn=lambda e: _name_key(e.value),
        options_fn=lambda cap: [_name_key(t) for t in cap.types],
        entity_category=EntityCategory.CONFIG,
    ),
    # Auto-empty: "off", or one of the frequencies the station offers.
    YeediSelectEntityDescription[AutoEmptyEvent](
        key="auto_empty",
        translation_key="auto_empty",
        capability_fn=lambda caps: caps.station.auto_empty if caps.station else None,
        # Stations without frequencies (yeedi vac station) are only "off" or "on".
        current_option_fn=lambda e: (
            "off" if not e.enabled else _name_key(e.frequency) if e.frequency else "on"
        ),
        options_fn=lambda cap: ["off", *(_name_key(t) for t in cap.types)] if cap.types else ["off", "on"],
        set_args_fn=lambda option: (
            (False, None) if option == "off" else (True, None) if option == "on" else (True, Frequency[option.upper()])
        ),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the selects."""
    controller = entry.runtime_data
    # Auto-empty belongs to the station, optional on several models.
    descriptions = tuple(
        d
        for d in ENTITY_DESCRIPTIONS
        if d.key != "auto_empty" or entry.options.get(CONF_STATION, False)
    )
    entities: list[YeediEntity] = get_supported_entities(
        controller.devices, YeediSelect, descriptions
    )
    entities.extend(
        YeediSuctionSelect(device, controller.suction[device.device_info["did"]])
        for device in controller.devices
        if controller.suction[device.device_info["did"]].supported
    )
    # Robots that can keep several maps (floors): which one is active.
    entities.extend(
        YeediMapSelect(device, device.capabilities.map)
        for device in controller.devices
        if device.capabilities.map and device.capabilities.map.multi_state
    )
    async_add_entities(entities)


class YeediSelect(YeediDescriptionEntity[CapabilitySetTypes], SelectEntity):
    """A select bound to a robot setting."""

    entity_description: YeediSelectEntityDescription

    def __init__(
        self,
        device: Device,
        capability: CapabilitySetTypes,
        entity_description: YeediSelectEntityDescription,
        **kwargs: Any,
    ) -> None:
        """Initialize the select."""
        super().__init__(device, capability, entity_description, **kwargs)
        self._attr_options = entity_description.options_fn(capability)

    async def async_added_to_hass(self) -> None:
        """Subscribe to the event."""
        await super().async_added_to_hass()

        async def on_event(event: Event) -> None:
            # A station that reports auto-empty on without a frequency has none (seen on
            # the yeedi vac station): offer only off / on.
            if (
                isinstance(event, AutoEmptyEvent)
                and event.enabled
                and event.frequency is None
                and self._attr_options != ["off", "on"]
            ):
                self._attr_options = ["off", "on"]
            self._attr_current_option = self.entity_description.current_option_fn(event)
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_select_option(self, option: str) -> None:
        """Change the setting."""
        await self._device.execute_command(
            self._capability.set(*self.entity_description.set_args_fn(option))
        )
        # setAutoEmpty is not linked to its get command: ask the robot again.
        if self.entity_description.key == "auto_empty":
            self._device.events.request_refresh(self._capability.event)


class YeediSuctionSelect(YeediEntity[YeediSuction], SelectEntity, RestoreEntity):
    """Suction power: the fan speed of the vacuum entity, plus mop only."""

    entity_description = SelectEntityDescription(
        key="suction",
        translation_key="suction",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, device: Device, suction: YeediSuction) -> None:
        """Initialize the select."""
        super().__init__(device, suction)
        self._attr_options = suction.options

    async def async_added_to_hass(self) -> None:
        """Restore the mop-only setting and follow the robot."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._capability.restore(last.state)

        @callback
        def on_change() -> None:
            self._attr_current_option = self._capability.current
            self.async_write_ha_state()

        self.async_on_remove(self._capability.add_listener(on_change))
        self._attr_current_option = self._capability.current

    async def async_select_option(self, option: str) -> None:
        """Change the suction power."""
        await self._capability.async_set(option)


class YeediMapSelect(YeediEntity, SelectEntity):
    """The active map, for robots that keep one map per floor."""

    entity_description = SelectEntityDescription(
        key="active_map",
        translation_key="active_map",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, device: Device, capability: Any) -> None:
        """Initialize the select."""
        super().__init__(device, capability)
        self._maps: dict[str, str] = {}  # name -> map id
        self._attr_options = []

    async def async_added_to_hass(self) -> None:
        """Follow the saved maps."""
        await super().async_added_to_hass()

        async def on_event(event: CachedMapInfoEvent) -> None:
            maps = sorted(event.maps, key=lambda m: str(m.id))
            names: dict[str, str] = {}
            for i, m in enumerate(maps, start=1):
                name = (m.name or "").strip() or f"#{i}"
                names[name if name not in names else f"{name} ({m.id})"] = str(m.id)
            self._maps = names
            self._attr_options = list(names)
            self._attr_current_option = next(
                (n for n, i in names.items() if any(m.using and str(m.id) == i for m in maps)), None
            )
            self.async_write_ha_state()

        self._subscribe(self._capability.cached_info.event, on_event)

    @property
    def available(self) -> bool:
        """Only once the robot listed its maps."""
        return super().available and bool(self._maps)

    async def async_select_option(self, option: str) -> None:
        """Make this map the active one, then read the maps again."""
        if (map_id := self._maps.get(option)) is None:
            return
        await self._device.execute_command(UseMap(map_id))
        self._device.events.request_refresh(CachedMapInfoEvent)
