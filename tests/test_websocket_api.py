"""Tests for the room → Home Assistant area names sent to the card."""

from __future__ import annotations

from homeassistant.helpers import area_registry as ar, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yeedi.const import DOMAIN
from custom_components.yeedi.websocket_api import _area_names, _find_map_data


async def test_area_names(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    areas = ar.async_get(hass)
    corridor = areas.async_create("Couloir")
    registry = er.async_get(hass)
    reg_entry = registry.async_get_or_create("vacuum", DOMAIN, "did123_vacuum", config_entry=entry)
    registry.async_update_entity_options(
        reg_entry.entity_id, "vacuum", {"area_mapping": {corridor.id: ["m1_1"], "ghost": ["m1_2"]}}
    )
    assert _area_names(hass, reg_entry.entity_id) == {"1": "Couloir"}
    assert _area_names(hass, "vacuum.unknown") == {}


async def test_find_map_data_needs_a_yeedi_entity(hass) -> None:
    registry = er.async_get(hass)
    other = registry.async_get_or_create("vacuum", "other", "x")
    assert _find_map_data(hass, other.entity_id) is None
    assert _find_map_data(hass, "vacuum.nope") is None
