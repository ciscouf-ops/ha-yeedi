"""Binary sensors for Yeedi robots: water tanks of a mop-washing station."""

from __future__ import annotations

from dataclasses import dataclass

from deebot_client.capabilities import Capabilities, CapabilityEvent
from deebot_client.commands import StationAction
from deebot_client.events import ErrorEvent

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controller import YeediConfigEntry
from .entity import (
    YeediCapabilityEntityDescription,
    YeediDescriptionEntity,
    get_supported_entities,
)


@dataclass(kw_only=True, frozen=True)
class YeediErrorBinarySensorEntityDescription(
    YeediCapabilityEntityDescription, BinarySensorEntityDescription
):
    """On while the robot reports one of these error codes."""

    codes: frozenset[int]


def _water_station(caps: Capabilities) -> CapabilityEvent | None:
    # The station measures no water level, it only reports these errors (M16 Infinity,
    # issue #2). Only for the stations that wash the mop, so have water tanks.
    if caps.station and StationAction.WASH_MOP in caps.station.action.types:
        return caps.error
    return None


ENTITY_DESCRIPTIONS: tuple[YeediErrorBinarySensorEntityDescription, ...] = (
    YeediErrorBinarySensorEntityDescription(
        key="clean_water_empty",
        translation_key="clean_water_empty",
        capability_fn=_water_station,
        # FreshWaterBox empty; Clean Water Tank is empty or not installed.
        codes=frozenset({301, 322}),
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    YeediErrorBinarySensorEntityDescription(
        key="dirty_water_full",
        translation_key="dirty_water_full",
        capability_fn=_water_station,
        # WasteWaterBox full; Dirty Water Tank is full (305, 318, 323 not installed).
        codes=frozenset({302, 305, 318, 323}),
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities(
        get_supported_entities(
            entry.runtime_data.devices, YeediErrorBinarySensor, ENTITY_DESCRIPTIONS
        )
    )


class YeediErrorBinarySensor(
    YeediDescriptionEntity[CapabilityEvent], BinarySensorEntity
):
    """A station problem, read from the robot errors."""

    entity_description: YeediErrorBinarySensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Follow the errors."""
        await super().async_added_to_hass()

        async def on_event(event: ErrorEvent) -> None:
            if event.code in self.entity_description.codes:
                self._attr_is_on = True
            elif event.code == 0 or self._attr_is_on is None:
                # The robot only reports its last error: another one does not mean
                # this one is solved, "no error" (0) does.
                self._attr_is_on = False
            else:
                return
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)
