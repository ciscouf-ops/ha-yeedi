"""Yeedi robot vacuums in Home Assistant, through the Yeedi cloud."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN
from .controller import YeediConfigEntry, YeediController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.VACUUM]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_CARD_FILE = Path(__file__).parent / "www" / "yeedi-map-card.js"
_CARD_URL = "/yeedi_static/yeedi-map-card.js"


def _read_version() -> str:
    manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
    return manifest.get("version", "0")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the map card and register its WebSocket command."""
    websocket_api.async_register(hass)
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL, str(_CARD_FILE), True)]
        )
        version = await hass.async_add_executor_job(_read_version)
        # The version in the URL makes browsers load the new card after an update.
        add_extra_js_url(hass, f"{_CARD_URL}?v={version}")
    except Exception:  # never block the integration because of the card
        _LOGGER.exception("Could not register the yeedi map card")
    return True


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
