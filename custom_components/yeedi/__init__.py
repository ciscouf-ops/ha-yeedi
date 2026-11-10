"""Yeedi robot vacuums in Home Assistant, through the Yeedi cloud."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import YeediConfigEntry, YeediController

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.VACUUM]


async def async_setup_entry(hass: HomeAssistant, entry: YeediConfigEntry) -> bool:
    """Set up a Yeedi account."""
    controller = YeediController(hass, entry)
    entry.async_on_unload(controller.teardown)
    await controller.initialize()
    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: YeediConfigEntry) -> bool:
    """Unload a Yeedi account."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
