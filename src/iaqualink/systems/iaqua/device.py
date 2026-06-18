from __future__ import annotations

import logging
from enum import Enum, StrEnum, unique
from typing import TYPE_CHECKING, Any, ClassVar, cast

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkClimate,
    AqualinkDevice,
    AqualinkFan,
    AqualinkLight,
    AqualinkNumber,
    AqualinkSelect,
    AqualinkSensor,
    AqualinkSwitch,
)
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
    AqualinkStateUnavailableException,
)
from iaqualink.systems.iaqua.enums import (
    IaquaHpmErrorCode,
    IaquaHpmMode,
    IaquaHpmStatus,
    IaquaTemperatureUnit,
)

if TYPE_CHECKING:
    from iaqualink.systems.iaqua.system import IaquaSystem
    from iaqualink.typing import DeviceData

IAQUA_TEMP_CELSIUS_LOW = 1
IAQUA_TEMP_CELSIUS_HIGH = 40
IAQUA_TEMP_FAHRENHEIT_LOW = 34
IAQUA_TEMP_FAHRENHEIT_HIGH = 104

LOGGER = logging.getLogger("iaqualink.systems.iaqua")


@unique
class IaquaBinaryState(StrEnum):
    OFF = "0"
    ON = "1"


@unique
class IaquaHeaterState(StrEnum):
    OFF = "0"
    ON = "1"
    ENABLED = "3"


@unique
class IaquaPresenceState(StrEnum):
    ABSENT = "absent"
    PRESENT = "present"


@unique
class IaquaZoneStatus(StrEnum):
    OFF = "off"
    ON = "on"
    ABSENT = "absent"


class IaquaDevice(AqualinkDevice):
    def __init__(self, system: IaquaSystem, data: DeviceData):
        super().__init__(system, data)

        # This silences mypy errors due to AqualinkDevice type annotations.
        self.system: IaquaSystem = system

    @property
    def label(self) -> str:
        if fixed := _HOME_DEVICE_LABELS.get(self.name):
            return fixed
        if "label" in self.data:
            label = self.data["label"]
            return " ".join([x.capitalize() for x in label.split()])
        label = self.data["name"]
        return " ".join([x.capitalize() for x in label.split("_")])

    # Internal property used by iaqua device logic; not part of the
    # AqualinkDevice public contract.
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


class IaquaSensor(IaquaDevice, AqualinkSensor):
    @property
    def value(self) -> str:
        return self.data["state"]


class IaquaBinarySensor(IaquaDevice, AqualinkBinarySensor):
    """These are non-actionable sensors, essentially read-only on/off."""

    @property
    def is_on(self) -> bool:
        return self.state == IaquaBinaryState.ON if self.state else False


class IaquaPresenceSensor(IaquaBinarySensor):
    @property
    def is_on(self) -> bool:
        return self.state == IaquaPresenceState.PRESENT


class IaquaSwitch(IaquaDevice, AqualinkSwitch):
    @property
    def is_on(self) -> bool:
        return self.state == IaquaBinaryState.ON if self.state else False

    async def _toggle(self) -> None:
        await self.system.set_switch(f"set_{self.name}")

    async def turn_on(self) -> None:
        if not self.is_on:
            await self._toggle()

    async def turn_off(self) -> None:
        if self.is_on:
            await self._toggle()


class IaquaOneTouchSwitch(IaquaSwitch):
    # set_onetouch has toggle semantics: sending the command flips the scene
    # state, so the inherited turn_on/turn_off guards are correct as-is.
    async def _toggle(self) -> None:
        await self.system.set_onetouch(self.data["name"])


class IaquaVSPump(IaquaDevice, AqualinkFan):
    def __init__(self, system: IaquaSystem, data: DeviceData) -> None:
        super().__init__(system, data)
        self._speed_presets: list[dict[str, Any]] | None = None

    @property
    def slot_id(self) -> int:
        return int(self.data.get("slot_id", 1))

    @property
    def supports_turn_on(self) -> bool:
        return True

    @property
    def supports_turn_off(self) -> bool:
        return True

    @property
    def supports_presets(self) -> bool:
        return bool(self._speed_presets)

    @property
    def supports_percentage(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        if self._speed_presets is None:
            return self.state == IaquaBinaryState.ON
        return any(p.get("enabled") == "true" for p in self._speed_presets)

    @property
    def preset_modes(self) -> list[str]:
        if not self._speed_presets:
            raise AqualinkOperationNotSupportedException
        return [str(p["speedName"]) for p in self._speed_presets]

    @property
    def preset_mode(self) -> str | None:
        if not self._speed_presets:
            raise AqualinkOperationNotSupportedException
        for p in self._speed_presets:
            if p.get("enabled") == "true":
                return str(p["speedName"])
        return None

    async def _set_preset_mode(self, preset_mode: str) -> None:
        # supports_presets gates this in the base class's set_preset_mode().
        assert self._speed_presets is not None
        for p in self._speed_presets:
            if p["speedName"] == preset_mode:
                result = await self.system.set_vsp_speed(
                    int(p["speedid"]), slot_id=self.slot_id
                )
                self._apply_speed_update(result.get("vsp_speedInfo", []))
                return
        raise AqualinkOperationNotSupportedException

    async def turn_on(self) -> None:
        if self.is_on:
            return
        speed_id = 1
        if self._speed_presets:
            speed_id = int(self._speed_presets[0]["speedid"])
        result = await self.system.set_vsp_speed(speed_id, slot_id=self.slot_id)
        self._apply_speed_update(result.get("vsp_speedInfo", []))

    async def turn_off(self) -> None:
        if not self.is_on:
            return
        result = await self.system.stop_vsp_pump(self.slot_id)
        self._apply_speed_update(result.get("vsp_speedInfo", []))

    def _apply_speed_update(self, speed_info: list[dict[str, Any]]) -> None:
        if self._speed_presets is None or not speed_info:
            return
        by_id = {int(p["speedId"]): p["status"] for p in speed_info}
        for preset in self._speed_presets:
            status = by_id.get(int(preset["speedid"]))
            if status is not None:
                preset["enabled"] = "true" if status == "Enabled" else "false"

    async def fetch_speed(self) -> None:
        data = await self.system.get_vsp_speed(self.slot_id)
        self._speed_presets = data.get("vsp_speedInfo", [])


class IaquaHeater(IaquaSwitch):
    @property
    def is_on(self) -> bool:
        return (
            self.state in [IaquaHeaterState.ON, IaquaHeaterState.ENABLED]
            if self.state
            else False
        )


class IaquaHeatPump(IaquaDevice, AqualinkSwitch):
    """Enable/disable switch for a paired HPM heat pump."""

    @property
    def is_on(self) -> bool:
        return (
            self.state in [IaquaHpmStatus.ON, IaquaHpmStatus.ENABLED]
            if self.state
            else False
        )

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.enable_disable_hpm(True)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.enable_disable_hpm(False)

    @property
    def model(self) -> str:
        hpm_type = self.data.get("hpm_type")
        return f"Heat Pump ({hpm_type})" if hpm_type else "Heat Pump"


class IaquaHeatPumpMode(IaquaDevice, AqualinkSelect):
    """Heat/chill mode picker for a paired HPM heat pump. Only present when chill is available."""

    @property
    def current_option(self) -> str | None:
        return self.state or None

    @property
    def options(self) -> list[str]:
        return [IaquaHpmMode.HEAT, IaquaHpmMode.CHILL]

    async def _select_option(self, option: str) -> None:
        await self.system.switch_hpm_mode(option)


class IaquaHeatPumpStatusSensor(IaquaSensor):
    @property
    def value_enum(self) -> type[Enum] | None:
        return IaquaHpmStatus


class IaquaHeatPumpAlertSensor(IaquaSensor):
    @property
    def value_enum(self) -> type[Enum] | None:
        return IaquaHpmErrorCode


class _IaquaAuxMixin(IaquaDevice):
    @property
    def is_on(self) -> bool:
        return self.state == IaquaBinaryState.ON if self.state else False

    async def _toggle(self) -> None:
        await self.system.set_aux(self.data["aux"])

    async def turn_on(self) -> None:
        if not self.is_on:
            await self._toggle()

    async def turn_off(self) -> None:
        if self.is_on:
            await self._toggle()


class IaquaAuxSwitch(_IaquaAuxMixin, AqualinkSwitch):
    pass


class IaquaLightSwitch(_IaquaAuxMixin, AqualinkLight):
    pass


class IaquaDimmableLight(_IaquaAuxMixin, AqualinkLight):
    async def turn_on(self) -> None:
        if not self.is_on:
            await self.set_brightness_percentage(100)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.set_brightness_percentage(0)

    @property
    def brightness_percentage(self) -> int | None:
        return int(self.data["subtype"])

    async def _set_brightness_percentage(self, brightness: int) -> None:
        # Brightness only works in 25% increments.
        if brightness not in [0, 25, 50, 75, 100]:
            msg = f"{brightness}% isn't a valid percentage."
            msg += " Only use 25% increments."
            raise AqualinkInvalidParameterException(msg)

        data = {"aux": self.data["aux"], "light": f"{brightness}"}
        await self.system.set_light(data)


class IaquaColorLight(_IaquaAuxMixin, AqualinkLight):
    _EFFECTS: ClassVar[dict[str, int]] = {}

    async def turn_on(self) -> None:
        if not self.is_on:
            await self._set_effect_by_id(1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self._set_effect_by_id(0)

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
    def effect_list(self) -> list[str]:
        return list(self._EFFECTS)

    async def _set_effect(self, effect: str) -> None:
        await self._set_effect_by_id(self._EFFECTS[effect])

    async def _set_effect_by_id(self, effect_id: int) -> None:
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

    _EFFECTS: ClassVar[dict[str, int]] = {
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

    _EFFECTS: ClassVar[dict[str, int]] = {
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


class IaquaColorLightCL(IaquaColorLight):
    @property
    def manufacturer(self) -> str:
        return "Pentair"

    @property
    def model(self) -> str:
        return "ColorLogic Light"

    _EFFECTS: ClassVar[dict[str, int]] = {
        "Off": 0,
        "Voodoo Lounge": 1,
        "Deep Blue Sea": 2,
        "Afternoon Skies": 3,
        "Emerald": 4,
        "Sangria": 5,
        "Cloud White": 6,
        "Twilight": 7,
        "Tranquility": 8,
        "Gemstone": 9,
        "USA!": 10,
        "Mardi Gras": 11,
        "Cool Cabaret": 12,
    }


class IaquaColorLightJL(IaquaColorLight):
    @property
    def manufacturer(self) -> str:
        return "Jandy"

    @property
    def model(self) -> str:
        return "LED WaterColors Light"

    _EFFECTS: ClassVar[dict[str, int]] = {
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
        "USA!": 12,
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

    _EFFECTS: ClassVar[dict[str, int]] = {
        "Off": 0,
        "SAm": 1,
        "Party": 2,
        "Romance": 3,
        "Caribbean": 4,
        "American": 5,
        "California Sunset": 6,
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

    _EFFECTS: ClassVar[dict[str, int]] = {
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
        "USA!": 15,
        "Mardi Gras": 16,
        "Cool Cabaret": 17,
    }


light_subtype_to_class = {
    "1": IaquaColorLightJC,
    "2": IaquaColorLightSL,
    "3": IaquaColorLightCL,
    "4": IaquaColorLightJL,
    "5": IaquaColorLightIB,
    "6": IaquaColorLightHU,
}


_HPM_TEMP_PARAM: dict[str, str] = {
    "pool_set_point": "poolheatsetpointtemp",
    "spa_set_point": "spaheatsetpointtemp",
    "pool_chill_set_point": "poolchillsetpointtemp",
}


class IaquaSetPoint(IaquaDevice, AqualinkNumber):
    @property
    def _temperature_key(self) -> str:
        # Spa takes precedence for temp1 if both set points are present.
        if (
            self.name.split("_")[0] == "pool"
            and "spa_set_point" in self.system.devices
        ):
            return "temp2"
        return "temp1"

    @property
    def current_value(self) -> float | None:
        try:
            return float(self.state)
        except (ValueError, KeyError):
            return None

    @property
    def min_value(self) -> float:
        if self.system.temp_unit is None:
            raise AqualinkStateUnavailableException(
                "Temperature unit unavailable; call update() first."
            )
        if self.system.temp_unit == IaquaTemperatureUnit.FAHRENHEIT:
            return float(IAQUA_TEMP_FAHRENHEIT_LOW)
        return float(IAQUA_TEMP_CELSIUS_LOW)

    @property
    def max_value(self) -> float:
        if self.system.temp_unit is None:
            raise AqualinkStateUnavailableException(
                "Temperature unit unavailable; call update() first."
            )
        if self.system.temp_unit == IaquaTemperatureUnit.FAHRENHEIT:
            return float(IAQUA_TEMP_FAHRENHEIT_HIGH)
        return float(IAQUA_TEMP_CELSIUS_HIGH)

    @property
    def unit_of_measurement(self) -> str | None:
        unit = self.system.temp_unit
        if unit is None:
            return None
        return "°C" if unit == IaquaTemperatureUnit.CELSIUS else "°F"

    async def _set_value(self, value: float) -> None:
        # Pool chill is heat-pump-only; pool/spa heat set points route through
        # the same HPM command once a heat pump is paired (it becomes the
        # equipment that actually heats, superseding the relay-heater path).
        if (
            self.name == "pool_chill_set_point"
            or "heatpump" in self.system.devices
        ):
            await self.system.setpoint_hpm_temp(
                {_HPM_TEMP_PARAM[self.name]: str(int(value))}
            )
        else:
            await self.system.set_temps(
                {self._temperature_key: str(int(value))}
            )


ICL_CUSTOM_COLOR_ID = 16
ICL_CUSTOM_COLOR_NAME = "Custom Color"

# index 16 = custom RGBW — not a named effect (use set_rgbw() instead)
ICL_EFFECTS = {
    "Off": 0,
    "Alpine White": 1,
    "Sky Blue": 2,
    "Cobalt Blue": 3,
    "Caribbean Blue": 4,
    "Spring Green": 5,
    "Emerald Green": 6,
    "Emerald Rose": 7,
    "Ruby Red": 8,
    "Magenta": 9,
    "Violet": 10,
    "Slow Color Splash": 11,
    "Fast Color Splash": 12,
    "America The Beautiful": 13,
    "Fat Tuesday": 14,
    "Disco Tech": 15,
}


class IaquaIclLight(IaquaDevice, AqualinkLight):
    @property
    def manufacturer(self) -> str:
        return "Jandy"

    @property
    def model(self) -> str:
        return "IntelliCenter Light"

    @property
    def _zone_id(self) -> int:
        return int(self.data.get("zoneId", 0))

    @property
    def label(self) -> str:
        name = self.data.get("zoneName", "")
        if name:
            return name
        return f"Light Zone {self._zone_id}"

    @property
    def name(self) -> str:
        return f"icl_zone_{self._zone_id}"

    @property
    def state(self) -> str:
        return self.data.get("zoneStatus", IaquaZoneStatus.OFF)

    @property
    def is_on(self) -> bool:
        return self.state == IaquaZoneStatus.ON

    @property
    def brightness_percentage(self) -> int | None:
        dim_level = self.data.get("dim_level")
        if dim_level:
            return int(dim_level)
        return None

    @property
    def effect(self) -> str | None:
        color_val = self.data.get("zoneColorVal")
        color_id = self._color_id
        if color_val and color_id is not None and 1 <= color_id <= 15:
            return color_val
        return None

    @property
    def effect_list(self) -> list[str]:
        return list(ICL_EFFECTS)

    @property
    def _color_id(self) -> int | None:
        color = self.data.get("zoneColor")
        if color:
            return int(color)
        return None

    @property
    def rgbw(self) -> tuple[int, int, int, int]:
        r = int(self.data.get("red_val") or 0)
        g = int(self.data.get("green_val") or 0)
        b = int(self.data.get("blue_val") or 0)
        w = int(self.data.get("white_val") or 0)
        return (r, g, b, w)

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.icl_zone_on_off(self._zone_id, turn_on=True)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.icl_zone_on_off(self._zone_id, turn_on=False)

    async def _set_brightness_percentage(self, brightness: int) -> None:
        # The API accepts any 0–100 value, but the app only exposes multiples of 5.
        if brightness % 5 != 0:
            msg = f"{brightness}% isn't a valid ICL brightness (must be a multiple of 5)."
            raise AqualinkInvalidParameterException(msg)
        await self.system.icl_set_brightness(self._zone_id, brightness)

    async def _set_effect(self, effect: str) -> None:
        await self._set_effect_by_id(ICL_EFFECTS[effect])

    async def _set_effect_by_id(self, effect_id: int) -> None:
        brightness = (
            self.brightness_percentage
            if self.brightness_percentage is not None
            else 100
        )
        await self.system.icl_set_color(self._zone_id, effect_id, brightness)

    async def _set_rgbw(
        self, red: int, green: int, blue: int, white: int = 0
    ) -> None:
        await self.system.icl_set_custom_color(
            self._zone_id, red, green, blue, white
        )


class IaquaClimate(IaquaDevice, AqualinkClimate):
    """Virtual thermostat composed from a set-point Number, a temp Sensor, and a heater Switch."""

    @property
    def _type(self) -> str:
        return self.name.split("_")[0]

    @property
    def state(self) -> str:
        raise AqualinkOperationNotSupportedException(
            "IaquaClimate is a virtual device and has no state field."
        )

    @property
    def _set_point(self) -> IaquaSetPoint:
        return cast(
            IaquaSetPoint, self.system.devices[f"{self._type}_set_point"]
        )

    @property
    def _heater(self) -> IaquaHeater:
        return cast(IaquaHeater, self.system.devices[f"{self._type}_heater"])

    @property
    def _sensor(self) -> IaquaSensor:
        return cast(IaquaSensor, self.system.devices[f"{self._type}_temp"])

    @property
    def temperature_unit(self) -> IaquaTemperatureUnit:
        if self.system.temp_unit is None:
            raise AqualinkStateUnavailableException(
                "Temperature unit unavailable; call update() first."
            )
        return self.system.temp_unit

    @property
    def current_temperature(self) -> str:
        return self._sensor.value

    @property
    def target_temperature(self) -> str:
        return self._set_point.state

    @property
    def min_temp(self) -> int:
        if self.temperature_unit == IaquaTemperatureUnit.FAHRENHEIT:
            return IAQUA_TEMP_FAHRENHEIT_LOW
        return IAQUA_TEMP_CELSIUS_LOW

    @property
    def max_temp(self) -> int:
        if self.temperature_unit == IaquaTemperatureUnit.FAHRENHEIT:
            return IAQUA_TEMP_FAHRENHEIT_HIGH
        return IAQUA_TEMP_CELSIUS_HIGH

    @property
    def is_on(self) -> bool:
        return self._heater.is_on

    async def turn_on(self) -> None:
        if not self._heater.is_on:
            await self._heater.turn_on()

    async def turn_off(self) -> None:
        if self._heater.is_on:
            await self._heater.turn_off()

    async def _set_temperature(self, temperature: int) -> None:
        await self._set_point.set_value(float(temperature))


_HOME_DEVICE_MAP: dict[str, type[IaquaDevice]] = {
    "spa_temp": IaquaSensor,
    "pool_temp": IaquaSensor,
    "air_temp": IaquaSensor,
    "cover_pool": IaquaSensor,
    "freeze_protection": IaquaBinarySensor,
    "spa_pump": IaquaSwitch,
    "pool_pump": IaquaSwitch,
    "spa_heater": IaquaHeater,
    "pool_heater": IaquaHeater,
    "solar_heater": IaquaHeater,
    "spa_salinity": IaquaSensor,
    "pool_salinity": IaquaSensor,
    "orp": IaquaSensor,
    "ph": IaquaSensor,
    "is_icl_present": IaquaPresenceSensor,
    "spa_set_point": IaquaSetPoint,
    "pool_set_point": IaquaSetPoint,
    "pool_chill_set_point": IaquaSetPoint,
    "relay_count": IaquaSensor,
}

_HOME_DEVICE_LABELS: dict[str, str] = {
    "spa_temp": "Spa Temperature",
    "pool_temp": "Pool Temperature",
    "air_temp": "Air Temperature",
    "cover_pool": "Pool Cover",
    "freeze_protection": "Freeze Protection",
    "spa_pump": "Spa Pump",
    "pool_pump": "Pool Pump",
    "spa_heater": "Spa Heater",
    "pool_heater": "Pool Heater",
    "solar_heater": "Solar Heater",
    "spa_salinity": "Spa Salinity",
    "pool_salinity": "Pool Salinity",
    "orp": "ORP",
    "ph": "pH",
    "is_icl_present": "ICL Present",
    "spa_set_point": "Spa Set Point",
    "pool_set_point": "Pool Set Point",
    "pool_chill_set_point": "Pool Chill Set Point",
    "relay_count": "Relay Count",
    "heatpump": "Heat Pump",
    "heatpump_mode": "Heat Pump Mode",
    "heatpump_status": "Heat Pump Status",
    "heatpump_alert": "Heat Pump Alert",
}
