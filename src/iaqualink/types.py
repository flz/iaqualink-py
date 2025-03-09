from serde import field, serde, Untagged

from datetime import datetime
from typing import Union, Optional, List
from uuid import UUID


@serde
class CognitoPool:
    app_client_id: str = field(rename="appClientId")
    domain: str
    pool_id: str = field(rename="poolId")
    region: str


@serde(rename_all="pascalcase")
class Credentials:
    access_key_id: str
    secret_key: str
    session_token: str
    expiration: datetime
    identity_id: str


@serde(rename_all="pascalcase")
class UserPoolOAuth:
    expires_in: int
    token_type: str
    refresh_token: str
    id_token: str


@serde
class LoginResponse:
    username: UUID
    email: str
    first_name: str
    last_name: str
    address: str
    address_1: str
    address_2: None
    city: str
    state: None
    country: str
    postal_code: str
    id: int
    authentication_token: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    time_zone: None
    phone: str
    opt_in_1: str
    opt_in_2: str
    role: str
    cognito_pool: CognitoPool = field(rename="cognitoPool")
    credentials: Credentials
    user_pool_o_auth: UserPoolOAuth = field(rename="userPoolOAuth")


@serde
class DevicesResponseElement:
    id: int
    serial_number: str
    created_at: datetime
    updated_at: datetime
    name: str
    device_type: str
    owner_id: None
    updating: bool
    firmware_version: None
    target_firmware_version: None
    update_firmware_start_at: None
    last_activity_at: None


DevicesResponse = List[DevicesResponseElement]


### Home Screen Response


@serde(rename_all="camelcase")
class HeatpumpInfo:
    isheatpump_present: Optional[bool] = False
    heatpumpstatus: Optional[str] = None
    is_chill_available: Optional[bool] = False
    heatpumpmode: Optional[str] = None
    heatpumptype: Optional[str] = None


@serde
class IclCustomColorInfo:
    zone_id: int = field(rename="zoneId")
    red_val: int
    green_val: int
    blue_val: int
    white_val: int


@serde(rename_all="camelcase")
class SwcInfo:
    isswc_present: bool
    swc_pool_value: Optional[str] = None
    swc_pool_status: Optional[str] = None


@serde
class HomeScreenStatus:
    status: str


@serde
class HomeScreenResponse:
    response: str


@serde
class HomeScreenSystemType:
    system_type: str


@serde
class HomeScreenTempScale:
    temp_scale: str


@serde
class HomeScreenSpaTemp:
    spa_temp: str


@serde
class HomeScreenPoolTemp:
    pool_temp: str


@serde
class HomeScreenAirTemp:
    air_temp: str


@serde
class HomeScreenSetPoint:
    spa_set_point: str


@serde
class HomeScreenPoolSetPoint:
    pool_set_point: str


@serde
class HomeScreenCoverPool:
    cover_pool: str


@serde
class HomeScreenFreezeProtection:
    freeze_protection: str


@serde
class HomeScreenSpaPump:
    spa_pump: str


@serde
class HomeScreenPoolPump:
    pool_pump: str


@serde
class HomeScreenSpaHeater:
    spa_heater: str


@serde
class HomeScreenPoolHeater:
    pool_heater: str


@serde
class HomeScreenSolarHeater:
    solar_heater: str


@serde
class HomeScreenSpaSalinity:
    spa_salinity: str


@serde
class HomeScreenPoolSalinity:
    pool_salinity: str


@serde
class HomeScreenOrp:
    orp: str


@serde
class HomeScreenPh:
    ph: str


@serde
class HomeScreenIsIclPresent:
    is_icl_present: str


@serde
class HomeScreenIclCustomColor:
    icl_custom_color_info: List[IclCustomColorInfo]


@serde
class HomeScreenHeatpumpInfo:
    heatpump_info: HeatpumpInfo


@serde
class HomeScreenPoolChillSetPoint:
    pool_chill_set_point: str


@serde
class HomeScreenSwcInfo:
    swc_info: SwcInfo


@serde
class HomeScreenRelayCount:
    relay_count: str


@serde(tagging=Untagged)
class HomeResponse:
    message: str
    serial: str
    home_screen: List[
        Union[
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
        ]
    ]
