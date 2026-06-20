from __future__ import annotations

import logging
from enum import Enum, IntEnum, unique
from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkClimate,
    AqualinkDevice,
    AqualinkSelect,
    AqualinkSensor,
    AqualinkSwitch,
)

# DeviceData is dict[str, str] for the whole codebase even though the actual
# values on the wire are a JSON mix of str/int/dict — every system reads
# through str()/int()/float() casts rather than relying on the static type.
# See src/iaqualink/systems/i2d/device.py for the established convention.

if TYPE_CHECKING:
    from iaqualink.systems.zs500.system import Zs500System
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink.systems.zs500")

# Wire temperatures (tsp, sns_1.value, sns_2.value) are the actual value x10.
ZS500_TEMP_SCALE = 10
ZS500_TEMP_CELSIUS_LOW = 15
ZS500_TEMP_CELSIUS_HIGH = 32


@unique
class Zs500Mode(IntEnum):
    BOOST = 0
    SILENT = 1
    SMART = 2


@unique
class Zs500StandbyReason(Enum):
    """String-valued so it round-trips through AqualinkSensor.value (str)."""

    NONE = "0"
    NO_WATER_FLOW = "1"
    TEMP_OUT_OF_RANGE = "2"
    TEMPERATURE_BUFFER = "3"
    COOL_MODE_DISABLED = "4"
    DEFROSTING = "5"
    STARTING_OR_STOPPING = "6"
    REMOTE_CONTACT_OFF = "7"
    COMPRESSOR_BUFFER = "8"


class Zs500Device(AqualinkDevice):
    def __init__(self, system: Zs500System, data: DeviceData):
        super().__init__(system, data)

        # This silences mypy errors due to AqualinkDevice type annotations.
        self.system: Zs500System = system

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def label(self) -> str:
        return " ".join(x.capitalize() for x in self.name.split("_"))

    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Zs500", "")

    @classmethod
    def from_data(cls, system: Zs500System, data: DeviceData) -> Zs500Device:
        class_: type[Zs500Device]

        name = data["name"]
        if name == "climate":
            class_ = Zs500Climate
        elif name == "mode":
            class_ = Zs500ModeSelect
        elif name == "cooling":
            class_ = Zs500CoolingSwitch
        elif name == "heating_priority":
            class_ = Zs500HeatingPrioritySwitch
        elif name in ("water_temp", "air_temp"):
            class_ = Zs500TemperatureSensor
        elif name == "compressor_speed":
            class_ = Zs500CompressorSpeedSensor
        elif name == "standby_reason":
            class_ = Zs500StandbyReasonSensor
        elif name == "error":
            class_ = Zs500ErrorBinarySensor
        else:
            raise ValueError(f"Unknown zs500 device name: {name!r}")

        return class_(system, data)


class Zs500Climate(Zs500Device, AqualinkClimate):
    """The `hp_0` heat pump core — on/off, mode, and temperature control."""

    @property
    def is_on(self) -> bool:
        return int(self.data.get("state") or 0) > 0

    async def turn_on(self) -> None:
        if not self.is_on:
            # 1 = Standby; the device picks Heat/Cool on its own from there.
            await self.system.set_desired({"state": 1})

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_desired({"state": 0})

    @property
    def temperature_unit(self) -> str:
        return self.system.temp_unit

    @property
    def current_temperature(self) -> str | None:
        # Water temperature is reported as its own sibling device (sns_1) —
        # same cross-reference pattern as ExoClimate's sensor lookup.
        sensor = self.system.devices.get("water_temp")
        if isinstance(sensor, AqualinkSensor):
            return sensor.value
        return None

    @property
    def target_temperature(self) -> str | None:
        tsp = self.data.get("tsp")
        if tsp is None:
            return None
        return str(round(float(tsp) / ZS500_TEMP_SCALE, 1))

    @property
    def min_temp(self) -> int:
        return ZS500_TEMP_CELSIUS_LOW

    @property
    def max_temp(self) -> int:
        return ZS500_TEMP_CELSIUS_HIGH

    async def _set_temperature(self, temperature: int) -> None:
        await self.system.set_desired({"tsp": temperature * ZS500_TEMP_SCALE})


class Zs500ModeSelect(Zs500Device, AqualinkSelect):
    """Boost / Silent / Smart (`st`)."""

    @property
    def current_option(self) -> str | None:
        st = self.data.get("st")
        if st is None:
            return None
        try:
            return Zs500Mode(int(st)).name.capitalize()
        except ValueError:
            return None

    @property
    def options(self) -> list[str]:
        return [m.name.capitalize() for m in Zs500Mode]

    async def _select_option(self, option: str) -> None:
        mode = Zs500Mode[option.upper()]
        await self.system.set_desired({"st": mode.value})


class Zs500Switch(Zs500Device, AqualinkSwitch):
    """Abstract: a single boolean field under `hp_0`."""

    _field: str

    @property
    def is_on(self) -> bool:
        return int(self.data.get(self._field) or 0) > 0

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_desired({self._field: 1})

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_desired({self._field: 0})


class Zs500CoolingSwitch(Zs500Switch):
    _field = "cl"


class Zs500HeatingPrioritySwitch(Zs500Switch):
    _field = "hp"


class Zs500Sensor(Zs500Device, AqualinkSensor):
    """Abstract base for read-only hp_0-derived sensors."""


class Zs500TemperatureSensor(Zs500Sensor):
    @property
    def value(self) -> str:
        raw = self.data.get("value")
        if raw is None:
            return ""
        return str(round(float(raw) / ZS500_TEMP_SCALE, 1))

    @property
    def unit_of_measurement(self) -> str | None:
        return self.system.temp_unit


class Zs500CompressorSpeedSensor(Zs500Sensor):
    @property
    def value(self) -> str:
        return str(self.data.get("cmprSpd") or 0)

    @property
    def unit_of_measurement(self) -> str | None:
        return "%"


class Zs500StandbyReasonSensor(Zs500Sensor):
    @property
    def value(self) -> str:
        return str(self.data.get("reason") or 0)

    @property
    def value_enum(self) -> type[Enum] | None:
        return Zs500StandbyReason


class Zs500ErrorBinarySensor(Zs500Device, AqualinkBinarySensor):
    """True when `errorCode` is anything other than `"0"`."""

    @property
    def is_on(self) -> bool:
        return (self.data.get("errorCode") or "0") != "0"
