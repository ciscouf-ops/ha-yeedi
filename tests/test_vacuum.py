"""Tests for the vacuum entity: rooms as segments, room cleaning commands."""

from __future__ import annotations

from unittest.mock import MagicMock

from deebot_client.capabilities import DeviceType
from deebot_client.events import RoomsEvent
from deebot_client.models import CleanMode, Room
from homeassistant.exceptions import ServiceValidationError
import pytest

from custom_components.yeedi.suction import YeediSuction
from custom_components.yeedi.vacuum import YeediVacuum

from .conftest import FakeDevice


def _vacuum():
    caps = MagicMock()
    caps.device_type = DeviceType.VACUUM
    caps.fan_speed = None
    caps.water = None
    caps.clean.action.area = lambda mode, value, cleanings: ("area", mode, value, cleanings)
    caps.custom.set = lambda name, args: ("custom", name, args)
    device = FakeDevice(capabilities=caps)
    vac = YeediVacuum(device, YeediSuction(device))
    vac.hass = MagicMock()
    vac.async_write_ha_state = lambda: None
    return device, vac


async def test_segments_and_rooms_attribute() -> None:
    device, vac = _vacuum()
    vac._rooms = RoomsEvent("m1", [Room("Living Room", 2, ""), Room("Default", 1, ""), Room("Default", 5, "")])
    segments = await vac.async_get_segments()
    assert [(s.id, s.name) for s in segments] == [("m1_2", "Living Room"), ("m1_1", "Default"), ("m1_5", "Default")]
    assert vac.extra_state_attributes["rooms"] == {"living_room": 2, "default": [1, 5]}


async def test_clean_segments_keeps_order() -> None:
    device, vac = _vacuum()
    await vac.async_clean_segments(["m1_3", "m1_1", "m1_2"])
    assert device.commands[-1] == ("area", CleanMode.SPOT_AREA, "3,1,2", 1)
    await vac.async_clean_segments(["bad"])  # nothing valid: no command sent
    assert len(device.commands) == 1


async def test_send_command_spot_and_custom_area() -> None:
    device, vac = _vacuum()
    await vac.async_send_command("spot_area", {"rooms": [2, 1], "cleanings": 2})
    assert device.commands[-1] == ("area", CleanMode.SPOT_AREA, "2,1", 2)
    await vac.async_send_command("custom_area", {"coordinates": "0,0,1000,1000"})
    assert device.commands[-1] == ("area", CleanMode.CUSTOM_AREA, "0,0,1000,1000", 1)
    await vac.async_send_command("setMopMute", {"enable": 1})
    assert device.commands[-1] == ("custom", "setMopMute", {"enable": 1})
    with pytest.raises(ServiceValidationError):
        await vac.async_send_command("spot_area", {})
    with pytest.raises(ServiceValidationError):
        await vac.async_send_command("spot_area", [1, 2])


async def test_clean_rooms_by_name_and_number() -> None:
    device, vac = _vacuum()
    vac._rooms = RoomsEvent("m1", [Room("Cuisine", 2, ""), Room("Salon", 4, "")])
    await vac.async_clean_rooms(["Cuisine", 4, "salon"], cleanings=2)
    assert device.commands == [("area", CleanMode.SPOT_AREA, "2,4,4", 2)]


async def test_clean_rooms_unknown_name() -> None:
    device, vac = _vacuum()
    vac._rooms = RoomsEvent("m1", [Room("Cuisine", 2, "")])
    with pytest.raises(ServiceValidationError):
        await vac.async_clean_rooms(["Garage"])
    assert device.commands == []


async def test_clean_zone_metres_to_millimetres_sorted() -> None:
    device, vac = _vacuum()
    await vac.async_clean_zone([1.0, 2.4, -1.5, 0.2])
    assert device.commands == [("area", CleanMode.CUSTOM_AREA, "-1500,200,1000,2400", 1)]


async def test_clean_zone_thin_rectangle_widened_to_one_metre() -> None:
    device, vac = _vacuum()
    # 20 cm wide, 3 m long: widened to 1 m around its middle (x = 0.1).
    await vac.async_clean_zone([0.0, 0.0, 0.2, 3.0])
    assert device.commands == [("area", CleanMode.CUSTOM_AREA, "-400,0,600,3000", 1)]
