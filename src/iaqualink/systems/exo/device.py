from __future__ import annotations

import logging
from enum import IntEnum, unique
from typing import TYPE_CHECKING, Any, cast

from iaqualink.device import (
    AqualinkClimate,
    AqualinkDevice,
    AqualinkSensor,
    AqualinkSwitch,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from iaqualink.systems.exo.system import ExoSystem
    from iaqualink.typing import DeviceData

EXO_TEMP_CELSIUS_LOW = 1
EXO_TEMP_CELSIUS_HIGH = 40

LOGGER = logging.getLogger("iaqualink.systems.exo")


@unique
class ExoState(IntEnum):
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

    # Internal property used by exo device logic; not part of the
    # AqualinkDevice public contract.
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
        class_: type[ExoDevice]

        if data["name"].startswith("aux_"):
            class_ = ExoAuxSwitch
        elif data["name"].startswith("sns_"):
            class_ = ExoSensor
        elif data["name"] == "heating":
            class_ = ExoClimate
        elif data["name"] == "heater":
            class_ = ExoHeater
        elif data["name"] in ["production", "boost", "low"]:
            class_ = ExoAttributeSwitch
        elif data["name"] == "filter_pump":
            class_ = ExoFilterPump
        elif data["name"] in ["error_code", "error_state"]:
            class_ = ExoErrorSensor
        else:
            class_ = ExoAttributeSensor

        return class_(system, data)


class ExoSensor(ExoDevice, AqualinkSensor):
    """These sensors are called sns_#."""

    @property
    def _is_active(self) -> bool:
        # Sensor liveness (state=0 absent/faulted, state=1 present/active) is
        # an EXO wire detail, not part of the AqualinkSensor public API.
        return self.data["state"] == ExoState.ON

    @property
    def value(self) -> str:
        if self._is_active:
            return str(self.data["value"])
        return ""

    @property
    def label(self) -> str:
        return self.data["sensor_type"]

    @property
    def name(self) -> str:
        # XXX: We're using the label as name rather than "sns_#".
        # Might revisit later.
        return self.data["sensor_type"].lower().replace(" ", "_")


class ExoAttributeSensor(ExoDevice, AqualinkSensor):
    """These sensors are a simple key/value in equipment->swc_0."""

    @property
    def value(self) -> str:
        return str(self.data["state"])


class ExoErrorSensor(ExoAttributeSensor):
    """Sensor for error_code and error_state diagnostic fields."""


# This is an abstract class, not to be instantiated directly.
class ExoSwitch(ExoDevice, AqualinkSwitch):
    @property
    def label(self) -> str:
        return self.name.replace("_", " ").capitalize()

    @property
    def is_on(self) -> bool:
        return self.data["state"] == ExoState.ON

    @property
    def _command(self) -> Callable[[str, int], Coroutine[Any, Any, None]]:
        raise NotImplementedError

    async def turn_on(self) -> None:
        if not self.is_on:
            await self._command(self.name, 1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self._command(self.name, 0)


class ExoAuxSwitch(ExoSwitch):
    @property
    def _command(self) -> Callable[[str, int], Coroutine[Any, Any, None]]:
        return self.system.set_aux


class ExoFilterPump(ExoSwitch):
    @property
    def _command(self) -> Callable[[str, int], Coroutine[Any, Any, None]]:
        return self.system.set_filter_pump


class ExoAttributeSwitch(ExoSwitch):
    @property
    def _command(self) -> Callable[[str, int], Coroutine[Any, Any, None]]:
        return self.system.set_toggle


class ExoHeater(ExoDevice):
    """This device is to separate the state of the heater from the climate to maintain the existing homeassistant API"""


class ExoClimate(ExoSwitch, AqualinkClimate):
    # Internal: the set-point stored in data["sp"]; not the AqualinkClimate.value
    @property
    def state(self) -> str:
        return str(self.data["sp"])

    @property
    def temperature_unit(self) -> str:
        return "C"

    @property
    def _sensor(self) -> ExoSensor:
        return cast(ExoSensor, self.system.devices["sns_3"])

    @property
    def _heater(self) -> ExoHeater:
        return cast(ExoHeater, self.system.devices["heater"])

    @property
    def current_temperature(self) -> str:
        return self._sensor.value

    @property
    def target_temperature(self) -> str:
        return str(self.data["sp"])

    @property
    def min_temp(self) -> int:
        return int(self.data["sp_min"])

    @property
    def max_temp(self) -> int:
        return int(self.data["sp_max"])

    async def _set_temperature(self, temperature: int) -> None:
        await self.system.set_heating("sp", temperature)

    @property
    def is_on(self) -> bool:
        return self.data["enabled"] == ExoState.ON

    async def turn_on(self) -> None:
        if self.is_on is False:
            await self.system.set_heating("enabled", 1)

    async def turn_off(self) -> None:
        if self.is_on is True:
            await self.system.set_heating("enabled", 0)
