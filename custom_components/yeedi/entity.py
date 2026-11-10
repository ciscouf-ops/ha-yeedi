"""Base entity for Yeedi robots."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import Capabilities
from deebot_client.device import Device
from deebot_client.events import AvailabilityEvent
from deebot_client.events.base import Event

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, MANUFACTURER


class YeediEntity[CapabilityEntityT](Entity):
    """Yeedi entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _always_available: bool = False

    def __init__(
        self, device: Device, capability: CapabilityEntityT, **kwargs: Any
    ) -> None:
        """Initialize entity."""
        super().__init__(**kwargs)
        self._attr_unique_id = (
            f"{device.device_info['did']}_{self.entity_description.key}"
        )
        self._device = device
        self._capability = capability
        self._subscribed_events: set[type[Event]] = set()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        info = self._device.device_info
        device_info = DeviceInfo(
            identifiers={(DOMAIN, info["did"])},
            manufacturer=MANUFACTURER,
            serial_number=info.get("name"),
            model_id=info["class"],
            model=info.get("deviceName") or f"yeedi {info['class']}",
            name=info.get("nick") or info.get("deviceName") or "yeedi",
        )
        if fw_version := self._device.fw_version:
            device_info["sw_version"] = fw_version
        if mac := self._device.mac:
            device_info["connections"] = {(dr.CONNECTION_NETWORK_MAC, mac)}
        return device_info

    async def async_added_to_hass(self) -> None:
        """Subscribe to availability once added."""
        await super().async_added_to_hass()
        if not self._always_available:

            async def on_available(event: AvailabilityEvent) -> None:
                self._attr_available = event.available
                self.async_write_ha_state()

            self._subscribe(AvailabilityEvent, on_available)

    def _subscribe[EventT: Event](
        self,
        event_type: type[EventT],
        callback: Callable[[EventT], Coroutine[Any, Any, None]],
    ) -> None:
        self._subscribed_events.add(event_type)
        self.async_on_remove(self._device.events.subscribe(event_type, callback))

    async def async_update(self) -> None:
        """Ask the robot to refresh everything this entity listens to."""
        for event_type in self._subscribed_events:
            self._device.events.request_refresh(event_type)


class YeediDescriptionEntity[CapabilityEntityT](YeediEntity[CapabilityEntityT]):
    """Entity built from a description."""

    def __init__(
        self,
        device: Device,
        capability: CapabilityEntityT,
        entity_description: EntityDescription,
        **kwargs: Any,
    ) -> None:
        """Initialize entity."""
        self.entity_description = entity_description
        super().__init__(device, capability, **kwargs)


@dataclass(kw_only=True, frozen=True)
class YeediCapabilityEntityDescription[CapabilityEntityT](EntityDescription):
    """Entity description bound to a capability."""

    capability_fn: Callable[[Capabilities], CapabilityEntityT | None]


def get_supported_entities(
    devices: list[Device],
    entity_class: type[YeediDescriptionEntity],
    descriptions: tuple[YeediCapabilityEntityDescription, ...],
) -> list[YeediEntity]:
    """Return the entities every robot supports."""
    return [
        entity_class(device, capability, description)
        for device in devices
        for description in descriptions
        if (capability := description.capability_fn(device.capabilities))
    ]
