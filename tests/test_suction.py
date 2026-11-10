"""Tests for the suction power (fan speed + mop only)."""

from __future__ import annotations

from unittest.mock import MagicMock

from deebot_client.events import FanSpeedEvent
from deebot_client.events.fan_speed import FanSpeedLevel

from custom_components.yeedi import suction as suction_module
from custom_components.yeedi.suction import MOP_ONLY, YeediSuction

from .conftest import FakeDevice


def _device(with_water: bool = True) -> FakeDevice:
    caps = MagicMock()
    caps.fan_speed.types = [FanSpeedLevel.NORMAL, FanSpeedLevel.MAX, FanSpeedLevel.MAX_PLUS]
    caps.fan_speed.event = FanSpeedEvent
    caps.fan_speed.set = lambda level: ("fan", level)
    caps.water = object() if with_water else None
    caps.custom.set = lambda name, args: ("custom", name, args)
    return FakeDevice(capabilities=caps)


def test_options() -> None:
    assert YeediSuction(_device()).options == [MOP_ONLY, "normal", "max", "max_plus"]
    assert YeediSuction(_device(with_water=False)).options == ["normal", "max", "max_plus"]
    no_fan = _device()
    no_fan.capabilities.fan_speed = None
    assert YeediSuction(no_fan).options == [] and not YeediSuction(no_fan).supported


async def test_mop_only_and_levels() -> None:
    device = _device()
    s = YeediSuction(device)
    s.start()
    seen = []
    s.add_listener(lambda: seen.append(s.current))

    await device.events.emit(FanSpeedEvent(FanSpeedLevel.MAX))
    assert s.current == "max"

    await s.async_set(MOP_ONLY)
    assert device.commands[-1] == ("custom", "setMopMute", {"enable": 1})
    assert s.current == MOP_ONLY

    await s.async_set("normal")
    assert device.commands[-2:] == [("custom", "setMopMute", {"enable": 0}), ("fan", "normal")]
    assert s.current == "normal"
    assert seen[-1] == "normal"


async def test_robot_change_clears_mop_only(monkeypatch) -> None:
    device = _device()
    s = YeediSuction(device)
    s.start()
    await device.events.emit(FanSpeedEvent(FanSpeedLevel.MAX))
    await s.async_set(MOP_ONLY)

    # Right after our own command: the robot's echo must not cancel mop only.
    await device.events.emit(FanSpeedEvent(FanSpeedLevel.MAX_PLUS))
    assert s.current == MOP_ONLY

    # Long after: a level changed in the yeedi app turns the motor back on.
    monkeypatch.setattr(suction_module.time, "monotonic", lambda: 10_000.0)
    await device.events.emit(FanSpeedEvent(FanSpeedLevel.MAX_PLUS))  # same level: no change
    assert s.current == MOP_ONLY
    await device.events.emit(FanSpeedEvent(FanSpeedLevel.NORMAL))
    assert s.current == "normal"


def test_restore_once() -> None:
    s = YeediSuction(_device())
    s.restore("max")  # not mop only: nothing to restore
    assert not s.mop_only
    s.restore(MOP_ONLY)  # restore happens once only
    assert not s.mop_only
    s2 = YeediSuction(_device())
    s2.restore(MOP_ONLY)
    assert s2.current == MOP_ONLY
