from __future__ import annotations

import logging
from enum import Enum, unique
from typing import TYPE_CHECKING, Type

from iaqualink.device import (
    AqualinkDevice,
    AqualinkSensor,
    AqualinkThermostat,
    AqualinkToggle,
)
from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.typing import DeviceData

if TYPE_CHECKING:
    from iaqualink.systems.exo.system import ExoSystem

EXO_TEMP_CELSIUS_LOW = 1
EXO_TEMP_CELSIUS_HIGH = 40

LOGGER = logging.getLogger("iaqualink")


@unique
class ExoState(Enum):
    OFF = 0
    ON = 1


class ExoDevice(AqualinkDevice):
    def __init__(self, system: ExoSystem, data: DeviceData):
        super().__init__(system, data)

        # This silences mypy errors due to AqualinkDevice type annotations.
        self.system: ExoSystem = system

    @property
    def label(self) -> str:
        name = self.name
        return " ".join([x.capitalize() for x in name.split("_")])

    @property
    def state(self) -> str:
        return str(self.data["state"])

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Exo", "")

    @classmethod
    def from_data(cls, system: ExoSystem, data: DeviceData) -> ExoDevice:
        class_: Type[ExoDevice]

        if data["name"].startswith("aux_"):
            class_ = ExoAuxToggle
        elif data["name"].startswith("sns_"):
            class_ = ExoSensor
        elif data["name"] == "heating":
            class_ = ExoThermostat
        elif data["name"] in ["production", "boost", "low"]:
            class_ = ExoAttributeToggle
        else:
            class_ = ExoAttributeSensor

        return class_(system, data)


class ExoSensor(ExoDevice, AqualinkSensor):
    """These sensors are called sns_#."""

    @property
    def is_on(self) -> bool:
        return ExoState(self.data["state"]) == ExoState.ON

    @property
    def state(self) -> str:
        if self.is_on:
            return str(self.data["value"])
        return ""

    @property
    def label(self) -> str:
        return self.data["sensor_type"]

    @property
    def name(self) -> str:
        # XXX - We're using the label as name rather than "sns_#".
        # Might revisit later.
        return self.data["sensor_type"].lower().replace(" ", "_")


class ExoAttributeSensor(ExoDevice, AqualinkSensor):
    """These sensors are a simple key/value in equipment->swc_0."""

    pass


class ExoThermostat(ExoDevice, AqualinkThermostat):
    @property
    def state(self) -> int:
        return str(self.data["sp"])

    @property
    def unit(self) -> str:
        return "C"

    @property
    def min_temperature(self) -> int:
        return self.data["sp_min"]

    @property
    def max_temperature(self) -> int:
        return self.data["sp_max"]

    async def set_temperature(self, temperature: int) -> None:
        unit = self.unit
        low = self.min_temperature
        high = self.max_temperature

        if temperature not in range(low, high + 1):
            msg = f"{temperature}{unit} isn't a valid temperature"
            msg += f" ({low}-{high}{unit})."
            raise AqualinkInvalidParameterException(msg)

        await self.system.set_temps(str(temperature))


class ExoToggle(ExoDevice, AqualinkToggle):
    @property
    def label(self) -> str:
        return self.name.replace("_", " ").capitalize()

    @property
    def is_on(self) -> bool:
        return ExoState(self.data["state"]) == ExoState.ON

    async def toggle(self) -> None:
        raise NotImplementedError()


class ExoAuxToggle(ExoToggle):
    async def toggle(self) -> None:
        new_state = 1 - int(self.state)
        await self.system.set_aux(self.name, new_state)


class ExoAttributeToggle(ExoToggle):
    async def toggle(self) -> None:
        new_state = 1 - int(self.state)
        await self.system.set_toggle(self.name, new_state)
