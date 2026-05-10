from dataclasses import dataclass, field
from typing import Any

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class IaquaHomeResponse(DataClassJSONMixin):
    home_screen: list["HomeScreenItem"]
    message: str = ""
    serial: str = ""


@dataclass
class IaquaDevicesResponse(DataClassJSONMixin):
    devices_screen: list["DevicesScreenItem"]
    message: str = ""


# Home Screen Response


@dataclass
class HeatpumpInfo:
    isheatpump_present: bool | None = field(
        default=False, metadata=field_options(alias="isheatpumpPresent")
    )
    heatpumpstatus: str | None = field(
        default=None, metadata=field_options(alias="heatpumpstatus")
    )
    is_chill_available: bool | None = field(
        default=False, metadata=field_options(alias="isChillAvailable")
    )
    heatpumpmode: str | None = field(
        default=None, metadata=field_options(alias="heatpumpmode")
    )
    heatpumptype: str | None = field(
        default=None, metadata=field_options(alias="heatpumptype")
    )


@dataclass
class IclCustomColorInfo:
    zone_id: int = field(metadata=field_options(alias="zoneId"))
    red_val: int
    green_val: int
    blue_val: int
    white_val: int


@dataclass
class SwcInfo:
    isswc_present: bool = field(metadata=field_options(alias="isswcPresent"))
    swc_pool_value: str | None = field(
        default=None, metadata=field_options(alias="swcPoolValue")
    )
    swc_pool_status: str | None = field(
        default=None, metadata=field_options(alias="swcPoolStatus")
    )
    swc_spa_value: str | None = field(
        default=None, metadata=field_options(alias="swcSpaValue")
    )
    swc_spa_status: str | None = field(
        default=None, metadata=field_options(alias="swcSpaStatus")
    )


@dataclass
class HomeScreenStatus:
    status: str


@dataclass
class HomeScreenResponse:
    response: str


@dataclass
class HomeScreenSystemType:
    system_type: str


@dataclass
class HomeScreenTempScale:
    temp_scale: str


@dataclass
class HomeScreenSpaTemp:
    spa_temp: str


@dataclass
class HomeScreenPoolTemp:
    pool_temp: str


@dataclass
class HomeScreenAirTemp:
    air_temp: str


@dataclass
class HomeScreenSetPoint:
    spa_set_point: str


@dataclass
class HomeScreenPoolSetPoint:
    pool_set_point: str


@dataclass
class HomeScreenCoverPool:
    cover_pool: str


@dataclass
class HomeScreenFreezeProtection:
    freeze_protection: str


@dataclass
class HomeScreenSpaPump:
    spa_pump: str


@dataclass
class HomeScreenPoolPump:
    pool_pump: str


@dataclass
class HomeScreenSpaHeater:
    spa_heater: str


@dataclass
class HomeScreenPoolHeater:
    pool_heater: str


@dataclass
class HomeScreenSolarHeater:
    solar_heater: str


@dataclass
class HomeScreenSpaSalinity:
    spa_salinity: str


@dataclass
class HomeScreenPoolSalinity:
    pool_salinity: str


@dataclass
class HomeScreenOrp:
    orp: str


@dataclass
class HomeScreenPh:
    ph: str


@dataclass
class HomeScreenIsIclPresent:
    is_icl_present: str


@dataclass
class HomeScreenIclCustomColor:
    icl_custom_color_info: list[IclCustomColorInfo]


@dataclass
class HomeScreenHeatpumpInfo:
    heatpump_info: HeatpumpInfo


@dataclass
class HomeScreenPoolChillSetPoint:
    pool_chill_set_point: str


@dataclass
class HomeScreenSwcInfo:
    swc_info: SwcInfo


@dataclass
class HomeScreenRelayCount:
    relay_count: str


@dataclass
class DevicesScreenGroup:
    group: str


@dataclass
class DevicesScreenAuxAttrs:
    """Aux device attributes, deserialized from a list of single-key dicts.

    The API sends: [{"state": "0"}, {"label": "X"}, {"icon": "..."}, ...]
    __pre_deserialize__ flattens that into a plain dict before mashumaro
    maps it onto the dataclass fields.
    """

    state: str
    label: str
    icon: str
    type: str
    subtype: str

    @classmethod
    def __pre_deserialize__(cls, d: Any) -> Any:
        if isinstance(d, list):
            merged: dict[str, Any] = {}
            for item in d:
                merged.update(item)
            return merged
        return d


@dataclass
class DevicesScreenAux:
    """Single aux entry from devices_screen: {"aux_N": [attrs...]}.

    __pre_deserialize__ extracts the aux name and passes attrs to
    DevicesScreenAuxAttrs for further flattening.
    """

    name: str
    attrs: DevicesScreenAuxAttrs

    @classmethod
    def __pre_deserialize__(cls, d: Any) -> Any:
        if isinstance(d, dict) and len(d) == 1:
            name, attrs = next(iter(d.items()))
            return {"name": name, "attrs": attrs}
        return d


DevicesScreenItem = (
    HomeScreenStatus
    | HomeScreenResponse
    | DevicesScreenGroup
    | DevicesScreenAux
)

# mashumaro resolves union variants in declaration order. The ordering below
# is intentional: more specific single-field types are tried before broader
# ones. Do not reorder without verifying against real API responses.
HomeScreenItem = (
    HomeScreenAirTemp
    | HomeScreenCoverPool
    | HomeScreenFreezeProtection
    | HomeScreenHeatpumpInfo
    | HomeScreenIclCustomColor
    | HomeScreenIsIclPresent
    | HomeScreenOrp
    | HomeScreenPh
    | HomeScreenPoolChillSetPoint
    | HomeScreenPoolHeater
    | HomeScreenPoolPump
    | HomeScreenPoolSalinity
    | HomeScreenPoolSetPoint
    | HomeScreenPoolTemp
    | HomeScreenRelayCount
    | HomeScreenResponse
    | HomeScreenSetPoint
    | HomeScreenSolarHeater
    | HomeScreenSpaHeater
    | HomeScreenSpaPump
    | HomeScreenSpaSalinity
    | HomeScreenSpaTemp
    | HomeScreenStatus
    | HomeScreenSwcInfo
    | HomeScreenSystemType
    | HomeScreenTempScale
)
