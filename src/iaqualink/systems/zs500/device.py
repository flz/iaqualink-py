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
        return self.data["value"]

    @property
    def name(self) -> str:
        return self.data["type"]

    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Zs500", "")

    @classmethod
    def from_data(cls, system: Zs500System, data: DeviceData) -> Zs500Device:
        class_: type[Zs500Device]

        device_type = data["et"]
        if device_type == "HEAT_PUMP":
            class_ = Zs500Thermostat
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
        return (
            AqualinkState(self.state)
            in [AqualinkState.ON, AqualinkState.ENABLED, AqualinkState.PRESENT]
            if self.state
            else False
        )


class Zs500Switch(Zs500BinarySensor, AqualinkSwitch):
    async def _toggle(self) -> None:
        await self.system.set_switch(f"set_{self.name}")

    async def turn_on(self) -> None:
        if not self.is_on:
            await self._toggle()

    async def turn_off(self) -> None:
        if self.is_on:
            await self._toggle()

class Zs500Thermostat(Zs500Switch, AqualinkThermostat):
    @property
    def _type(self) -> str:
        return self.data["dt"]

    @property
    def unit(self) -> str:
        return self.system.temp_unit

    def _sensor(self, sensor_type: str) -> Zs500TemperatureSensor:
        for name, sensor in self.data.items():
            if not name.startswith("sns_"):
                continue
            if sensor["type"] != sensor_type:
                continue
            return Zs500TemperatureSensor(self.system, sensor)
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

    async def turn_on(self) -> None:
        if self.is_on is False:
            await self.system.set_device_property(self, 1, "state")

    async def turn_off(self) -> None:
        if self.is_on is True:
            await self.system.set_device_property(self, 0, "state")
