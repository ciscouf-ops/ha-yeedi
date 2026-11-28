"""Sensors for Yeedi robots: battery, error, cleaning statistics, consumables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from deebot_client.capabilities import CapabilityEvent, CapabilityLifeSpan
from deebot_client.device import Device
from deebot_client.events import (
    BatteryEvent,
    ErrorEvent,
    Event,
    LifeSpan,
    LifeSpanEvent,
    StatsEvent,
    TotalStatsEvent,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.sensor import RestoreSensor
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfArea, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import PROBLEM_CODES, PROBLEM_OPTIONS, SUPPORTED_LIFESPANS
from .controller import YeediConfigEntry
from .entity import (
    YeediCapabilityEntityDescription,
    YeediDescriptionEntity,
    YeediEntity,
    get_supported_entities,
)
from .map_data import YeediMapData

# Attribute holding when the last real cleaning ended (stats sensors).
ATTR_END = "end"
# Below this, with no area, the stats are an empty session, not a cleaning.
MIN_CLEANING_SECONDS = 60


@dataclass(kw_only=True, frozen=True)
class YeediSensorEntityDescription[EventT: Event](
    YeediCapabilityEntityDescription, SensorEntityDescription
):
    """Sensor description."""

    value_fn: Callable[[EventT], StateType]


ENTITY_DESCRIPTIONS: tuple[YeediSensorEntityDescription, ...] = (
    YeediSensorEntityDescription[BatteryEvent](
        key="battery",
        capability_fn=lambda caps: caps.battery,
        value_fn=lambda e: e.value,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YeediSensorEntityDescription[StatsEvent](
        key="stats_area",
        translation_key="stats_area",
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.area,
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
    ),
    YeediSensorEntityDescription[StatsEvent](
        key="stats_time",
        translation_key="stats_time",
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.time,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
    ),
    YeediSensorEntityDescription[TotalStatsEvent](
        key="total_stats_area",
        translation_key="total_stats_area",
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.area,
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    YeediSensorEntityDescription[TotalStatsEvent](
        key="total_stats_time",
        translation_key="total_stats_time",
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.time,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    YeediSensorEntityDescription[TotalStatsEvent](
        key="total_stats_cleanings",
        translation_key="total_stats_cleanings",
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.cleanings,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    YeediSensorEntityDescription[ErrorEvent](
        # What is wrong, in words (translated), for dashboards and notifications.
        key="problem",
        translation_key="problem",
        capability_fn=lambda caps: caps.error,
        value_fn=lambda e: PROBLEM_CODES.get(e.code, "other"),
        device_class=SensorDeviceClass.ENUM,
        options=PROBLEM_OPTIONS,
    ),
    YeediSensorEntityDescription[ErrorEvent](
        key="error",
        translation_key="error",
        capability_fn=lambda caps: caps.error,
        value_fn=lambda e: e.code,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


@dataclass(kw_only=True, frozen=True)
class YeediLifespanSensorEntityDescription(SensorEntityDescription):
    """Consumable description."""

    component: LifeSpan
    value_fn: Callable[[LifeSpanEvent], int | float]


LIFESPAN_ENTITY_DESCRIPTIONS = tuple(
    YeediLifespanSensorEntityDescription(
        component=component,
        value_fn=lambda e: e.percent,
        key=f"lifespan_{component.name.lower()}",
        translation_key=f"lifespan_{component.name.lower()}",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    for component in SUPPORTED_LIFESPANS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YeediConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    devices = entry.runtime_data.devices
    entities: list[YeediEntity] = get_supported_entities(
        devices, YeediSensor, ENTITY_DESCRIPTIONS
    )
    entities.extend(
        YeediLifespanSensor(device, device.capabilities.life_span, description)
        for device in devices
        for description in LIFESPAN_ENTITY_DESCRIPTIONS
        if description.component in device.capabilities.life_span.types
    )
    map_data = entry.runtime_data.map_data
    entities.extend(
        YeediProgressSensor(device, map_data[device.device_info["did"]], description)
        for device in devices
        if device.device_info["did"] in map_data
        for description in PROGRESS_DESCRIPTIONS
    )
    async_add_entities(entities)


@dataclass(kw_only=True, frozen=True)
class YeediProgressSensorEntityDescription(SensorEntityDescription):
    """Sensor built from the progress of the current cleaning (see YeediMapData)."""

    value_fn: Callable[[dict[str, Any] | None], StateType | datetime]
    attributes_fn: Callable[[dict[str, Any] | None], dict[str, Any]] = lambda _: {}
    # What the sensor reads in the map data (default: the progress of the cleaning).
    data_fn: Callable[[YeediMapData], Any] = lambda m: m.estimate()


def _end(progress: dict[str, Any] | None) -> datetime | None:
    end = (progress or {}).get("end")
    return datetime.fromtimestamp(end, UTC) if end else None


PROGRESS_DESCRIPTIONS: tuple[YeediProgressSensorEntityDescription, ...] = (
    YeediProgressSensorEntityDescription(
        key="current_room",
        translation_key="current_room",
        value_fn=lambda p: (p or {}).get("room"),
        attributes_fn=lambda p: {"room_id": (p or {}).get("room_id")},
    ),
    YeediProgressSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        value_fn=lambda p: (p or {}).get("remaining_minutes"),
        attributes_fn=lambda p: {
            "progress": (p or {}).get("progress"),
            "elapsed_minutes": (p or {}).get("elapsed_minutes"),
            "planned_rooms": (p or {}).get("planned"),
        },
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        suggested_display_precision=0,
    ),
    # 28/11/2026: history of the cleanings, recorded by ha-yeedi (rooms included).
    YeediProgressSensorEntityDescription(
        key="last_cleaning",
        translation_key="last_cleaning",
        data_fn=lambda m: m.history,
        value_fn=lambda h: datetime.fromtimestamp(h[0]["end"], UTC) if h else None,
        attributes_fn=lambda h: (
            {
                "minutes": h[0].get("minutes"),
                "area": h[0].get("area"),
                "rooms": h[0].get("rooms"),
                "result": h[0].get("result"),
                "history": h[:10],
            }
            if h
            else {}
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    YeediProgressSensorEntityDescription(
        key="cleaning_end",
        translation_key="cleaning_end",
        value_fn=_end,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


class YeediSensor(YeediDescriptionEntity[CapabilityEvent], RestoreSensor):
    """A sensor fed by one robot event."""

    entity_description: YeediSensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Subscribe to the event."""
        await super().async_added_to_hass()
        # When it (re)connects, the robot reports the stats of an empty session
        # (0 m2, a few seconds). Keep the last real cleaning instead (value and its
        # end time in the "end" attribute, restored across restarts).
        stats = self.entity_description.key in ("stats_area", "stats_time")
        if stats:
            last = await self.async_get_last_sensor_data()
            old = await self.async_get_last_state()
            if (
                last is not None
                and last.native_value is not None
                and old is not None
                and old.attributes.get(ATTR_END)
            ):
                self._attr_native_value = last.native_value
                self._attr_extra_state_attributes = {ATTR_END: old.attributes[ATTR_END]}

        async def on_event(event: Event) -> None:
            if (
                stats
                and isinstance(event, StatsEvent)
                and (event.time or 0) < MIN_CLEANING_SECONDS
                and not event.area
            ):
                return
            value = self.entity_description.value_fn(event)
            if value is not None:
                self._attr_native_value = value
                if isinstance(event, ErrorEvent):
                    self._attr_extra_state_attributes = {"description": event.description}
                    if self.entity_description.key == "problem":
                        self._attr_extra_state_attributes["code"] = event.code
                if stats:
                    self._attr_extra_state_attributes = {ATTR_END: dt_util.utcnow().isoformat()}
                self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)


class YeediLifespanSensor(YeediDescriptionEntity[CapabilityLifeSpan], SensorEntity):
    """Remaining life of a consumable."""

    entity_description: YeediLifespanSensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Subscribe to the event."""
        await super().async_added_to_hass()

        async def on_event(event: LifeSpanEvent) -> None:
            if event.type == self.entity_description.component:
                self._attr_native_value = self.entity_description.value_fn(event)
                self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)


class YeediProgressSensor(YeediDescriptionEntity[YeediMapData], SensorEntity):
    """Room, time left or end of the current cleaning, from the map data."""

    entity_description: YeediProgressSensorEntityDescription

    def __init__(
        self,
        device: Device,
        map_data: YeediMapData,
        description: YeediProgressSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(device, map_data, description)
        self._refresh()

    async def async_added_to_hass(self) -> None:
        """Follow the map data."""
        await super().async_added_to_hass()
        self.async_on_remove(self._capability.async_add_listener(self._on_map_data))

    @callback
    def _on_map_data(self) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _refresh(self) -> None:
        progress = self.entity_description.data_fn(self._capability)
        self._attr_native_value = self.entity_description.value_fn(progress)
        self._attr_extra_state_attributes = self.entity_description.attributes_fn(progress)
