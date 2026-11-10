"""Number entities for Yeedi robots: voice volume."""

from __future__ import annotations

from dataclasses import dataclass

from deebot_client.capabilities import CapabilitySet
from deebot_client.events import VolumeEvent

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers."""
    async_add_entities(
        get_supported_entities(entry.runtime_data.devices, YeediVolume, ENTITY_DESCRIPTIONS)
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
