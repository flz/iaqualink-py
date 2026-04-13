from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class IaquaHomeResponse(DataClassJSONMixin):
    home_screen: list["HomeScreenItem"]
    message: str = ""
    serial: str = ""


@dataclass
class IaquaDevicesResponse(DataClassJSONMixin):
    devices_screen: list[dict[str, Any]]
    message: str = ""


### Home Screen Response


@dataclass
class HeatpumpInfo(DataClassJSONMixin):
    isheatpump_present: Optional[bool] = field(
        default=False, metadata=field_options(alias="isheatpumpPresent")
    )
    heatpumpstatus: Optional[str] = field(
        default=None, metadata=field_options(alias="heatpumpstatus")
    )
    is_chill_available: Optional[bool] = field(
        default=False, metadata=field_options(alias="isChillAvailable")
    )
    heatpumpmode: Optional[str] = field(
        default=None, metadata=field_options(alias="heatpumpmode")
    )
    heatpumptype: Optional[str] = field(
        default=None, metadata=field_options(alias="heatpumptype")
    )


@dataclass
class IclCustomColorInfo(DataClassJSONMixin):
    zone_id: int = field(metadata=field_options(alias="zoneId"))
    red_val: int
    green_val: int
    blue_val: int
    white_val: int


@dataclass
class SwcInfo(DataClassJSONMixin):
    isswc_present: bool = field(metadata=field_options(alias="isswcPresent"))
    swc_pool_value: Optional[str] = field(
        default=None, metadata=field_options(alias="swcPoolValue")
    )
    swc_pool_status: Optional[str] = field(
        default=None, metadata=field_options(alias="swcPoolStatus")
    )


@dataclass
class HomeScreenStatus(DataClassJSONMixin):
    status: str


@dataclass
class HomeScreenResponse(DataClassJSONMixin):
    response: str


@dataclass
class HomeScreenSystemType(DataClassJSONMixin):
    system_type: str


@dataclass
class HomeScreenTempScale(DataClassJSONMixin):
    temp_scale: str


@dataclass
class HomeScreenSpaTemp(DataClassJSONMixin):
    spa_temp: str


@dataclass
class HomeScreenPoolTemp(DataClassJSONMixin):
    pool_temp: str


@dataclass
class HomeScreenAirTemp(DataClassJSONMixin):
    air_temp: str


@dataclass
class HomeScreenSetPoint(DataClassJSONMixin):
    spa_set_point: str


@dataclass
class HomeScreenPoolSetPoint(DataClassJSONMixin):
    pool_set_point: str


@dataclass
class HomeScreenCoverPool(DataClassJSONMixin):
    cover_pool: str


@dataclass
class HomeScreenFreezeProtection(DataClassJSONMixin):
    freeze_protection: str


@dataclass
class HomeScreenSpaPump(DataClassJSONMixin):
    spa_pump: str


@dataclass
class HomeScreenPoolPump(DataClassJSONMixin):
    pool_pump: str


@dataclass
class HomeScreenSpaHeater(DataClassJSONMixin):
    spa_heater: str


@dataclass
class HomeScreenPoolHeater(DataClassJSONMixin):
    pool_heater: str


@dataclass
class HomeScreenSolarHeater(DataClassJSONMixin):
    solar_heater: str


@dataclass
class HomeScreenSpaSalinity(DataClassJSONMixin):
    spa_salinity: str


@dataclass
class HomeScreenPoolSalinity(DataClassJSONMixin):
    pool_salinity: str


@dataclass
class HomeScreenOrp(DataClassJSONMixin):
    orp: str


@dataclass
class HomeScreenPh(DataClassJSONMixin):
    ph: str


@dataclass
class HomeScreenIsIclPresent(DataClassJSONMixin):
    is_icl_present: str


@dataclass
class HomeScreenIclCustomColor(DataClassJSONMixin):
    icl_custom_color_info: List[IclCustomColorInfo]


@dataclass
class HomeScreenHeatpumpInfo(DataClassJSONMixin):
    heatpump_info: HeatpumpInfo


@dataclass
class HomeScreenPoolChillSetPoint(DataClassJSONMixin):
    pool_chill_set_point: str


@dataclass
class HomeScreenSwcInfo(DataClassJSONMixin):
    swc_info: SwcInfo


@dataclass
class HomeScreenRelayCount(DataClassJSONMixin):
    relay_count: str


HomeScreenItem = Union[
    HomeScreenAirTemp,
    HomeScreenCoverPool,
    HomeScreenFreezeProtection,
    HomeScreenHeatpumpInfo,
    HomeScreenIclCustomColor,
    HomeScreenIsIclPresent,
    HomeScreenOrp,
    HomeScreenPh,
    HomeScreenPoolChillSetPoint,
    HomeScreenPoolHeater,
    HomeScreenPoolPump,
    HomeScreenPoolSalinity,
    HomeScreenPoolSetPoint,
    HomeScreenPoolTemp,
    HomeScreenRelayCount,
    HomeScreenResponse,
    HomeScreenSetPoint,
    HomeScreenSolarHeater,
    HomeScreenSpaHeater,
    HomeScreenSpaPump,
    HomeScreenSpaSalinity,
    HomeScreenSpaTemp,
    HomeScreenStatus,
    HomeScreenSwcInfo,
    HomeScreenSystemType,
    HomeScreenTempScale,
]


@dataclass
class HomeResponse(DataClassJSONMixin):
    message: str
    serial: str
    home_screen: List[HomeScreenItem]
