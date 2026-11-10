"""Suction power of a robot, shared by the vacuum entity and the suction select.

The suction power is the robot's fan speed, plus "mop only": the yeedi ``MopMute``
setting, which turns the vacuum motor off so only the mop works. The robot reports its
fan speed but not the mop-only setting, so the latter is kept here, as last set from
Home Assistant (and restored by the entities after a restart).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from deebot_client.device import Device
from deebot_client.events import FanSpeedEvent

MOP_ONLY = "mop_only"


def _name_key(level: Any) -> str:
    return str(level.name).lower()


class YeediSuction:
    """Suction power of one robot."""

    def __init__(self, device: Device) -> None:
        """Initialize."""
        self._device = device
        self._capability = device.capabilities.fan_speed
        self.mop_only = False
        self._robot_level: str | None = None
        self._restored = False
        self._listeners: list[Callable[[], None]] = []
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def supported(self) -> bool:
        """Return True if the robot has a fan speed setting."""
        return self._capability is not None

    @property
    def options(self) -> list[str]:
        """Return the possible levels, mop only first when the robot can mop."""
        if self._capability is None:
            return []
        levels = [_name_key(t) for t in self._capability.types]
        if self._device.capabilities.water is not None:
            levels.insert(0, MOP_ONLY)
        return levels

    @property
    def current(self) -> str | None:
        """Return the current level."""
        return MOP_ONLY if self.mop_only else self._robot_level

    def start(self) -> None:
        """Follow the fan speed reported by the robot."""
        if self._capability is None:
            return

        async def on_fan_speed(event: FanSpeedEvent) -> None:
            self._robot_level = _name_key(event.speed)
            self._notify()

        self._unsubscribe = self._device.events.subscribe(
            self._capability.event, on_fan_speed
        )

    def stop(self) -> None:
        """Stop following the robot."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def restore(self, level: str | None) -> None:
        """Restore the mop-only setting saved by an entity (once)."""
        if self._restored:
            return
        self._restored = True
        if level == MOP_ONLY and MOP_ONLY in self.options:
            self.mop_only = True
            self._notify()

    async def async_set(self, level: str) -> None:
        """Set the suction power."""
        if self._capability is None:
            return
        if level == MOP_ONLY:
            await self._set_mop_only(True)
        else:
            if self.mop_only or MOP_ONLY in self.options:
                await self._set_mop_only(False)
            await self._device.execute_command(self._capability.set(level))
            self._robot_level = level
        self._notify()

    async def _set_mop_only(self, enable: bool) -> None:
        await self._device.execute_command(
            self._device.capabilities.custom.set(
                "setMopMute", {"enable": 1 if enable else 0}
            )
        )
        self.mop_only = enable

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call ``listener`` when the level changes; return the remover."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()
