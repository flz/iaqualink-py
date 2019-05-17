from enum import Enum, auto, unique
import logging
from typing import Optional

from iaqualink.typing import DeviceData


@unique
class AqualinkState(Enum):
    OFF = "0"
    ON = "1"
    ENABLED = "3"


# XXX - I don't know the exact values per type. The enum is pretty much a
# placeholder. If you know what type of lights you have and have debugging
# on, please submit an issue to GitHub with the details so I can update the
# code.
@unique
class AqualinkLightType(Enum):
    JANDY_LED_WATERCOLORS = auto()
    JANDY_COLORS = auto()
    HAYWARD_COLOR_LOGIC = auto()
    PENTAIR_INTELLIBRITE = auto()
    PENTAIR_SAM_SAL = auto()


# XXX - These values are probably LightType-specific but they're all I have
# at the moment. I can see this changing into a color profile system later.
class AqualinkLightEffect(Enum):
    NONE = "0"
    ALPINE_WHITE = "1"
    SKY_BLUE = "2"
    COBALT_BLUE = "3"
    CARIBBEAN_BLUE = "4"
    SPRING_GREEN = "5"
    EMERALD_GREEN = "6"
    EMERALD_ROSE = "7"
    MAGENTA = "8"
    VIOLENT = "9"
    SLOW_COLOR_SPLASH = "10"
    FAST_COLOR_SPLASH = "11"
    USA = "12"
    FAT_TUESDAY = "13"
    DISCO_TECH = "14"


LOGGER = logging.getLogger("aqualink")


class AqualinkDevice(object):
    def __init__(self, system: "AqualinkSystem", data: "DeviceData"):
        self.system = system
        self.data = data

    def __repr__(self) -> str:
        attrs = ["name", "data"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return f'{self.__class__.__name__}({" ".join(attrs)})'

    @property
    def label(self) -> str:
        if "label" in self.data:
            label = self.data["label"]
            return " ".join([x.capitalize() for x in label.split()])
        else:
            label = self.data["name"]
            return " ".join([x.capitalize() for x in label.split("_")])

    @property
    def state(self) -> str:
        return self.data["state"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @classmethod
    def from_data(cls, system: "AqualinkSystem", data: DeviceData) -> "AqualinkDevice":
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
            AqualinkState(self.state) in [AqualinkState.ON, AqualinkState.ENABLED]
            if self.state
            else False
        )


class AqualinkToggle(AqualinkDevice):
    @property
    def is_on(self) -> bool:
        return (
            AqualinkState(self.state) in [AqualinkState.ON, AqualinkState.ENABLED]
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
class AqualinkLight(object):
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
    def effect(self) -> Optional[int]:
        return None


class AqualinkDimmableLight(AqualinkLight, AqualinkDevice):
    @property
    def brightness(self) -> Optional[int]:
        return int(self.data["subtype"])

    @property
    def effect(self) -> Optional[int]:
        return None

    async def set_brightness(self, brightness: int) -> None:
        # Brightness only works in 25% increments.
        if brightness not in [0, 25, 50, 75, 100]:
            msg = f"{brightness}% isn't a valid percentage. Only use 25% increments."
            raise Exception(msg)

        data = {"aux": self.data["aux"], "light": f"{brightness}"}
        await self.system.set_light(data)

    async def turn_on(self, level: int = 100) -> None:
        await self.set_brightness(level)

    async def turn_off(self) -> None:
        await self.set_brightness(0)


class AqualinkColorLight(AqualinkLight, AqualinkDevice):
    @property
    def brightness(self) -> Optional[int]:
        # Assuming that color lights don't have adjustable brightness.
        return None

    @property
    def effect(self) -> Optional[int]:
        return self.data["state"]

    @property
    def is_on(self) -> bool:
        return self.effect != "0"

    async def set_effect(self, effect: str) -> None:
        try:
            AqualinkLightEffect(effect)
        except Exception:
            msg = f"{repr(effect)} isn't a valid effect."
            raise Exception(msg)

        data = {
            "aux": self.data["aux"],
            "light": effect,
            "subtype": self.data["subtype"],
        }
        await self.system.set_light(data)

    async def turn_off(self):
        if self.is_on:
            await self.set_effect("0")

    async def turn_on(self):
        if not self.is_on:
            await self.set_effect("1")


class AqualinkThermostat(AqualinkDevice):
    @property
    def temp(self) -> str:
        # Spa takes precedence for temp1 if present.
        if self.name.startswith("pool") and self.system.has_spa:
            return "temp2"
        return "temp1"

    async def set_temperature(self, temperature: int) -> None:
        if temperature not in range(34, 105):
            msg = f"{temperature}F isn't a valid temperature (34-104F)."
            raise Exception(msg)

        data = {self.temp: temperature}
        await self.system.set_temps(data)
