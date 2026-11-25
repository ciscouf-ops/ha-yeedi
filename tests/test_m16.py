"""The M16 Infinity reuses a deebot-client sheet: every platform must cope with it."""

from __future__ import annotations

from deebot_client import hardware as dc_hardware

from custom_components.yeedi import button, number, select, sensor, switch
from custom_components.yeedi.entity import get_supported_entities
from custom_components.yeedi.hardware import register_yeedi_models
from custom_components.yeedi.suction import YeediSuction
from custom_components.yeedi.vacuum import YeediVacuum

from .conftest import FakeDevice


def test_m16_infinity_entities() -> None:
    register_yeedi_models()
    device = FakeDevice(capabilities=dc_hardware._DEVICES["4e64gs"].capabilities)  # noqa: SLF001
    devices = [device]
    entities = [
        *get_supported_entities(devices, button.YeediButton, button.ENTITY_DESCRIPTIONS),
        *get_supported_entities(
            devices, button.YeediStationButton, button.STATION_DESCRIPTIONS
        ),
        *get_supported_entities(
            devices, button.YeediLifeSpanButton, button.LIFESPAN_DESCRIPTIONS
        ),
        *get_supported_entities(devices, number.YeediVolume, number.ENTITY_DESCRIPTIONS),
        *get_supported_entities(
            devices, number.YeediWaterAmount, number.WATER_DESCRIPTIONS
        ),
        *get_supported_entities(devices, select.YeediSelect, select.ENTITY_DESCRIPTIONS),
        *get_supported_entities(devices, switch.YeediSwitch, switch.ENTITY_DESCRIPTIONS),
        *get_supported_entities(devices, sensor.YeediSensor, sensor.ENTITY_DESCRIPTIONS),
        *(
            sensor.YeediLifespanSensor(device, device.capabilities.life_span, d)
            for d in sensor.LIFESPAN_ENTITY_DESCRIPTIONS
            if d.component in device.capabilities.life_span.types
        ),
    ]
    suction = YeediSuction(device)
    assert suction.supported
    assert suction.options[0] == "mop_only"
    assert YeediVacuum(device, suction, None).supported_features
    keys = {e.entity_description.key for e in entities}
    assert {"auto_empty", "volume", "water_amount"} <= keys
    (water,) = [e for e in entities if isinstance(e, number.YeediWaterAmount)]
    assert (water.native_min_value, water.native_max_value) == (0, 50)
    # The older models keep the water select, and get no water number.
    old = FakeDevice(capabilities=dc_hardware._DEVICES["04z443"].capabilities)  # noqa: SLF001
    assert not get_supported_entities([old], number.YeediWaterAmount, number.WATER_DESCRIPTIONS)
    assert any(
        e.entity_description.key == "water_amount"
        for e in get_supported_entities([old], select.YeediSelect, select.ENTITY_DESCRIPTIONS)
    )
