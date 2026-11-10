"""Select entities for Yeedi robots: water level."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import CapabilitySetTypes
from deebot_client.device import Device
from deebot_client.events import Event
from deebot_client.events.water_info import WaterAmountEvent

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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


def _name_key(value: Any) -> str:
    return str(value.name).lower()


ENTITY_DESCRIPTIONS: tuple[YeediSelectEntityDescription, ...] = (
    YeediSelectEntityDescription[WaterAmountEvent](
        key="water_amount",
        translation_key="water_amount",
        capability_fn=lambda caps: caps.water.amount if caps.water else None,
        current_option_fn=lambda e: _name_key(e.value),
        options_fn=lambda cap: [_name_key(t) for t in cap.types],
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
    entities: list[YeediEntity] = get_supported_entities(
        controller.devices, YeediSelect, ENTITY_DESCRIPTIONS
    )
    entities.extend(
        YeediSuctionSelect(device, controller.suction[device.device_info["did"]])
        for device in controller.devices
        if controller.suction[device.device_info["did"]].supported
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
            self._attr_current_option = self.entity_description.current_option_fn(event)
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_select_option(self, option: str) -> None:
        """Change the setting."""
        await self._device.execute_command(self._capability.set(option))


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
