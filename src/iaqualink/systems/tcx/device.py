from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from iaqualink.device import (
    AqualinkClimate,
    AqualinkDevice,
    AqualinkFan,
    AqualinkLight,
    AqualinkNumber,
    AqualinkSensor,
    AqualinkSwitch,
)
from iaqualink.systems.tcx.enums import (
    AuxType,
    LightType,
    SolarStatus,
    WaterStatus,
)

if TYPE_CHECKING:
    from iaqualink.systems.tcx.system import TcxSystem
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink.systems.tcx")

# Water/solar heater set-point bounds (user-supplied spec: 60-104°F,
# 1°F step — shared by both TcxClimate and TcxSolarSetPoint). Shadow does
# not supply bounds fields, so these are hardcoded. Celsius bounds are the
# Fahrenheit values converted and rounded to the nearest whole degree
# (60°F=15.56°C, 104°F=40.00°C) — see docs/implementation/systems/tcx.md.
_TEMP_SETPOINT_MIN_F = 60
_TEMP_SETPOINT_MAX_F = 104
_TEMP_SETPOINT_MIN_C = 16
_TEMP_SETPOINT_MAX_C = 40

# Freeze-protection set-point bounds (user-supplied spec: 34-42°F, 1°F
# step). Celsius bounds converted the same way (34°F=1.11°C, 42°F=5.56°C).
_FREEZE_SP_MIN_F = 34
_FREEZE_SP_MAX_F = 42
_FREEZE_SP_MIN_C = 1
_FREEZE_SP_MAX_C = 6

# VSP speed bounds (user-supplied spec: 600-3450 RPM, 25 RPM step). Some
# hardware variants ("SVRS") report an effective minimum of 1050 RPM
# instead — not detectable from wire data, so 600 is used uniformly as the
# absolute floor; TcxVspMinSpeed/MaxSpeed/PrimingSpeed/FreezeProtectSpeed
# additionally clamp against each other's *current* value for the
# min<=max invariant (see device.py TcxVsp* classes below).
_VSP_SPEED_MIN_RPM = 600
_VSP_SPEED_MAX_RPM = 3450
_VSP_SPEED_STEP_RPM = 25

# VSP priming-duration bounds (user-supplied spec: 0-300 seconds, 60s
# step). Wire unit is already seconds — no temperature-style scaling.
_VSP_PRIMING_DURATION_MIN_S = 0
_VSP_PRIMING_DURATION_MAX_S = 300
_VSP_PRIMING_DURATION_STEP_S = 60


def _wire_temp_to_display(raw: int | float | str) -> str:
    """Temperature wire fields (water/solar value, TspBdy0.waterTempSet,
    freezeSP, lowAirSP) are tenths of the active display unit (whichever
    `tempSetting` selects) — e.g. 283 -> "28.3". Confirmed from live wire
    capture: freezeSP=33 and lowAirSP=128 only make sense as 3.3°C/12.8°C,
    not 33°C/128°C, and waterTempSet/water.value agreeing at raw 283 only
    makes sense as 28.3°C for both, not 283°C."""
    return str(float(raw) / 10)


def _display_temp_to_wire(temperature: int) -> int:
    """Inverse of `_wire_temp_to_display` for the write path."""
    return temperature * 10


def _lvh1_en_to_status(en: int) -> str:
    """lvh1.en is a ranged code, not a 1:1 enum (docs/reference/systems/tcx.md
    "lvh1 (Heater Tile State)"): 0 -> off, 1-5 -> standby, 6 -> heating,
    >=7 -> off. Doesn't fit AqualinkSensor.value_enum's exact-membership
    `cls(value)` lookup, so classify directly instead."""
    if en == 6:
        return "heating"
    if 1 <= en <= 5:
        return "standby"
    return "off"


# Synthetic device keys for read-only speed (RPM) sensors built from
# filt0/ecm0 sub-fields with no confirmed write action — see
# TcxSystem._ECM0_EXTRA_SPEED_FIELDS. Not full wire device names, so
# dispatched by exact match here rather than the filt0/ecm0 branches above.
_SPEED_SENSOR_NAMES = frozenset(
    {
        "filt0_manSpd",
        "ecm0_manSpd",
        "ecm0_qcSpd",
    }
)

# aux0.et values that indicate a real color-capable light, dispatched to
# TcxAuxLight. LightType.WHITE_LIGHT ("WL", non-color) and anything without
# `et` stay TcxAuxSwitch — see docs/implementation/systems/tcx.md.
_AUX_LIGHT_TYPES = frozenset(
    {
        LightType.JANDY_WATERCOLORS,
        LightType.PENTAIR_INTELLIBRITE,
        LightType.PENTAIR_SAM_SAL,
        LightType.HAYWARD_COLORLOGIC,
    }
)


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
        if name in _SPEED_SENSOR_NAMES:
            return TcxSpeedSensor(system, data)
        if name == "ecm0_minSpd":
            return TcxVspMinSpeed(system, data)
        if name == "ecm0_maxSpd":
            return TcxVspMaxSpeed(system, data)
        if name == "ecm0_prmSpd":
            return TcxVspPrimingSpeed(system, data)
        if name == "ecm0_frzSpd":
            return TcxVspFreezeProtectSpeed(system, data)
        if name == "ecm0_prmDur":
            return TcxVspPrimingDuration(system, data)
        if name == "aux0_fp":
            return TcxAuxFreezeProtectSwitch(system, data)
        if name.startswith("aux") and name[3:].isdigit():
            if data.get("et") in _AUX_LIGHT_TYPES:
                return TcxAuxLight(system, data)
            return TcxAuxSwitch(system, data)
        if name.startswith("jva") and name[3:].isdigit():
            return TcxJvaSwitch(system, data)
        if name == "TspBdy0":
            return TcxClimate(system, data)
        if name == "TspBdy0_water":
            return TcxWaterSetPoint(system, data)
        if name == "TspBdy0_solar":
            return TcxSolarSetPoint(system, data)
        if name == "freezeSP":
            return TcxFreezeSetPoint(system, data)
        if name == "lvh1":
            return TcxHeaterStatusSensor(system, data)
        if name == "lvh1_enable":
            return TcxHeaterEnableSwitch(system, data)
        if name == "swc0":
            return TcxChlorinatorBoost(system, data)
        if name == "solar":
            return TcxSolarSensor(system, data)
        if name.startswith("feaCircuit") and name[10:].isdigit():
            return TcxFeatureCircuit(system, data)
        if name.startswith("auxz") and name[4:].isdigit():
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
        return _wire_temp_to_display(raw) if raw is not None else ""


class TcxSpeedSensor(TcxDevice, AqualinkSensor):
    """Read-only RPM sensor for a filt0/ecm0 speed field not otherwise
    surfaced (see _SPEED_SENSOR_NAMES / _ECM0_EXTRA_SPEED_FIELDS in
    system.py). These are raw RPM values, already whole units — no
    temperature-style /10 scaling applies."""

    @property
    def label(self) -> str:
        return str(self.data.get("label") or self.name)

    @property
    def value(self) -> str:
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
        us = self.data.get("us")
        if us != SolarStatus.PRESENT:
            return ""
        raw = self.data.get("value")
        return _wire_temp_to_display(raw) if raw is not None else ""


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
    def model(self) -> str:
        ty = self.data.get("ty")
        if ty is not None:
            try:
                return AuxType(ty).name.replace("_", " ").title()
            except ValueError:
                pass
        return super().model

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_aux(self.name, 1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_aux(self.name, 0)


class TcxAuxLight(TcxDevice, AqualinkLight):
    """Color-capable aux relay (aux0.et in JL/IB/PSS/HU — see LightType).
    On/off reuses the same `st` field/write path as TcxAuxSwitch. Color
    control exposes the raw `currClr`/`cmdClr` index only — no confirmed
    color-index-to-name mapping exists for TCX (unlike iaqua's per-brand
    effect lists, which are keyed on a different platform's subtype codes
    and can't be safely assumed to match here). See "Deltas vs Protocol
    Reference" in docs/implementation/systems/tcx.md."""

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

    @property
    def current_color_index(self) -> int | None:
        raw = self.data.get("currClr")
        return int(raw) if raw is not None else None

    async def set_color_index(self, index: int) -> None:
        await self.system.set_aux_light(self.name, index)

    async def reset_color(self) -> None:
        await self.system.reset_aux_light(self.name)


class TcxAuxFreezeProtectSwitch(TcxDevice, AqualinkSwitch):
    """Synthetic sibling of aux0 for the `fp` (freeze protect) field —
    aux0-only, singleton (synthetic key `aux0_fp`), same technique as
    lvh1/lvh1_enable. The wire action (`setIsAux0FreezeProtect`) hardcodes
    "Aux0" in its name, unlike the genuinely generic per-aux actions
    (setAuxState/setAuxLight/setAuxSetup) — freeze protect is a real
    hardware feature of the aux0 relay specifically, not a capability every
    auxN has."""

    @property
    def label(self) -> str:
        return "Freeze Protect"

    @property
    def is_on(self) -> bool:
        return bool(self.data.get("fp"))

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_aux_freeze_protect(True)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_aux_freeze_protect(False)


class TcxJvaSwitch(TcxDevice, AqualinkSwitch):
    """JVA valve actuator. Write path (setJvaState/NAMESPACE_PIB) is
    inferred, never wire-confirmed — no "PIB" command entries exist in the
    reference doc despite "PIB" being a listed namespace. See Deltas table
    in docs/implementation/systems/tcx.md."""

    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else self.name.upper()

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_jva_state(self.name, 1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_jva_state(self.name, 0)


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
            if entry.get("speed") == cmd_spd:
                return str(entry["name"])
        return None

    async def _set_preset_mode(self, preset_mode: str) -> None:
        for entry in self._spd_list():
            if str(entry["name"]) == preset_mode:
                await self.system.set_vsp_speed(int(entry["speed"]))
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


class TcxVspMinSpeed(TcxDevice, AqualinkNumber):
    """Minimum VSP master speed (`ecm0.minSpd`), namespace `vsp`. Absolute
    floor 600 RPM per user-supplied spec — some hardware variants ("SVRS")
    report an effective minimum of 1050 RPM instead, not detectable from
    wire data, so 600 is used uniformly. Dynamic upper bound: must stay
    <= the current `maxSpd` (read from the same synthesized `ecm0` dict —
    see TcxSystem._ECM0_WRITABLE_SPEED_FIELDS)."""

    @property
    def label(self) -> str:
        return "VSP Minimum Speed"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("minSpd")
        return float(raw) if raw is not None else None

    @property
    def min_value(self) -> float:
        return _VSP_SPEED_MIN_RPM

    @property
    def max_value(self) -> float:
        raw = self.data.get("maxSpd")
        return float(raw) if raw is not None else _VSP_SPEED_MAX_RPM

    @property
    def step(self) -> float:
        return _VSP_SPEED_STEP_RPM

    @property
    def unit_of_measurement(self) -> str | None:
        return "rpm"

    async def _set_value(self, value: float) -> None:
        await self.system.set_vsp_min_speed(int(value))


class TcxVspMaxSpeed(TcxDevice, AqualinkNumber):
    """Maximum VSP master speed (`ecm0.maxSpd`), namespace `vsp`. Dynamic
    lower bound: must stay >= the current `minSpd`. Absolute ceiling 3450
    RPM (same across hardware variants per user-supplied spec)."""

    @property
    def label(self) -> str:
        return "VSP Maximum Speed"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("maxSpd")
        return float(raw) if raw is not None else None

    @property
    def min_value(self) -> float:
        raw = self.data.get("minSpd")
        return float(raw) if raw is not None else _VSP_SPEED_MIN_RPM

    @property
    def max_value(self) -> float:
        return _VSP_SPEED_MAX_RPM

    @property
    def step(self) -> float:
        return _VSP_SPEED_STEP_RPM

    @property
    def unit_of_measurement(self) -> str | None:
        return "rpm"

    async def _set_value(self, value: float) -> None:
        await self.system.set_vsp_max_speed(int(value))


class TcxVspPrimingSpeed(TcxDevice, AqualinkNumber):
    """Priming speed (`ecm0.prmSpd`), namespace `vsp`. Dynamic bounds
    `[minSpd, maxSpd]` per user-supplied spec."""

    @property
    def label(self) -> str:
        return "VSP Priming Speed"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("prmSpd")
        return float(raw) if raw is not None else None

    @property
    def min_value(self) -> float:
        raw = self.data.get("minSpd")
        return float(raw) if raw is not None else _VSP_SPEED_MIN_RPM

    @property
    def max_value(self) -> float:
        raw = self.data.get("maxSpd")
        return float(raw) if raw is not None else _VSP_SPEED_MAX_RPM

    @property
    def step(self) -> float:
        return _VSP_SPEED_STEP_RPM

    @property
    def unit_of_measurement(self) -> str | None:
        return "rpm"

    async def _set_value(self, value: float) -> None:
        await self.system.set_vsp_priming_speed(int(value))


class TcxVspFreezeProtectSpeed(TcxDevice, AqualinkNumber):
    """Freeze-protection speed (`ecm0.frzSpd`), namespace `vsp`. Dynamic
    bounds `[minSpd, maxSpd]` per user-supplied spec. Distinct from
    TcxAuxFreezeProtectSwitch (aux0.fp, a separate freeze-protect concept
    for the aux0 relay, action setIsAux0FreezeProtect)."""

    @property
    def label(self) -> str:
        return "VSP Freeze Protect Speed"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("frzSpd")
        return float(raw) if raw is not None else None

    @property
    def min_value(self) -> float:
        raw = self.data.get("minSpd")
        return float(raw) if raw is not None else _VSP_SPEED_MIN_RPM

    @property
    def max_value(self) -> float:
        raw = self.data.get("maxSpd")
        return float(raw) if raw is not None else _VSP_SPEED_MAX_RPM

    @property
    def step(self) -> float:
        return _VSP_SPEED_STEP_RPM

    @property
    def unit_of_measurement(self) -> str | None:
        return "rpm"

    async def _set_value(self, value: float) -> None:
        await self.system.set_vsp_freeze_protect_speed(int(value))


class TcxVspPrimingDuration(TcxDevice, AqualinkNumber):
    """Priming duration in seconds (`ecm0.prmDur`), namespace `vsp`. Wire
    unit is already seconds — no temperature-style scaling. 0-300s, 60s
    step per user-supplied spec."""

    @property
    def label(self) -> str:
        return "VSP Priming Duration"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("prmDur")
        return float(raw) if raw is not None else None

    @property
    def min_value(self) -> float:
        return _VSP_PRIMING_DURATION_MIN_S

    @property
    def max_value(self) -> float:
        return _VSP_PRIMING_DURATION_MAX_S

    @property
    def step(self) -> float:
        return _VSP_PRIMING_DURATION_STEP_S

    @property
    def unit_of_measurement(self) -> str | None:
        return "s"

    async def _set_value(self, value: float) -> None:
        await self.system.set_vsp_priming_duration(int(value))


class TcxClimate(TcxDevice, AqualinkClimate):
    @property
    def label(self) -> str:
        body_name = self.data.get("bodyName")
        return str(body_name) if body_name else "Heater"

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
        return _wire_temp_to_display(raw) if raw is not None else None

    @property
    def min_temp(self) -> int:
        return (
            _TEMP_SETPOINT_MIN_C
            if self.system.temp_unit == "C"
            else _TEMP_SETPOINT_MIN_F
        )

    @property
    def max_temp(self) -> int:
        return (
            _TEMP_SETPOINT_MAX_C
            if self.system.temp_unit == "C"
            else _TEMP_SETPOINT_MAX_F
        )

    async def _set_temperature(self, temperature: int) -> None:
        await self.system.set_water_temp_setpoint(
            _display_temp_to_wire(temperature)
        )


class TcxWaterSetPoint(TcxDevice, AqualinkNumber):
    """Water heater set point (`TspBdy0.waterTempSet`) — synthetic sibling
    of TcxClimate, same technique as `TcxSolarSetPoint` (built from the
    same TspBdy0 dict, synthetic key `TspBdy0_water`). Duplicates
    TcxClimate.target_temperature as a standalone Number, for consumers
    that want the setpoint without a full Climate entity. Reuses the
    existing, already-confirmed `set_water_temp_setpoint` — same write
    path TcxClimate._set_temperature already calls, no new action."""

    @property
    def label(self) -> str:
        return "Water Heater Set Point"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("waterTempSet")
        return float(_wire_temp_to_display(raw)) if raw is not None else None

    @property
    def min_value(self) -> float:
        return (
            _TEMP_SETPOINT_MIN_C
            if self.system.temp_unit == "C"
            else _TEMP_SETPOINT_MIN_F
        )

    @property
    def max_value(self) -> float:
        return (
            _TEMP_SETPOINT_MAX_C
            if self.system.temp_unit == "C"
            else _TEMP_SETPOINT_MAX_F
        )

    @property
    def unit_of_measurement(self) -> str | None:
        return "°C" if self.system.temp_unit == "C" else "°F"

    async def _set_value(self, value: float) -> None:
        await self.system.set_water_temp_setpoint(
            _display_temp_to_wire(int(value))
        )


class TcxSolarSetPoint(TcxDevice, AqualinkNumber):
    """Solar heater set point (`TspBdy0.solarTempSet`) — synthetic sibling
    of TcxClimate, same technique as lvh1/lvh1_enable (built from the same
    TspBdy0 dict, synthetic key `TspBdy0_solar`). Writable via the
    confirmed `setSolarTempSetpoint` action, same field-name convention as
    `setWaterTempSetpoint` -> `waterTempSet`. Shares TcxClimate's bounds
    (`_TEMP_SETPOINT_MIN/MAX_*`) per the user-supplied spec."""

    @property
    def label(self) -> str:
        return "Solar Heater Set Point"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("solarTempSet")
        return float(_wire_temp_to_display(raw)) if raw is not None else None

    @property
    def min_value(self) -> float:
        return (
            _TEMP_SETPOINT_MIN_C
            if self.system.temp_unit == "C"
            else _TEMP_SETPOINT_MIN_F
        )

    @property
    def max_value(self) -> float:
        return (
            _TEMP_SETPOINT_MAX_C
            if self.system.temp_unit == "C"
            else _TEMP_SETPOINT_MAX_F
        )

    @property
    def unit_of_measurement(self) -> str | None:
        return "°C" if self.system.temp_unit == "C" else "°F"

    async def _set_value(self, value: float) -> None:
        await self.system.set_solar_temp_setpoint(
            _display_temp_to_wire(int(value))
        )


class TcxFreezeSetPoint(TcxDevice, AqualinkNumber):
    """Freeze-protection temperature threshold (top-level `freezeSP`, not
    nested under any device object) — writable via the confirmed
    `setFreezeSetPoint` action. Whole-degree step, same as TcxClimate's
    target_temperature, even though the wire field stores tenths. Bounds
    are unconfirmed defaults — see _FREEZE_SP_MIN/MAX_* above."""

    @property
    def label(self) -> str:
        return "Freeze Protection Set Point"

    @property
    def current_value(self) -> float | None:
        raw = self.data.get("value")
        return float(_wire_temp_to_display(raw)) if raw is not None else None

    @property
    def min_value(self) -> float:
        return (
            _FREEZE_SP_MIN_C
            if self.system.temp_unit == "C"
            else _FREEZE_SP_MIN_F
        )

    @property
    def max_value(self) -> float:
        return (
            _FREEZE_SP_MAX_C
            if self.system.temp_unit == "C"
            else _FREEZE_SP_MAX_F
        )

    @property
    def unit_of_measurement(self) -> str | None:
        return "°C" if self.system.temp_unit == "C" else "°F"

    async def _set_value(self, value: float) -> None:
        await self.system.set_freeze_set_point(
            _display_temp_to_wire(int(value))
        )


class TcxHeaterStatusSensor(TcxDevice, AqualinkSensor):
    """Read-only heater-equipment tile status (lvh1.en), the tcx analog of
    iaqua's IaquaHeatPumpStatusSensor — distinct from TcxClimate, which
    owns TspBdy0's setpoint/enable and has no `lvh1` data of its own."""

    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else "Heater Status"

    @property
    def value(self) -> str:
        en = self.data.get("en")
        return _lvh1_en_to_status(int(en)) if en is not None else ""


class TcxHeaterEnableSwitch(TcxDevice, AqualinkSwitch):
    """Enable/disable switch for lvh1.app ("HEAT"/"OFF") — the tcx analog
    of iaqua's IaquaHeater. Synthetic sibling of TcxHeaterStatusSensor,
    built from the same lvh1 dict (synthetic key `lvh1_enable`)."""

    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        return str(fr) if fr else "Heater Enabled"

    @property
    def is_on(self) -> bool:
        return self.data.get("app") == "HEAT"

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_lvh_app_type(True)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_lvh_app_type(False)


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
    """ZigBee-paired device (e.g. a light) surfaced as a top-level
    `auxz[N]` key in the `_zig` sub-shadow — confirmed by live wire capture
    and protocol research. See docs/reference/systems/tcx.md."""

    @property
    def label(self) -> str:
        fr = self.data.get("fr")
        if fr:
            return str(fr)
        idx = self.name[len("auxz") :]
        return f"ZigBee {idx}"

    @property
    def is_on(self) -> bool:
        return self.data.get("st") == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_zigbee_state(self.name, 1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_zigbee_state(self.name, 0)
