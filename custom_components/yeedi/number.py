"""Number entities for Yeedi robots: voice volume, water flow on recent models."""

from __future__ import annotations

from dataclasses import dataclass

from deebot_client.capabilities import CapabilityNumber, CapabilitySet
from deebot_client.events import VolumeEvent
from deebot_client.events.water_info import WaterCustomAmountEvent

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controller import YeediConfigEntry
from .entity import (
    YeediCapabilityEntityDescription,
    YeediDescriptionEntity,
    get_supported_entities,
)


@dataclass(kw_only=True, frozen=True)
class YeediNumberEntityDescription(
    YeediCapabilityEntityDescription, NumberEntityDescription
):
    """Number bound to a setting."""


ENTITY_DESCRIPTIONS: tuple[YeediNumberEntityDescription, ...] = (
    YeediNumberEntityDescription(
        key="volume",
        translation_key="volume",
        capability_fn=lambda caps: caps.settings.volume,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
)

# Recent models (M16 Infinity) set the water flow with a number; the others use the
# "water_amount" select.
WATER_DESCRIPTIONS: tuple[YeediNumberEntityDescription, ...] = (
    YeediNumberEntityDescription(
        key="water_amount",
        translation_key="water_amount",
        capability_fn=lambda caps: (
            caps.water.amount
            if caps.water and isinstance(caps.water.amount, CapabilityNumber)
            else None
        ),
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers."""
    devices = entry.runtime_data.devices
    async_add_entities(
        [
            *get_supported_entities(devices, YeediVolume, ENTITY_DESCRIPTIONS),
            *get_supported_entities(devices, YeediWaterAmount, WATER_DESCRIPTIONS),
        ]
    )


class YeediVolume(YeediDescriptionEntity[CapabilitySet], NumberEntity):
    """The voice volume of the robot."""

    entity_description: YeediNumberEntityDescription

    async def async_added_to_hass(self) -> None:
        """Follow the volume."""
        await super().async_added_to_hass()

        async def on_event(event: VolumeEvent) -> None:
            self._attr_native_value = event.volume
            if event.maximum:
                self._attr_native_max_value = event.maximum
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_set_native_value(self, value: float) -> None:
        """Change the volume."""
        await self._device.execute_command(self._capability.set(int(value)))


class YeediWaterAmount(YeediDescriptionEntity[CapabilityNumber], NumberEntity):
    """The water flow of the mop, as a number (recent models)."""

    entity_description: YeediNumberEntityDescription

    def __init__(self, *args, **kwargs) -> None:
        """Take the range from the robot sheet."""
        super().__init__(*args, **kwargs)
        self._attr_native_min_value = self._capability.min
        self._attr_native_max_value = self._capability.max

    async def async_added_to_hass(self) -> None:
        """Follow the water flow."""
        await super().async_added_to_hass()

        async def on_event(event: WaterCustomAmountEvent) -> None:
            self._attr_native_value = event.value
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_set_native_value(self, value: float) -> None:
        """Change the water flow."""
        await self._device.execute_command(self._capability.set(int(value)))
