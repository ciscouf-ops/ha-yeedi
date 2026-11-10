"""Buttons for Yeedi robots: empty the dustbin, relocate, reset consumables, clear the map."""

from __future__ import annotations

from dataclasses import dataclass

from deebot_client.capabilities import (
    CapabilityExecute,
    CapabilityExecuteTypes,
    CapabilityLifeSpan,
)
from deebot_client.commands import StationAction
from deebot_client.events import LifeSpan

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_STATION, SUPPORTED_LIFESPANS
from .controller import YeediConfigEntry
from .entity import (
    YeediCapabilityEntityDescription,
    YeediDescriptionEntity,
    YeediEntity,
    get_supported_entities,
)


@dataclass(kw_only=True, frozen=True)
class YeediButtonEntityDescription(
    YeediCapabilityEntityDescription, ButtonEntityDescription
):
    """Button bound to an execute capability."""


@dataclass(kw_only=True, frozen=True)
class YeediLifeSpanButtonEntityDescription(
    YeediCapabilityEntityDescription, ButtonEntityDescription
):
    """Button resetting one consumable counter."""

    component: LifeSpan


@dataclass(kw_only=True, frozen=True)
class YeediStationButtonEntityDescription(
    YeediCapabilityEntityDescription, ButtonEntityDescription
):
    """Button running one station action."""

    action: StationAction


ENTITY_DESCRIPTIONS: tuple[YeediButtonEntityDescription, ...] = (
    YeediButtonEntityDescription(
        key="relocate",
        translation_key="relocate",
        capability_fn=lambda caps: caps.map.relocation if caps.map else None,
        entity_category=EntityCategory.CONFIG,
    ),
    YeediButtonEntityDescription(
        key="clear_map",
        translation_key="clear_map",
        capability_fn=lambda caps: caps.map.clear if caps.map else None,
        entity_category=EntityCategory.CONFIG,
        # Destructive: hidden by default, the user enables it knowingly.
        entity_registry_enabled_default=False,
    ),
)

STATION_DESCRIPTIONS: tuple[YeediStationButtonEntityDescription, ...] = (
    YeediStationButtonEntityDescription(
        key="station_empty_dustbin",
        translation_key="station_empty_dustbin",
        capability_fn=lambda caps: (
            caps.station.action
            if caps.station and StationAction.EMPTY_DUSTBIN in caps.station.action.types
            else None
        ),
        action=StationAction.EMPTY_DUSTBIN,
    ),
)

LIFESPAN_DESCRIPTIONS: tuple[YeediLifeSpanButtonEntityDescription, ...] = tuple(
    YeediLifeSpanButtonEntityDescription(
        key=f"reset_lifespan_{component.name.lower()}",
        translation_key=f"reset_lifespan_{component.name.lower()}",
        capability_fn=lambda caps, c=component: (
            caps.life_span if c in caps.life_span.types else None
        ),
        component=component,
        entity_category=EntityCategory.CONFIG,
    )
    for component in SUPPORTED_LIFESPANS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    devices = entry.runtime_data.devices
    entities: list[YeediEntity] = get_supported_entities(
        devices, YeediButton, ENTITY_DESCRIPTIONS
    )
    # The station is optional on several models: only when the user says they have one.
    if entry.options.get(CONF_STATION, False):
        entities.extend(
            get_supported_entities(devices, YeediStationButton, STATION_DESCRIPTIONS)
        )
    entities.extend(get_supported_entities(devices, YeediLifeSpanButton, LIFESPAN_DESCRIPTIONS))
    async_add_entities(entities)


class YeediButton(YeediDescriptionEntity[CapabilityExecute], ButtonEntity):
    """A button running a robot command."""

    entity_description: YeediButtonEntityDescription

    async def async_press(self) -> None:
        """Run the command."""
        await self._device.execute_command(self._capability.execute())


class YeediStationButton(
    YeediDescriptionEntity[CapabilityExecuteTypes[StationAction]], ButtonEntity
):
    """A button running a station action."""

    entity_description: YeediStationButtonEntityDescription

    async def async_press(self) -> None:
        """Run the station action."""
        await self._device.execute_command(
            self._capability.execute(self.entity_description.action)
        )


class YeediLifeSpanButton(YeediDescriptionEntity[CapabilityLifeSpan], ButtonEntity):
    """A button resetting a consumable counter."""

    entity_description: YeediLifeSpanButtonEntityDescription

    async def async_press(self) -> None:
        """Reset the counter and refresh the matching sensor."""
        await self._device.execute_command(
            self._capability.reset(self.entity_description.component)
        )
        self._device.events.request_refresh(self._capability.event)
