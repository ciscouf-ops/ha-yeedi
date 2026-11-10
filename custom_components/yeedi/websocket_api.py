"""WebSocket command used by the yeedi map card."""

from __future__ import annotations

from typing import Any

try:
    import probatio as vol
except ImportError:  # Home Assistant before probatio
    import voluptuous as vol  # type: ignore[no-redef]

from homeassistant.components import websocket_api
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    entity_registry as er,
)

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


def _area_names(hass: HomeAssistant, entity_id: str) -> dict[str, str]:
    """Return {room id: HA area name} from the vacuum's segment-to-area mapping.

    Home Assistant lets the user associate the robot's segments with the areas of the
    home (entity settings of the vacuum). The card shows those area names, so the
    rooms are named once, in one place.
    """
    entry = er.async_get(hass).async_get(entity_id)
    if entry is None:
        return {}
    mapping = (entry.options.get("vacuum") or {}).get("area_mapping") or {}
    areas = ar.async_get(hass)
    out: dict[str, str] = {}
    for area_id, segment_ids in mapping.items():
        area = areas.async_get_area(area_id)
        if area is None:
            continue
        for segment_id in segment_ids:
            # segment id = "<map id>_<room id>"
            out[str(segment_id).rpartition("_")[2]] = area.name
    return out


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

    entity_id = msg["entity_id"]

    @callback
    def send() -> None:
        data = map_data.as_dict()
        area_names = _area_names(hass, entity_id)
        for room in data["rooms"]:
            room["area_name"] = area_names.get(str(room["id"]))
        connection.send_message(websocket_api.event_message(msg["id"], data))

    @callback
    def on_registry_update(event: Event) -> None:
        if event.data.get("entity_id") == entity_id:
            send()

    remove_listener = map_data.async_add_listener(send)
    remove_registry = hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED, on_registry_update
    )

    @callback
    def unsubscribe() -> None:
        remove_listener()
        remove_registry()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send()
