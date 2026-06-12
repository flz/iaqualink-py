from __future__ import annotations

from enum import IntEnum, StrEnum, unique


@unique
class SwcMode(IntEnum):
    STANDARD = 0
    LOW = 1
    BOOST = 2


@unique
class AuxApp(StrEnum):
    ON = "ON"
    UNUSED = "UNUSED"
    OTHER = "OTH"
    WATERFALL = "WF"
    POOL_LIGHT = "POOL_LT"
    CLEANER = "CLNR"


@unique
class LightType(StrEnum):
    JANDY_WATERCOLORS = "JL"
    PENTAIR_INTELLIBRITE = "IB"
    PENTAIR_SAM_SAL = "PSS"
    HAYWARD_COLORLOGIC = "HU"
    WHITE_LIGHT = "WL"


@unique
class WaterStatus(IntEnum):
    VALID = 1
    PUMP_OFF = 2
    LOADING = 3
    SENSOR_UNAVAILABLE_4 = 4
    SENSOR_UNAVAILABLE_5 = 5


@unique
class SolarStatus(IntEnum):
    PRESENT = 1
    OPEN_FAULT = 4
    SHORT_FAULT = 5
