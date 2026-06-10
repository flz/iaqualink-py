from __future__ import annotations

from enum import StrEnum, unique


@unique
class IaquaSystemType(StrEnum):
    SPA_AND_POOL = "0"  # single pump shared by both spa and pool
    POOL_ONLY = "1"
    DUAL = "2"  # two separate pumps, one per body of water


@unique
class IaquaSystemStatus(StrEnum):
    ONLINE = "Online"
    OFFLINE = "Offline"
    SERVICE = "Service"
    UNKNOWN = "Unknown"


@unique
class IaquaTemperatureUnit(StrEnum):
    FAHRENHEIT = "F"
    CELSIUS = "C"


# Wire values for the `boostStatus` field in get_swc_config responses.
@unique
class IaquaBoostStatus(StrEnum):
    ON = "on"
    PAUSED = "paused"
    OFF = ""  # absent or empty string when boost is not running


@unique
class IaquaBoostMode(StrEnum):
    POOL = "pool"
    SPILLOVER = "spillover"


@unique
class IaquaBoostControl(StrEnum):
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"


# Wire values for swcPoolStatus/swcSpaStatus fields in get_home's swc_info object.
@unique
class IaquaSwcStatus(StrEnum):
    STANDBY = "standby"
    RUNNING = "running"
    BOOSTING = "boosting"
    BOOST_PAUSED = "boostpaused"
