"""Diagnostics for the yeedi integration (Settings → Devices → ⋮ → Download diagnostics)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_ACCOUNT_CREDENTIALS
from .controller import YeediConfigEntry

# Account and robot identifiers are personal: never in a file people attach to issues.
TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCOUNT_CREDENTIALS,
    "device_id",
    "did",
    "name",  # robot serial number
    "resource",
    "token",
    "user_id",
    "uid",
    "mac",
    "ip",
    "ssid",
    "homeId",
}


def _device_dump(device: Any, controller: Any) -> dict[str, Any]:
    info = dict(device.device_info)
    did = info.get("did")
    caps = device.capabilities
    map_data = controller.map_data.get(did)
    suction = controller.suction.get(did)
    return {
        "info": {k: info.get(k) for k in ("class", "deviceName", "nick", "model", "company", "did", "name")},
        "capabilities": {
            "device_type": str(getattr(caps, "device_type", None)),
            "fan_speed": [str(t) for t in caps.fan_speed.types] if caps.fan_speed else None,
            "water": [str(t) for t in caps.water.amount.types] if caps.water else None,
            "map": caps.map is not None,
            "clean_area": bool(caps.clean.action.area) if caps.clean else False,
        },
        "firmware": device.fw_version,
        "suction": {"current": suction.current, "options": suction.options} if suction else None,
        "map": _map_dump(map_data.as_dict()) if map_data else None,
    }


def _map_dump(data: dict[str, Any]) -> dict[str, Any]:
    """Keep the shape of the map data without the coordinates themselves."""
    return {
        "map_id": data.get("map_id"),
        "state": data.get("state"),
        "rooms": [
            {"id": r["id"], "name": r.get("name"), "outline_points": len(r.get("outline") or [])}
            for r in data.get("rooms", [])
        ],
        "has_robot_position": data.get("robot") is not None,
        "has_dock_position": data.get("dock") is not None,
        "trace_points": len(data.get("trace") or []),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: YeediConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "robots": async_redact_data(
            [_device_dump(d, controller) for d in controller.devices], TO_REDACT
        ),
    }
