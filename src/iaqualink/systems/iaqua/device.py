from __future__ import annotations

import logging
from enum import Enum, unique
from typing import TYPE_CHECKING, cast

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkLight,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)
from iaqualink.exception import (
    AqualinkDeviceNotSupported,
    AqualinkInvalidParameterException,
)

if TYPE_CHECKING:
    from iaqualink.systems.iaqua.system import IaquaSystem
    from iaqualink.typing import DeviceData

IAQUA_TEMP_CELSIUS_LOW = 1
IAQUA_TEMP_CELSIUS_HIGH = 40
IAQUA_TEMP_FAHRENHEIT_LOW = 32
IAQUA_TEMP_FAHRENHEIT_HIGH = 104

LOGGER = logging.getLogger("iaqualink")


@unique
class AqualinkState(Enum):
    OFF = "0"
    ON = "1"
    STANDBY = "2"
    ENABLED = "3"
    ABSENT = "absent"
    PRESENT = "present"


class IaquaDevice(AqualinkDevice):
    def __init__(self, system: IaquaSystem, data: DeviceData):
        super().__init__(system, data)

        # This silences mypy errors due to AqualinkDevice type annotations.
        self.system: IaquaSystem = system

    @property
    def label(self) -> str:
        if "label" in self.data:
            label = self.data["label"]
            return " ".join([x.capitalize() for x in label.split()])

        label = self.data["name"]
        return " ".join([x.capitalize() for x in label.split("_")])

    @property
    def state(self) -> str:
        return self.data["state"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def manufacturer(self) -> str:
        return "Jandy"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Iaqua", "")

    @classmethod
    def from_data(cls, system: IaquaSystem, data: DeviceData) -> IaquaDevice:
        class_: type[IaquaDevice]

        # I don't have a system where these fields get populated.
        # No idea what they are and what to do with them.
        if isinstance(data["state"], dict | list):
            raise AqualinkDeviceNotSupported(data)

        if data["name"].endswith("_heater") or data["name"].endswith("_pump"):
            class_ = IaquaSwitch
        elif data["name"].endswith("_set_point"):
            if data["state"] == "":
                raise AqualinkDeviceNotSupported(data)
            class_ = IaquaThermostat
        elif data["name"] == "freeze_protection" or data["name"].endswith(
            "_present"
        ):
            class_ = IaquaBinarySensor
        elif data["name"].startswith("aux_"):
            if data["type"] == "2":
                class_ = light_subtype_to_class[data["subtype"]]
            elif data["type"] == "1":
                class_ = IaquaDimmableLight
            elif "LIGHT" in data["label"]:
                class_ = IaquaLightSwitch
            else:
                class_ = IaquaAuxSwitch
        else:
            class_ = IaquaSensor

        return class_(system, data)


class IaquaSensor(IaquaDevice, AqualinkSensor):
    pass


class IaquaBinarySensor(IaquaSensor, AqualinkBinarySensor):
    """These are non-actionable sensors, essentially read-only on/off."""

    @property
    def is_on(self) -> bool:
        return (
            AqualinkState(self.state)
            in [AqualinkState.ON, AqualinkState.ENABLED, AqualinkState.PRESENT]
            if self.state
            else False
        )


class IaquaSwitch(IaquaBinarySensor, AqualinkSwitch):
    async def _toggle(self) -> None:
        await self.system.set_switch(f"set_{self.name}")

    async def turn_on(self) -> None:
        if not self.is_on:
            await self._toggle()

    async def turn_off(self) -> None:
        if self.is_on:
            await self._toggle()


class IaquaAuxSwitch(IaquaSwitch):
    @property
    def is_on(self) -> bool:
        return (
            AqualinkState(self.state) == AqualinkState.ON
            if self.state
            else False
        )

    async def _toggle(self) -> None:
        await self.system.set_aux(self.data["aux"])


class IaquaLightSwitch(IaquaAuxSwitch, AqualinkLight):
    pass


class IaquaDimmableLight(IaquaAuxSwitch, AqualinkLight):
    async def turn_on(self) -> None:
        if not self.is_on:
            await self.set_brightness(100)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.set_brightness(0)

    @property
    def brightness(self) -> int | None:
        return int(self.data["subtype"])

    async def set_brightness(self, brightness: int) -> None:
        # Brightness only works in 25% increments.
        if brightness not in [0, 25, 50, 75, 100]:
            msg = f"{brightness}% isn't a valid percentage."
            msg += " Only use 25% increments."
            raise AqualinkInvalidParameterException(msg)

        data = {"aux": self.data["aux"], "light": f"{brightness}"}
        await self.system.set_light(data)


class IaquaColorLight(IaquaAuxSwitch, AqualinkLight):
    async def turn_on(self) -> None:
        if not self.is_on:
            await self.set_effect_by_id(1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.set_effect_by_id(0)

    @property
    def effect(self) -> str | None:
        # "state"=0 indicates the light is off.
        # "state"=1 indicates the light is on.
        # I don't see a way to retrieve the current effect.
        # The official iAquaLink app doesn't seem to show the current effect
        # choice either, so perhaps it's an unfortunate limitation of the
        # current API.
        return self.data["state"]

    @property
    def supported_effects(self) -> dict[str, int]:
        raise NotImplementedError

    async def set_effect_by_name(self, effect: str) -> None:
        try:
            effect_id = self.supported_effects[effect]
        except KeyError as e:
            msg = f"{effect!r} isn't a valid effect."
            raise AqualinkInvalidParameterException(msg) from e
        await self.set_effect_by_id(effect_id)

    async def set_effect_by_id(self, effect_id: int) -> None:
        try:
            _ = list(self.supported_effects.values()).index(effect_id)
        except ValueError as e:
            msg = f"{effect_id!r} isn't a valid effect."
            raise AqualinkInvalidParameterException(msg) from e

        data = {
            "aux": self.data["aux"],
            "light": str(effect_id),
            "subtype": self.data["subtype"],
        }
        await self.system.set_light(data)


class IaquaColorLightJC(IaquaColorLight):
    @property
    def manufacturer(self) -> str:
        return "Jandy"

    @property
    def model(self) -> str:
        return "Colors Light"

    @property
    def supported_effects(self) -> dict[str, int]:
        return {
            "Off": 0,
            "Alpine White": 1,
            "Sky Blue": 2,
            "Cobalt Blue": 3,
            "Caribbean Blue": 4,
            "Spring Green": 5,
            "Emerald Green": 6,
            "Emerald Rose": 7,
            "Magenta": 8,
            "Garnet Red": 9,
            "Violet": 10,
            "Color Splash": 11,
        }


class IaquaColorLightSL(IaquaColorLight):
    @property
    def manufacturer(self) -> str:
        return "Pentair"

    @property
    def model(self) -> str:
        return "SAm/SAL Light"

    @property
    def supported_effects(self) -> dict[str, int]:
        return {
            "Off": 0,
            "White": 1,
            "Light Green": 2,
            "Green": 3,
            "Cyan": 4,
            "Blue": 5,
            "Lavender": 6,
            "Magenta": 7,
            "Light Magenta": 8,
            "Color Splash": 9,
        }


class IaquaColorLightJL(IaquaColorLight):
    @property
    def manufacturer(self) -> str:
        return "Jandy"

    @property
    def model(self) -> str:
        return "LED WaterColors Light"

    @property
    def supported_effects(self) -> dict[str, int]:
        return {
            "Off": 0,
            "Alpine White": 1,
            "Sky Blue": 2,
            "Cobalt Blue": 3,
            "Caribbean Blue": 4,
            "Spring Green": 5,
            "Emerald Green": 6,
            "Emerald Rose": 7,
            "Magenta": 8,
            "Violet": 9,
            "Slow Splash": 10,
            "Fast Splash": 11,
            "USA!!!": 12,
            "Fat Tuesday": 13,
            "Disco Tech": 14,
        }


class IaquaColorLightIB(IaquaColorLight):
    @property
    def manufacturer(self) -> str:
        return "Pentair"

    @property
    def model(self) -> str:
        return "Intellibrite Light"

    @property
    def supported_effects(self) -> dict[str, int]:
        return {
            "Off": 0,
            "SAm": 1,
            "Party": 2,
            "Romance": 3,
            "Caribbean": 4,
            "American": 5,
            "Cal Sunset": 6,
            "Royal": 7,
            "Blue": 8,
            "Green": 9,
            "Red": 10,
            "White": 11,
            "Magenta": 12,
        }


class IaquaColorLightHU(IaquaColorLight):
    @property
    def manufacturer(self) -> str:
        return "Hayward"

    @property
    def model(self) -> str:
        return "Universal Light"

    @property
    def supported_effects(self) -> dict[str, int]:
        return {
            "Off": 0,
            "Voodoo Lounge": 1,
            "Deep Blue Sea": 2,
            "Royal Blue": 3,
            "Afternoon Skies": 4,
            "Aqua Green": 5,
            "Emerald": 6,
            "Cloud White": 7,
            "Warm Red": 8,
            "Flamingo": 9,
            "Vivid Violet": 10,
            "Sangria": 11,
            "Twilight": 12,
            "Tranquility": 13,
            "Gemstone": 14,
            "USA": 15,
        }


light_subtype_to_class = {
    "1": IaquaColorLightJC,
    "2": IaquaColorLightSL,
    "4": IaquaColorLightJL,
    "5": IaquaColorLightIB,
    "6": IaquaColorLightHU,
}


class IaquaThermostat(IaquaSwitch, AqualinkThermostat):
    @property
    def _type(self) -> str:
        return self.name.split("_")[0]

    @property
    def _temperature(self) -> str:
        # Spa takes precedence for temp1 if present.
        if self._type == "pool" and "spa_set_point" in self.system.devices:
            return "temp2"
        return "temp1"

    @property
    def unit(self) -> str:
        return self.system.temp_unit

    @property
    def _sensor(self) -> IaquaSensor:
        return cast(IaquaSensor, self.system.devices[f"{self._type}_temp"])

    @property
    def current_temperature(self) -> str:
        return self._sensor.state

    @property
    def target_temperature(self) -> str:
        return self.state

    @property
    def min_temperature(self) -> int:
        if self.unit == "F":
            return IAQUA_TEMP_FAHRENHEIT_LOW
        return IAQUA_TEMP_CELSIUS_LOW

    @property
    def max_temperature(self) -> int:
        if self.unit == "F":
            return IAQUA_TEMP_FAHRENHEIT_HIGH
        return IAQUA_TEMP_CELSIUS_HIGH

    async def set_temperature(self, temperature: int) -> None:
        unit = self.unit
        low = self.min_temperature
        high = self.max_temperature

        if temperature not in range(low, high + 1):
            msg = f"{temperature}{unit} isn't a valid temperature"
            msg += f" ({low}-{high}{unit})."
            raise AqualinkInvalidParameterException(msg)

        data = {self._temperature: str(temperature)}
        await self.system.set_temps(data)

    @property
    def _heater(self) -> IaquaSwitch:
        return cast(IaquaSwitch, self.system.devices[f"{self._type}_heater"])

    @property
    def is_on(self) -> bool:
        return self._heater.is_on

    async def turn_on(self) -> None:
        if self._heater.is_on is False:
            await self._heater.turn_on()

    async def turn_off(self) -> None:
        if self._heater.is_on is True:
            await self._heater.turn_off()
