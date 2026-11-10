"""Capability sheets for Yeedi robots (950-type JSON protocol).

Model sheet for the yeedi vac max (class 04z443) and its siblings.

Écrite le 10/11/2026 à partir de la fiche Deebot OZMO 950 (yna5xi) et de la fiche Node
(ecovacs-deebot.js, library/models.js : 950type, spot_area, custom_area, mopping_system,
auto_empty_station, clean_speed, map_image_supported). Vitesses : Standard / Max / Max+
(pas de niveau silencieux sur ce modèle, comme dans l'appli yeedi).
"""

from __future__ import annotations

from deebot_client.capabilities import (
    Capabilities,
    CapabilityClean,
    CapabilityCleanAction,
    CapabilityCustomCommand,
    CapabilityEvent,
    CapabilityExecute,
    CapabilityLifeSpan,
    CapabilityMap,
    CapabilitySet,
    CapabilitySetEnable,
    CapabilitySettings,
    CapabilitySetTypes,
    CapabilityStation,
    CapabilityStats,
    CapabilityExecuteTypes,
    CapabilityWater,
    DeviceType,
)
from deebot_client.commands.json.advanced_mode import GetAdvancedMode, SetAdvancedMode
from deebot_client.commands.json.battery import GetBattery
from deebot_client.commands.json.carpet import (
    GetCarpetAutoFanBoost,
    SetCarpetAutoFanBoost,
)
from deebot_client.commands import StationAction
from deebot_client.commands.json import station_action
from deebot_client.commands.json.auto_empty import GetAutoEmpty, SetAutoEmpty
from deebot_client.commands.json.charge import Charge
from deebot_client.commands.json.charge_state import GetChargeState
from deebot_client.commands.json.clean import Clean, CleanArea, GetCleanInfo
from deebot_client.commands.json.clean_logs import GetCleanLogs
from deebot_client.commands.json.clear_map import ClearMap
from deebot_client.commands.json.continuous_cleaning import (
    GetContinuousCleaning,
    SetContinuousCleaning,
)
from deebot_client.commands.json.custom import CustomCommand
from deebot_client.commands.json.error import GetError
from deebot_client.commands.json.fan_speed import GetFanSpeed, SetFanSpeed
from deebot_client.commands.json.life_span import GetLifeSpan, ResetLifeSpan
from deebot_client.commands.json.map import (
    GetMajorMap,
    GetMapSet,
    GetMapTrace,
    GetMinorMap,
    SetMajorMap,
)
from deebot_client.commands.json.multimap_state import (
    GetMultimapState,
    SetMultimapState,
)
from deebot_client.commands.json.network import GetNetInfo
from deebot_client.commands.json.ota import GetOta
from deebot_client.commands.json.play_sound import PlaySound
from deebot_client.commands.json.pos import GetPos
from deebot_client.commands.json.relocation import SetRelocationState
from deebot_client.commands.json.stats import GetStats, GetTotalStats
from deebot_client.commands.json.volume import GetVolume, SetVolume
from deebot_client.commands.json.water_info import GetWaterInfo, SetWaterInfo
from deebot_client.const import DataType
from deebot_client.events import (
    AdvancedModeEvent,
    AvailabilityEvent,
    BatteryEvent,
    CachedMapInfoEvent,
    CarpetAutoFanBoostEvent,
    CleanLogEvent,
    ContinuousCleaningEvent,
    CustomCommandEvent,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    LifeSpan,
    LifeSpanEvent,
    MajorMapEvent,
    MapChangedEvent,
    MapTraceEvent,
    MultimapStateEvent,
    OtaEvent,
    PositionsEvent,
    ReportStatsEvent,
    RoomsEvent,
    StateEvent,
    StationEvent,
    StatsEvent,
    TotalStatsEvent,
    VolumeEvent,
    water_info,
)
from deebot_client.events import auto_empty
from deebot_client.events.auto_empty import AutoEmptyEvent
from deebot_client.events.network import NetworkInfoEvent
from deebot_client.models import StaticDeviceInfo

from .commands import GetMapInfoV2


def _station() -> CapabilityStation:
    """Auto-empty station capabilities."""
    return CapabilityStation(
        action=CapabilityExecuteTypes(
            station_action.StationAction, types=(StationAction.EMPTY_DUSTBIN,)
        ),
        auto_empty=CapabilitySetTypes(
            event=AutoEmptyEvent,
            get=[GetAutoEmpty()],
            set=SetAutoEmpty,
            types=(auto_empty.Frequency.AUTO, auto_empty.Frequency.SMART),
        ),
        # The yeedi stations do not answer getStationState: nothing to poll.
        state=CapabilityEvent(StationEvent, []),
    )


def yeedi_950_capabilities(*, station: bool = True) -> StaticDeviceInfo:
    """Return the capabilities of a Yeedi 950-type robot."""
    return StaticDeviceInfo(
        DataType.JSON,
        Capabilities(
            device_type=DeviceType.VACUUM,
            availability=CapabilityEvent(
                AvailabilityEvent, [GetBattery(is_available_check=True)]
            ),
            battery=CapabilityEvent(BatteryEvent, [GetBattery()]),
            charge=CapabilityExecute(Charge),
            clean=CapabilityClean(
                action=CapabilityCleanAction(command=Clean, area=CleanArea),
                continuous=CapabilitySetEnable(
                    ContinuousCleaningEvent,
                    [GetContinuousCleaning()],
                    SetContinuousCleaning,
                ),
                log=CapabilityEvent(CleanLogEvent, [GetCleanLogs()]),
            ),
            custom=CapabilityCustomCommand(
                event=CustomCommandEvent, get=[], set=CustomCommand
            ),
            error=CapabilityEvent(ErrorEvent, [GetError()]),
            fan_speed=CapabilitySetTypes(
                event=FanSpeedEvent,
                get=[GetFanSpeed()],
                set=SetFanSpeed,
                types=(
                    FanSpeedLevel.NORMAL,
                    FanSpeedLevel.MAX,
                    FanSpeedLevel.MAX_PLUS,
                ),
            ),
            life_span=CapabilityLifeSpan(
                types=(LifeSpan.BRUSH, LifeSpan.FILTER, LifeSpan.SIDE_BRUSH),
                event=LifeSpanEvent,
                get=[
                    GetLifeSpan([LifeSpan.BRUSH, LifeSpan.FILTER, LifeSpan.SIDE_BRUSH])
                ],
                reset=ResetLifeSpan,
            ),
            map=CapabilityMap(
                cached_info=CapabilityEvent(CachedMapInfoEvent, [GetMapInfoV2()]),
                changed=CapabilityEvent(MapChangedEvent, []),
                clear=CapabilityExecute(ClearMap),
                major=CapabilitySet(MajorMapEvent, [GetMajorMap()], SetMajorMap),
                minor=CapabilityExecute(GetMinorMap),
                multi_state=CapabilitySetEnable(
                    MultimapStateEvent, [GetMultimapState()], SetMultimapState
                ),
                position=CapabilityEvent(PositionsEvent, [GetPos()]),
                relocation=CapabilityExecute(SetRelocationState),
                rooms=CapabilityEvent(RoomsEvent, [GetMapInfoV2()]),
                set=CapabilityExecute(GetMapSet),
                trace=CapabilityEvent(MapTraceEvent, [GetMapTrace()]),
            ),
            network=CapabilityEvent(NetworkInfoEvent, [GetNetInfo()]),
            play_sound=CapabilityExecute(PlaySound),
            settings=CapabilitySettings(
                advanced_mode=CapabilitySetEnable(
                    AdvancedModeEvent, [GetAdvancedMode()], SetAdvancedMode
                ),
                carpet_auto_fan_boost=CapabilitySetEnable(
                    CarpetAutoFanBoostEvent,
                    [GetCarpetAutoFanBoost()],
                    SetCarpetAutoFanBoost,
                ),
                ota=CapabilityEvent(OtaEvent, [GetOta()]),
                volume=CapabilitySet(VolumeEvent, [GetVolume()], SetVolume),
            ),
            state=CapabilityEvent(StateEvent, [GetChargeState(), GetCleanInfo()]),
            station=_station() if station else None,
            stats=CapabilityStats(
                clean=CapabilityEvent(StatsEvent, [GetStats()]),
                report=CapabilityEvent(ReportStatsEvent, []),
                total=CapabilityEvent(TotalStatsEvent, [GetTotalStats()]),
            ),
            water=CapabilityWater(
                amount=CapabilitySetTypes(
                    event=water_info.WaterAmountEvent,
                    get=[GetWaterInfo()],
                    set=SetWaterInfo,
                    types=(
                        water_info.WaterAmount.LOW,
                        water_info.WaterAmount.MEDIUM,
                        water_info.WaterAmount.HIGH,
                        water_info.WaterAmount.ULTRAHIGH,
                    ),
                ),
                mop_attached=CapabilityEvent(
                    water_info.MopAttachedEvent, [GetWaterInfo()]
                ),
            ),
        ),
    )


# Yeedi model classes using the 950-type JSON protocol, and what kind of dock they have.
# Sources: ecovacs-deebot.js (library/models.js, KnownYeediModels) and the yeedi product pages.
# Only the vac max has been tested with a real robot; the others share the same protocol
# family ("QRP"/"BL_QRP" in the Ecovacs cloud) and are declared on a best-effort basis.
# The Floor 3 Station / Floor 3+ family (t5e5o6, kd0una, t6kipw, u3bsxq, rwp09o) is not
# listed here on purpose: deebot-client ships its own, more complete sheets for them.
#
# Dock kinds:
#   "empty"  - auto-empty station (dust bag): station entities are created.
#   "mop"    - mop-washing/drying station: no auto-empty, so no station entities (yet).
#   "none"   - plain charging dock.
YEEDI_MODELS: dict[str, tuple[str, str]] = {
    "04z443": ("yeedi vac max", "empty"),
    "h041es": ("yeedi vac hybrid", "empty"),
    "mnx7f4": ("yeedi vac station", "empty"),
    "aaxesz": ("yeedi vac 2 pro", "empty"),  # station sold as an optional bundle
    "9t30w8": ("yeedi vac 2", "empty"),
    "6r6dbt": ("yeedi cube", "empty"),
    "p5nx9u": ("yeedi 2 hybrid", "none"),
    "vthpeg": ("yeedi mop station", "mop"),
    "zwvyi2": ("yeedi mop station pro", "mop"),
}


def model_name(class_: str) -> str | None:
    """Return the marketing name of a Yeedi class, if known."""
    return YEEDI_MODELS.get(class_, (None, ""))[0]


def register_yeedi_models() -> None:
    """Make the Yeedi models known to deebot-client (without shadowing its own sheets)."""
    from deebot_client import hardware  # noqa: PLC0415

    for model, (_name, dock) in YEEDI_MODELS.items():
        if model not in hardware._DEVICES:  # noqa: SLF001
            hardware._DEVICES[model] = yeedi_950_capabilities(station=dock == "empty")  # noqa: SLF001
        hardware._NOT_FOUND.discard(model)  # noqa: SLF001
