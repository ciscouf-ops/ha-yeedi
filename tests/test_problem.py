"""The "Problem" sensor: robot error codes in words."""

from __future__ import annotations

import json
from pathlib import Path

from deebot_client import hardware as dc_hardware
from deebot_client.events import ErrorEvent

from custom_components.yeedi import sensor
from custom_components.yeedi.const import PROBLEM_CODES, PROBLEM_OPTIONS
from custom_components.yeedi.entity import get_supported_entities
from custom_components.yeedi.hardware import register_yeedi_models

from .conftest import FakeDevice
from .test_platforms import _ready

ROOT = Path(__file__).parents[1] / "custom_components" / "yeedi"


async def test_problem_in_words() -> None:
    register_yeedi_models()
    device = FakeDevice(capabilities=dc_hardware._DEVICES["04z443"].capabilities)  # noqa: SLF001
    (problem,) = [
        e
        for e in get_supported_entities([device], sensor.YeediSensor, sensor.ENTITY_DESCRIPTIONS)
        if e.entity_description.key == "problem"
    ]
    _ready(problem)
    await problem.async_added_to_hass()
    await device.events.emit(ErrorEvent(105, "Stuck: Robot is stuck"))
    assert problem.native_value == "stuck"
    assert problem.extra_state_attributes["code"] == 105
    await device.events.emit(ErrorEvent(4242, None))
    assert problem.native_value == "other"
    await device.events.emit(ErrorEvent(0, "NoError: Robot is operational"))
    assert problem.native_value == "none"


def test_every_state_is_translated() -> None:
    assert set(PROBLEM_CODES.values()) <= set(PROBLEM_OPTIONS)
    for path in [ROOT / "strings.json", *sorted((ROOT / "translations").glob("*.json"))]:
        states = json.loads(path.read_text())["entity"]["sensor"]["problem"]["state"]
        assert set(states) == set(PROBLEM_OPTIONS), path.name


async def test_m16_settings() -> None:
    """Cleaning mode, passes and mop wash interval of the M16 Infinity."""
    from deebot_client.events import CleanCountEvent
    from deebot_client.events.mop_auto_wash_frequency import MopAutoWashFrequencyEvent
    from deebot_client.events.work_mode import WorkMode, WorkModeEvent

    from custom_components.yeedi import number, select, switch

    register_yeedi_models()
    device = FakeDevice(capabilities=dc_hardware._DEVICES["4e64gs"].capabilities)  # noqa: SLF001
    (mode,) = [
        e
        for e in get_supported_entities([device], select.YeediSelect, select.ENTITY_DESCRIPTIONS)
        if e.entity_description.key == "work_mode"
    ]
    _ready(mode)
    await mode.async_added_to_hass()
    assert set(mode.options) == {"mop", "mop_after_vacuum", "vacuum", "vacuum_and_mop"}
    await device.events.emit(WorkModeEvent(WorkMode.MOP_AFTER_VACUUM))
    assert mode.current_option == "mop_after_vacuum"
    await mode.async_select_option("vacuum")
    assert device.commands[-1]._args == {"mode": WorkMode.VACUUM}  # noqa: SLF001

    numbers = {
        e.entity_description.key: e
        for e in get_supported_entities([device], number.YeediSettingNumber, number.SETTING_DESCRIPTIONS)
    }
    for n in numbers.values():
        _ready(n)
        await n.async_added_to_hass()
    await device.events.emit(CleanCountEvent(2))
    await device.events.emit(MopAutoWashFrequencyEvent(15))
    assert numbers["clean_count"].native_value == 2
    assert numbers["mop_auto_wash_frequency"].native_value == 15
    assert numbers["mop_auto_wash_frequency"].native_max_value == 60

    keys = {
        e.entity_description.key
        for e in get_supported_entities([device], switch.YeediSwitch, switch.ENTITY_DESCRIPTIONS)
    }
    assert {"child_lock", "true_detect"} <= keys


async def test_active_map() -> None:
    """Robots keeping several floors: the active map can be chosen."""
    from deebot_client.events.map import CachedMapInfoEvent, Map
    from deebot_client.rs.map import RotationAngle

    from custom_components.yeedi import select
    from custom_components.yeedi.commands import UseMap

    register_yeedi_models()
    device = FakeDevice(capabilities=dc_hardware._DEVICES["04z443"].capabilities)  # noqa: SLF001
    sel = select.YeediMapSelect(device, device.capabilities.map)
    _ready(sel)
    await sel.async_added_to_hass()
    angle = RotationAngle.DEG_0
    await device.events.emit(
        CachedMapInfoEvent({Map("1", "Ground floor", True, True, angle), Map("2", "", False, True, angle)})
    )
    assert sel.options == ["Ground floor", "#2"] and sel.current_option == "Ground floor"
    await sel.async_select_option("#2")
    (cmd,) = [c for c in device.commands if isinstance(c, UseMap)]
    assert cmd._args == {"act": "use", "mid": "2"}  # noqa: SLF001
