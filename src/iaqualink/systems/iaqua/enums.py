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
