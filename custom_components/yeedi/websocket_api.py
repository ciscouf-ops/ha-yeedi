"""WebSocket command used by the yeedi map card."""

from __future__ import annotations

from typing import Any

try:
    import probatio as vol
except ImportError:  # Home Assistant before probatio
    import voluptuous as vol  # type: ignore[no-redef]

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN
from .map_data import YeediMapData


def _find_map_data(hass: HomeAssistant, entity_id: str) -> YeediMapData | None:
    """Return the map data of the robot behind a yeedi vacuum entity."""
    entry = er.async_get(hass).async_get(entity_id)
    if entry is None or entry.platform != DOMAIN or entry.config_entry_id is None:
        return None
    config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
    controller = getattr(config_entry, "runtime_data", None) if config_entry else None
    if controller is None:
        return None
    for did, map_data in controller.map_data.items():
        if entry.unique_id.startswith(f"{did}_"):
            return map_data
    return None


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the commands."""
    websocket_api.async_register_command(hass, ws_subscribe_map)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "yeedi/map/subscribe",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def ws_subscribe_map(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the map data now and every time it changes."""
    map_data = _find_map_data(hass, msg["entity_id"])
    if map_data is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Not a yeedi vacuum"
        )
        return

    @callback
    def send() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], map_data.as_dict())
        )

    connection.subscriptions[msg["id"]] = map_data.async_add_listener(send)
    connection.send_result(msg["id"])
    send()
