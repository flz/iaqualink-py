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

# Default heater set-point bounds when shadow does not supply them.
_HEAT_MIN_F = 65
_HEAT_MAX_F = 104
_HEAT_MIN_C = 18
_HEAT_MAX_C = 40

# Default freeze-protection set-point bounds when shadow does not supply
# them — unconfirmed, chosen as a plausible range around freezing (same
# caveat as _HEAT_MIN/MAX_* above; see docs/implementation/systems/tcx.md).
_FREEZE_SP_MIN_F = 20
_FREEZE_SP_MAX_F = 50
_FREEZE_SP_MIN_C = -7
_FREEZE_SP_MAX_C = 10


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


# Synthetic device keys for speed (RPM) sensors built from filt0/ecm0
# sub-fields in TcxSystem._update_devices — see _ECM0_EXTRA_SPEED_FIELDS
# there. Not full wire device names, so dispatched by exact match here
# rather than the filt0/ecm0 branches above.
_SPEED_SENSOR_NAMES = frozenset(
    {
        "filt0_manSpd",
        "ecm0_manSpd",
        "ecm0_frzSpd",
        "ecm0_prmSpd",
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
        return _HEAT_MIN_C if self.system.temp_unit == "C" else _HEAT_MIN_F

    @property
    def max_temp(self) -> int:
        return _HEAT_MAX_C if self.system.temp_unit == "C" else _HEAT_MAX_F

    async def _set_temperature(self, temperature: int) -> None:
        await self.system.set_water_temp_setpoint(
            _display_temp_to_wire(temperature)
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
