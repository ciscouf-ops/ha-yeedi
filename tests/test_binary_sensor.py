"""Water tank sensors of a mop-washing station, read from the robot errors."""

from __future__ import annotations

from deebot_client import hardware as dc_hardware
from deebot_client.events import ErrorEvent

from custom_components.yeedi import binary_sensor
from custom_components.yeedi.entity import get_supported_entities
from custom_components.yeedi.hardware import register_yeedi_models

from .conftest import FakeDevice
from .test_platforms import _ready


def _sensors(model: str) -> dict:
    register_yeedi_models()
    device = FakeDevice(capabilities=dc_hardware._DEVICES[model].capabilities)  # noqa: SLF001
    entities = get_supported_entities(
        [device], binary_sensor.YeediErrorBinarySensor, binary_sensor.ENTITY_DESCRIPTIONS
    )
    return device, {e.entity_description.key: e for e in entities}


def test_only_for_mop_washing_stations() -> None:
    assert _sensors("04z443")[1] == {}  # vac max: auto-empty station, no water tanks
    assert set(_sensors("4e64gs")[1]) == {"clean_water_empty", "dirty_water_full"}


async def test_follow_the_errors() -> None:
    device, sensors = _sensors("4e64gs")
    clean, dirty = sensors["clean_water_empty"], sensors["dirty_water_full"]
    for sensor in (clean, dirty):
        _ready(sensor)
        await sensor.async_added_to_hass()

    await device.events.emit(ErrorEvent(0, "NoError: Robot is operational"))
    assert (clean.is_on, dirty.is_on) == (False, False)
    await device.events.emit(ErrorEvent(301, "FreshWaterBox empty"))
    assert (clean.is_on, dirty.is_on) == (True, False)
    await device.events.emit(ErrorEvent(318, "Dirty Water Tank is full"))
    # Only the last error is reported: the clean tank is not refilled for all that.
    assert (clean.is_on, dirty.is_on) == (True, True)
    await device.events.emit(ErrorEvent(0, "NoError: Robot is operational"))
    assert (clean.is_on, dirty.is_on) == (False, False)
