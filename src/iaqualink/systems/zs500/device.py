from __future__ import annotations

import logging
from enum import Enum, unique
from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)
from iaqualink.exception import (
    AqualinkDeviceNotSupported,
    AqualinkInvalidParameterException,
)

if TYPE_CHECKING:
    from iaqualink.systems.iaqua.system import Zs500System
    from iaqualink.typing import DeviceData

ZS500_TEMP_SCALE = 0.1
ZS500_TEMP_CELSIUS_LOW = 15
ZS500_TEMP_CELSIUS_HIGH = 32

LOGGER = logging.getLogger("iaqualink")

@unique
class AqualinkState(Enum):
    OFF = "0"
    ON = "1"
    ENABLED = "3"
    ABSENT = "absent"
    PRESENT = "present"


class Zs500Device(AqualinkDevice):
    def __init__(self, system: Zs500System, data: DeviceData):
        super().__init__(system, data)

        # This silences mypy errors due to AqualinkDevice type annotations.
        self.system: Zs500System = system

    @property
    def label(self) -> str:
        if "label" in self.data:
            label = self.data["label"]
            return " ".join([x.capitalize() for x in label.split()])

        label = self.name
        return " ".join([x.capitalize() for x in label.split("_")])

    @property
    def state(self) -> str:
        if "value" in self.data:
            return self.data["value"]

        if "state" in self.data:
            return self.data["state"]

        return None

    @property
    def name(self) -> str:
        et = self.data["et"].lower()
        return " ".join([x.capitalize() for x in et.split('_')])


    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Zs500", "")

    @classmethod
    def from_data(cls, system: Zs500System, data: DeviceData) -> Zs500Device:
        class_: type[Zs500Device]

        if not "et" in data:
            raise AqualinkDeviceNotSupported(data)

        device_type = data["et"]
        if device_type == "HEAT_PUMP":
            class_ = Zs500Thermostat
        elif device_type == "AIR_SENSOR":
            class_ = Zs500TemperatureSensor
        elif device_type == "WATER_SENSOR":
            class_ = Zs500TemperatureSensor
        elif device_type == "_SENSOR":
            class_ = Zs500Sensor
        elif device_type == "_BINARY_SENSOR":
            class_ = Zs500BinarySensor
        elif device_type == "_SWITCH":
            class_ = Zs500Switch
        else:
            raise AqualinkDeviceNotSupported(data)

        return class_(system, data)


class Zs500Sensor(Zs500Device, AqualinkSensor):
    pass

class Zs500TemperatureSensor(Zs500Sensor):

    @property
    def state(self) -> str:
        return round(self.data["value"] * ZS500_TEMP_SCALE, 1)


class Zs500BinarySensor(Zs500Sensor, AqualinkBinarySensor):
    """These are non-actionable sensors, essentially read-only on/off."""

    @property
    def is_on(self) -> bool:
        if isinstance(self.state, int):
            return self.state > 0

        return (
            AqualinkState(self.state)
            in [AqualinkState.ON, AqualinkState.ENABLED, AqualinkState.PRESENT]
            if self.state
            else False
        )


class Zs500Switch(Zs500BinarySensor, AqualinkSwitch):
    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_device_property(self, 0, "state")

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_device_property(self, 1, "state")

class Zs500Thermostat(Zs500Switch, AqualinkThermostat):
    @property
    def _type(self) -> str:
        return self.data["dt"]

    @property
    def unit(self) -> str:
        return self.system.temp_unit

    @property
    def state(self) -> float:
        return self.current_temperature

    def _sensor(self, sensor_type: str) -> Zs500TemperatureSensor:
        for name, sensor in self.data.items():
            if not name.startswith("sns_"):
                continue
            if sensor["type"] != sensor_type:
                continue

            sensor_data = {
                "et": sensor["type"].upper() + "_SENSOR",
                **sensor,
            }
            return Zs500Device.from_data(self.system, sensor_data)
        raise AqualinkDeviceNotSupported

    @property
    def _air_sensor(self) -> Zs500TemperatureSensor:
        return self._sensor("air")

    @property
    def _water_sensor(self) -> Zs500TemperatureSensor:
        return self._sensor("water")

    @property
    def air_temperature(self) -> str:
        return self._air_sensor.state

    @property
    def current_temperature(self) -> str:
        return self._water_sensor.state

    @property
    def target_temperature(self) -> str:
        return round(self.data["tsp"] * ZS500_TEMP_SCALE, 1)

    @property
    def min_temperature(self) -> int:
        return ZS500_TEMP_CELSIUS_LOW

    @property
    def max_temperature(self) -> int:
        return ZS500_TEMP_CELSIUS_HIGH

    async def set_temperature(self, temperature: int) -> None:
        unit = self.unit
        low = self.min_temperature
        high = self.max_temperature

        if temperature > high or temperature < low:
            msg = f"{temperature}{unit} isn't a valid temperature"
            msg += f" ({low}-{high}{unit})."
            raise AqualinkInvalidParameterException(msg)

        value = round(temperature * 10)
        await self.system.set_device_property(self, value, "tsp")

    @property
    def is_cooling_mode_on(self) -> bool:
        return self.data["cl"] > 0

    async def turn_on_cooling_mode(self) -> None:
        await self.system.set_device_property(self, 1, "cl")

    async def turn_off_cooling_mode(self) -> None:
        await self.system.set_device_property(self, 0, "cl")

    @property
    def is_on(self) -> bool:
        return self.data["state"] > 0
