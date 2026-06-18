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


@unique
class IaquaHpmMode(StrEnum):
    HEAT = "heat"
    CHILL = "chill"


@unique
class IaquaHpmStatus(StrEnum):
    OFF = "off"
    ENABLED = "enabled"
    ON = "on"


@unique
class IaquaHpmErrorCode(StrEnum):
    EXCHANGER_PROTECTION_COOL = "1"
    EVAPORATOR_HIGH_TEMP_COOL = "2"
    PHASE_ORDER_FAULT = "3"
    COOLING_LOW_PRESSURE = "4"
    COOLING_HIGH_PRESSURE = "5"
    COMPRESSOR_DISCHARGE_TEMP_FAULT = "6"
    WATER_INLET_SENSOR_FAULT = "7"
    FLUID_LINE_SENSOR_FAULT = "8"
    DEFROST_SENSOR_FAULT = "9"
    AIR_INLET_SENSOR_FAULT = "10"
    COMPRESSOR_DISCHARGE_SENSOR_FAULT = "11"
    BOARD_COMMUNICATION_FAULT = "12"
    # "13" is genuinely absent from the reference implementation's error code
    # list (codes jump from "12" to "14") — not a documentation omission.
    ELECTRONIC_BOARD_OVERHEAT = "14"
    ELECTRICAL_NETWORK_PROTECTION = "15"
    FAN_MOTOR_ERROR = "16"
    COMPRESSOR_DRIVER_PROBLEM = "17"
    DRIVER_COMPRESSOR_COMM_ERROR = "18"
    MAIN_PCB_NOT_CONFIGURED = "19"
    UNRECOGNISED_CONFIG_FAULT = "20"
    UNKNOWN = "-1"


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
