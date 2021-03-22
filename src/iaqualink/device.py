from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from typing import TYPE_CHECKING, Dict, Optional, Type

from iaqualink.const import (
    AQUALINK_TEMP_CELSIUS_HIGH,
    AQUALINK_TEMP_CELSIUS_LOW,
    AQUALINK_TEMP_FAHRENHEIT_HIGH,
    AQUALINK_TEMP_FAHRENHEIT_LOW,
)
from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.typing import DeviceData

if TYPE_CHECKING:
    from iaqualink.system import AqualinkSystem


@unique
class AqualinkState(Enum):
    OFF = "0"
    ON = "1"
    ENABLED = "3"


@dataclass
class AqualinkLightType:
    # The name as displayed in the System Setup Web UI as big buttons.
    display_name: str
    # The name as displayed in the System Setup Web UI next to the Aux list.
    short_name: str
    # The subtype value returned by the API and sent to the API.
    subtype: int
    # Maps effect_name -> effect_number.
    effects: Dict[str, str]


# Maps subtype (as string) to AqualinkLightType.
# These are listed here in the same order as in the System Setup Web UI.
# There is no subtype "3" in the REV T.2 firmware.
# The effect_name to effect_number mappings seem to be hardcoded into the iOS
# app as well.
LIGHT_TYPES_BY_SUBTYPE_STR = {
    "4": AqualinkLightType(
        "Jandy LED WaterColors",
        "JL",
        4,
        {
            "Off": "0",
            "Alpine White": "1",
            "Sky Blue": "2",
            "Cobalt Blue": "3",
            "Caribbean Blue": "4",
            "Spring Green": "5",
            "Emerald Green": "6",
            "Emerald Rose": "7",
            "Magenta": "8",
            "Violet": "9",
            "Slow Splash": "10",
            "Fast Splash": "11",
            "USA!!!": "12",
            "Fat Tuesday": "13",
            "Disco Tech": "14",
        },
    ),
    "5": AqualinkLightType(
        "Pentair IntelliBrite",
        "IB",
        5,
        {
            "Off": "0",
            "SAm": "1",
            "Party": "2",
            "Romance": "3",
            "Caribbean": "4",
            "American": "5",
            "Cal Sunset": "6",
            "Royal": "7",
            "Blue": "8",
            "Green": "9",
            "Red": "10",
            "White": "11",
            "Magenta": "12",
        },
    ),
    "6": AqualinkLightType(
        "Hayward Universal",
        "HU",
        6,
        {
            "Off": "0",
            "Voodoo Lounge": "1",
            "Deep Blue Sea": "2",
            "Royal Blue": "3",
            "Afternoon Skies": "4",
            "Aqua Green": "5",
            "Emerald": "6",
            "Cloud White": "7",
            "Warm Red": "8",
            "Flamingo": "9",
            "Vivid Violet": "10",
            "Sangria": "11",
            "Twilight": "12",
            "Tranquility": "13",
            "Gemstone": "14",
            "USA": "15",
        },
    ),
    "1": AqualinkLightType(
        "JandyColors",
        "JC",
        1,
        {
            "Off": "0",
            "Alpine White": "1",
            "Sky Blue": "2",
            "Cobalt Blue": "3",
            "Caribbean Blue": "4",
            "Spring Green": "5",
            "Emerald Green": "6",
            "Emerald Rose": "7",
            "Magenta": "8",
            "Garnet Red": "9",
            "Violet": "10",
            "Color Splash": "11",
        },
    ),
    "2": AqualinkLightType(
        "Pentair SAm/SAL",
        "SL",
        2,
        {
            "Off": "0",
            "White": "1",
            "Light Green": "2",
            "Green": "3",
            "Cyan": "4",
            "Blue": "5",
            "Lavender": "6",
            "Magenta": "7",
            "Light Magenta": "8",
            "Color Splash": "9",
        },
    ),
}


def light_type_from_subtype(subtype: str) -> AqualinkLightType:
    return LIGHT_TYPES_BY_SUBTYPE_STR[subtype]


LOGGER = logging.getLogger("iaqualink")


class AqualinkDevice:
    def __init__(self, system: AqualinkSystem, data: DeviceData):
        self.system = system
        self.data = data

    def __repr__(self) -> str:
        attrs = ["data"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return f'{self.__class__.__name__}({", ".join(attrs)})'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AqualinkDevice):
            return NotImplemented

        if (
            self.system.serial == other.system.serial
            and self.data == other.data
        ):
            return True
        return False

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

    @classmethod
    def from_data(
        cls, system: AqualinkSystem, data: DeviceData
    ) -> AqualinkDevice:
        class_: Type[AqualinkDevice]

        if data["name"].endswith("_heater"):
            class_ = AqualinkHeater
        elif data["name"].endswith("_set_point"):
            class_ = AqualinkThermostat
        elif data["name"].endswith("_pump"):
            class_ = AqualinkPump
        elif data["name"] == "freeze_protection":
            class_ = AqualinkBinarySensor
        elif data["name"].startswith("aux_"):
            if data["type"] == "2":
                class_ = AqualinkColorLight
            elif data["type"] == "1":
                class_ = AqualinkDimmableLight
            elif "LIGHT" in data["label"]:
                class_ = AqualinkLightToggle
            else:
                class_ = AqualinkAuxToggle
        else:
            class_ = AqualinkSensor

        return class_(system, data)


class AqualinkSensor(AqualinkDevice):
    pass


class AqualinkBinarySensor(AqualinkSensor):
    """These are non-actionable sensors, essentially read-only on/off."""

    @property
    def is_on(self) -> bool:
        return (
            AqualinkState(self.state)
            in [AqualinkState.ON, AqualinkState.ENABLED]
            if self.state
            else False
        )


class AqualinkToggle(AqualinkDevice):
    @property
    def is_on(self) -> bool:
        return (
            AqualinkState(self.state)
            in [AqualinkState.ON, AqualinkState.ENABLED]
            if self.state
            else False
        )

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.toggle()

    async def turn_off(self) -> None:
        if self.is_on:
            await self.toggle()

    async def toggle(self) -> None:
        raise NotImplementedError()


class AqualinkPump(AqualinkToggle):
    async def toggle(self) -> None:
        await self.system.set_pump(f"set_{self.name}")


class AqualinkHeater(AqualinkToggle):
    async def toggle(self) -> None:
        await self.system.set_heater(f"set_{self.name}")


class AqualinkAuxToggle(AqualinkToggle):
    async def toggle(self) -> None:
        await self.system.set_aux(self.data["aux"])


# Using AqualinkLight as a Mixin so we can use isinstance(dev, AqualinkLight).
class AqualinkLight:
    @property
    def brightness(self) -> Optional[int]:
        raise NotImplementedError()

    @property
    def effect(self) -> Optional[str]:
        raise NotImplementedError()

    @property
    def is_dimmer(self) -> bool:
        return self.brightness is not None

    @property
    def is_color(self) -> bool:
        return self.effect is not None


class AqualinkLightToggle(AqualinkLight, AqualinkAuxToggle):
    @property
    def brightness(self) -> Optional[bool]:
        return None

    @property
    def effect(self) -> Optional[str]:
        return None


class AqualinkDimmableLight(AqualinkLight, AqualinkDevice):
    @property
    def brightness(self) -> Optional[int]:
        return int(self.data["subtype"])

    @property
    def effect(self) -> Optional[str]:
        return None

    @property
    def is_on(self) -> bool:
        return self.brightness != 0

    async def set_brightness(self, brightness: int) -> None:
        # Brightness only works in 25% increments.
        if brightness not in [0, 25, 50, 75, 100]:
            msg = f"{brightness}% isn't a valid percentage."
            msg += " Only use 25% increments."
            raise Exception(msg)

        data = {"aux": self.data["aux"], "light": f"{brightness}"}
        await self.system.set_light(data)

    async def turn_on(self, level: int = 100) -> None:
        if self.brightness != level:
            await self.set_brightness(level)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.set_brightness(0)


class AqualinkColorLight(AqualinkLight, AqualinkDevice):
    @property
    def brightness(self) -> Optional[int]:
        # Assuming that color lights don't have adjustable brightness.
        return None

    @property
    def effect_num(self) -> Optional[str]:
        # "state"=0 indicates the light is off.
        # "state"=1 indicates the light is on.
        # I don't see a way to retrieve the current color.
        # The official iAquaLink app doesn't seem to show the current color
        # choice either, so perhaps it's an unfortunate limitation of the
        # current API.
        return self.data["state"]

    @property
    def effect(self) -> Optional[str]:
        # Ideally, this would return the effect name.
        # However, the API seems to return "state"=1 no matter what effect is
        # currently chosen.
        # Workaround: instead of returning a possibly incorrect effect name,
        # we'll just return "On".
        return "On" if self.is_on else "Off"

    @property
    def is_on(self) -> bool:
        return self.effect_num != "0"

    @property
    def supported_light_effects(self) -> Dict[str, str]:
        return light_type_from_subtype(self.data["subtype"]).effects

    async def set_effect_by_name(self, effect_name: str) -> None:
        try:
            effect_num = self.supported_light_effects[effect_name]
        except IndexError as e:
            msg = f"{repr(effect_name)} isn't a valid effect."
            raise AqualinkInvalidParameterException(msg) from e
        await self.set_effect_by_num(effect_num)

    async def set_effect_by_num(self, effect_num: str) -> None:
        data = {
            "aux": self.data["aux"],
            "light": effect_num,
            "subtype": self.data["subtype"],
        }
        await self.system.set_light(data)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.set_effect_by_num("0")

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.set_effect_by_num("1")


class AqualinkThermostat(AqualinkDevice):
    @property
    def temp(self) -> str:
        # Spa takes precedence for temp1 if present.
        if self.name.startswith("pool") and self.system.has_spa:
            return "temp2"
        return "temp1"

    async def set_temperature(self, temperature: int) -> None:
        unit = self.system.temp_unit

        if unit == "F":
            low = AQUALINK_TEMP_FAHRENHEIT_LOW
            high = AQUALINK_TEMP_FAHRENHEIT_HIGH
        else:
            low = AQUALINK_TEMP_CELSIUS_LOW
            high = AQUALINK_TEMP_CELSIUS_HIGH

        if temperature not in range(low, high + 1):
            msg = f"{temperature}{unit} isn't a valid temperature"
            msg += f" ({low}-{high}{unit})."
            raise Exception(msg)

        data = {self.temp: str(temperature)}
        await self.system.set_temps(data)
