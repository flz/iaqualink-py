from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from iaqualink.device import (
    AqualinkClimate,
    AqualinkDevice,
    AqualinkFan,
    AqualinkSensor,
    AqualinkSwitch,
)
from iaqualink.systems.tcx.enums import WaterStatus

if TYPE_CHECKING:
    from iaqualink.systems.tcx.system import TcxSystem
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink.systems.tcx")

# Default heater set-point bounds when shadow does not supply them.
_HEAT_MIN_F = 65
_HEAT_MAX_F = 104
_HEAT_MIN_C = 18
_HEAT_MAX_C = 40


class TcxDevice(AqualinkDevice):
    def __init__(self, system: TcxSystem, data: DeviceData):
        super().__init__(system, data)
        self.system: TcxSystem = system

    @property
    def name(self) -> str:
        return str(self.data["name"])

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Tcx", "")

    @classmethod
    def from_data(cls, system: TcxSystem, data: DeviceData) -> TcxDevice:
        name = str(data["name"])

        if name == "water":
            return TcxWaterSensor(system, data)
        if name == "air":
            return TcxAirSensor(system, data)
        if name == "filt0":
            return TcxFilterPump(system, data)
        if name == "ecm0":
            return TcxVariableSpeedPump(system, data)
        if name.startswith("aux") and name[3:].isdigit():
            return TcxAuxSwitch(system, data)
        if name == "TspBdy0":
            return TcxClimate(system, data)
        if name == "swc0":
            return TcxChlorinatorBoost(system, data)
        if name == "solar":
            return TcxSolarSensor(system, data)
        if name.startswith("feaCircuit") and name[10:].isdigit():
            return TcxFeatureCircuit(system, data)
        if name.startswith("zig_"):
            return TcxZigbeeSwitch(system, data)

        return TcxGenericSensor(system, data)


class TcxWaterSensor(TcxDevice, AqualinkSensor):
    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else "Water Temperature"

    @property
    def value(self) -> str:
        us = self.data.get("us")
        if us != WaterStatus.VALID:
            return ""
        raw = self.data.get("value")
        return str(raw) if raw is not None else ""


class TcxAirSensor(TcxDevice, AqualinkSensor):
    @property
    def label(self) -> str:
        return "Air Temperature"

    @property
    def value(self) -> str:
        raw = self.data.get("value")
        return str(raw) if raw is not None else ""


class TcxSolarSensor(TcxDevice, AqualinkSensor):
    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else "Solar Temperature"

    @property
    def value(self) -> str:
        raw = self.data.get("value")
        return str(raw) if raw is not None else ""


class TcxGenericSensor(TcxDevice, AqualinkSensor):
    @property
    def value(self) -> str:
        raw = self.data.get("value") or self.data.get("st")
        return str(raw) if raw is not None else ""


class TcxFilterPump(TcxDevice, AqualinkSwitch):
    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else "Filter Pump"

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_filter_pump(1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_filter_pump(0)


class TcxAuxSwitch(TcxDevice, AqualinkSwitch):
    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else self.name.upper()

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_aux(self.name, 1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_aux(self.name, 0)


class TcxVariableSpeedPump(TcxDevice, AqualinkFan):
    """Variable speed pump (ECM). Exposes named speed presets from spdList."""

    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else "Variable Speed Pump"

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    @property
    def supports_presets(self) -> bool:
        return bool(self.data.get("spdList"))

    def _spd_list(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self.data.get("spdList", []))

    @property
    def preset_modes(self) -> list[str]:
        return [str(entry["name"]) for entry in self._spd_list()]

    @property
    def preset_mode(self) -> str | None:
        cmd_spd = self.data.get("cmdSpd")
        if cmd_spd is None:
            return None
        for entry in self._spd_list():
            if entry.get("spd") == cmd_spd:
                return str(entry["name"])
        return None

    async def _set_preset_mode(self, preset_mode: str) -> None:
        for entry in self._spd_list():
            if str(entry["name"]) == preset_mode:
                await self.system.set_vsp_speed(int(entry["spd"]))
                return

    @property
    def supports_percentage(self) -> bool:
        return True

    @property
    def percentage(self) -> int | None:
        cmd_spd = self.data.get("cmdSpd")
        min_spd = self.data.get("minSpd")
        max_spd = self.data.get("maxSpd")
        if cmd_spd is None or min_spd is None or max_spd is None:
            return None
        c, lo, hi = int(cmd_spd), int(min_spd), int(max_spd)
        if hi == lo:
            return None
        pct = (c - lo) / (hi - lo) * 100
        return max(0, min(100, round(pct)))

    async def _set_percentage(self, percentage: int) -> None:
        min_spd = int(self.data.get("minSpd") or 0)
        max_spd = int(self.data.get("maxSpd") or 3450)
        spd = round(min_spd + (max_spd - min_spd) * percentage / 100)
        await self.system.set_vsp_speed(spd)


class TcxClimate(TcxDevice, AqualinkClimate):
    @property
    def label(self) -> str:
        name = self.data.get("name_")
        return str(name) if name else "Heater"

    @property
    def is_on(self) -> bool:
        return bool(self.data.get("heatEnabled"))

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_heat_enabled(True)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_heat_enabled(False)

    @property
    def temperature_unit(self) -> str:
        return self.system.temp_unit

    @property
    def current_temperature(self) -> str | None:
        water = self.system.devices.get("water")
        if water is None or not isinstance(water, TcxWaterSensor):
            return None
        v = water.value
        return v if v else None

    @property
    def target_temperature(self) -> str | None:
        raw = self.data.get("waterTempSet")
        return str(raw) if raw is not None else None

    @property
    def min_temp(self) -> int:
        return _HEAT_MIN_C if self.system.temp_unit == "C" else _HEAT_MIN_F

    @property
    def max_temp(self) -> int:
        return _HEAT_MAX_C if self.system.temp_unit == "C" else _HEAT_MAX_F

    async def _set_temperature(self, temperature: int) -> None:
        await self.system.set_water_temp_setpoint(temperature)


class TcxChlorinatorBoost(TcxDevice, AqualinkSwitch):
    """SWC boost mode on/off."""

    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else "Chlorinator Boost"

    @property
    def is_on(self) -> bool:
        return bool(self.data.get("boost"))

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_swc_boost(True)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_swc_boost(False)


class TcxFeatureCircuit(TcxDevice, AqualinkSwitch):
    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        if fr:
            return str(fr)
        idx = self.name[len("feaCircuit") :]
        return f"Feature Circuit {idx}"

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_feature_circuit_state(self.name, 1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_feature_circuit_state(self.name, 0)


class TcxZigbeeSwitch(TcxDevice, AqualinkSwitch):
    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        if fr:
            return str(fr)
        return self.name.replace("zig_", "ZigBee ")

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            addr = str(self.data.get("addr", self.name[4:]))
            await self.system.set_zigbee_state(addr, 1)

    async def turn_off(self) -> None:
        if self.is_on:
            addr = str(self.data.get("addr", self.name[4:]))
            await self.system.set_zigbee_state(addr, 0)
