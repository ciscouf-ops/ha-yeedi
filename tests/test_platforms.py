"""Buttons, switches, number and selects built from capabilities."""

from __future__ import annotations

from unittest.mock import MagicMock

from deebot_client.commands import StationAction
from deebot_client.events import LifeSpan, VolumeEvent
from deebot_client.events.auto_empty import AutoEmptyEvent, Frequency

from custom_components.yeedi import button, number, select, switch
from custom_components.yeedi.entity import get_supported_entities

from .conftest import FakeDevice


def _caps():
    caps = MagicMock()
    caps.station.action.types = (StationAction.EMPTY_DUSTBIN,)
    caps.station.action.execute = lambda action: ("station", action)
    caps.station.auto_empty.types = (Frequency.AUTO, Frequency.SMART)
    caps.station.auto_empty.event = AutoEmptyEvent
    caps.station.auto_empty.set = lambda enable, freq: ("auto_empty", enable, freq)
    caps.life_span.types = (LifeSpan.BRUSH, LifeSpan.FILTER)
    caps.life_span.reset = lambda c: ("reset", c)
    caps.map.relocation.execute = lambda: ("relocate",)
    caps.settings.volume.set = lambda v: ("volume", v)
    caps.settings.volume.event = VolumeEvent
    caps.clean.continuous.set = lambda on: ("continuous", on)
    return caps


def _ready(entity):
    entity.hass = MagicMock()
    entity.async_write_ha_state = lambda: None
    return entity


async def test_buttons() -> None:
    device = FakeDevice(capabilities=_caps())
    entities = get_supported_entities(
        [device], button.YeediStationButton, button.STATION_DESCRIPTIONS
    ) + get_supported_entities([device], button.YeediLifeSpanButton, button.LIFESPAN_DESCRIPTIONS)
    keys = [e.entity_description.key for e in entities]
    assert keys == ["station_empty_dustbin", "reset_lifespan_brush", "reset_lifespan_filter"]
    for e in entities:
        await e.async_press()
    assert device.commands == [
        ("station", StationAction.EMPTY_DUSTBIN),
        ("reset", LifeSpan.BRUSH),
        ("reset", LifeSpan.FILTER),
    ]


async def test_auto_empty_select() -> None:
    device = FakeDevice(capabilities=_caps())
    (sel,) = [
        e
        for e in get_supported_entities([device], select.YeediSelect, select.ENTITY_DESCRIPTIONS)
        if e.entity_description.key == "auto_empty"
    ]
    _ready(sel)
    assert sel.options == ["off", "auto", "smart"]
    await sel.async_added_to_hass()
    await device.events.emit(AutoEmptyEvent(True, Frequency.SMART))
    assert sel.current_option == "smart"
    await device.events.emit(AutoEmptyEvent(False, Frequency.SMART))
    assert sel.current_option == "off"
    await sel.async_select_option("off")
    await sel.async_select_option("auto")
    assert device.commands == [("auto_empty", False, None), ("auto_empty", True, Frequency.AUTO)]



async def test_auto_empty_select_without_frequencies() -> None:
    caps = _caps()
    caps.station.auto_empty.types = ()
    device = FakeDevice(capabilities=caps)
    (sel,) = [
        e
        for e in get_supported_entities([device], select.YeediSelect, select.ENTITY_DESCRIPTIONS)
        if e.entity_description.key == "auto_empty"
    ]
    _ready(sel)
    assert sel.options == ["off", "on"]
    await sel.async_added_to_hass()
    await device.events.emit(AutoEmptyEvent(True, None))
    assert sel.current_option == "on"
    await device.events.emit(AutoEmptyEvent(False, None))
    assert sel.current_option == "off"
    await sel.async_select_option("on")
    await sel.async_select_option("off")
    assert device.commands == [("auto_empty", True, None), ("auto_empty", False, None)]
    assert device.events.refreshed == [AutoEmptyEvent, AutoEmptyEvent]

async def test_switch_and_volume() -> None:
    device = FakeDevice(capabilities=_caps())
    (sw,) = [
        e
        for e in get_supported_entities([device], switch.YeediSwitch, switch.ENTITY_DESCRIPTIONS)
        if e.entity_description.key == "continuous_cleaning"
    ]
    await sw.async_turn_on()
    await sw.async_turn_off()
    (vol,) = get_supported_entities([device], number.YeediVolume, number.ENTITY_DESCRIPTIONS)
    _ready(vol)
    await vol.async_added_to_hass()
    await device.events.emit(VolumeEvent(volume=7, maximum=10))
    assert vol.native_value == 7 and vol.native_max_value == 10
    await vol.async_set_native_value(3.0)
    assert device.commands == [("continuous", True), ("continuous", False), ("volume", 3)]
