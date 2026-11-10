"""Switches for Yeedi robots: continuous cleaning, carpet boost, advanced mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import CapabilitySetEnable
from deebot_client.events import EnableEvent

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
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
class YeediSwitchEntityDescription(
    YeediCapabilityEntityDescription, SwitchEntityDescription
):
    """Switch bound to an enable/disable setting."""


ENTITY_DESCRIPTIONS: tuple[YeediSwitchEntityDescription, ...] = (
    YeediSwitchEntityDescription(
        key="continuous_cleaning",
        translation_key="continuous_cleaning",
        capability_fn=lambda caps: caps.clean.continuous,
        entity_category=EntityCategory.CONFIG,
    ),
    YeediSwitchEntityDescription(
        key="carpet_auto_fan_boost",
        translation_key="carpet_auto_fan_boost",
        capability_fn=lambda caps: caps.settings.carpet_auto_fan_boost,
        entity_category=EntityCategory.CONFIG,
    ),
    YeediSwitchEntityDescription(
        key="advanced_mode",
        translation_key="advanced_mode",
        capability_fn=lambda caps: caps.settings.advanced_mode,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches."""
    async_add_entities(
        get_supported_entities(entry.runtime_data.devices, YeediSwitch, ENTITY_DESCRIPTIONS)
    )


class YeediSwitch(YeediDescriptionEntity[CapabilitySetEnable], SwitchEntity):
    """A robot setting that is on or off."""

    entity_description: YeediSwitchEntityDescription

    async def async_added_to_hass(self) -> None:
        """Follow the setting."""
        await super().async_added_to_hass()

        async def on_event(event: EnableEvent) -> None:
            self._attr_is_on = event.enabled
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        await self._device.execute_command(self._capability.set(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        await self._device.execute_command(self._capability.set(False))
