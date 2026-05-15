from __future__ import annotations

import logging
from enum import StrEnum, unique
from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkNumber,
    AqualinkPump,
    AqualinkSensor,
    AqualinkSwitch,
)
from iaqualink.exception import AqualinkInvalidParameterException

if TYPE_CHECKING:
    from iaqualink.systems.i2d.system import I2dSystem
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink")


@unique
class I2dBinaryState(StrEnum):
    OFF = "0"
    ON = "1"


@unique
class I2dRunState(StrEnum):
    ON = "on"
    OFF = "off"


_RPM_HARDWARE_MIN_DEFAULT = 600
_RPM_HARDWARE_MAX = 3450
_RPM_STEP = 25


class I2dDevice:
    """Shared properties for all iQPump sub-devices."""

    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return "iQPump"


class I2dSensor(I2dDevice, AqualinkSensor):
    """Read-only telemetry value from an iQPump device."""

    def __init__(
        self,
        system: I2dSystem,
        data: DeviceData,
        key: str,
        label: str,
        unit: str | None = None,
    ) -> None:
        super().__init__(system, data)
        self.system: I2dSystem = system
        self._key = key
        self._label = label
        self._unit = unit

    @property
    def name(self) -> str:
        return self._key

    @property
    def label(self) -> str:
        return self._label

    @property
    def state(self) -> str:
        return str(self.data.get(self._key, ""))

    @property
    def unit(self) -> str | None:
        return self._unit


@unique
class I2dOpMode(StrEnum):
    SCHEDULE = "0"
    CUSTOM = "1"
    STOP = "2"
    QUICK_CLEAN = "3"
    TIMED_RUN = "4"
    TIMEOUT = "5"
    SERVICE_OFF = "7"  # value 6 undefined in hardware protocol


# Modes the user can request; others are entered automatically by the pump.
SETTABLE_OPMODES: tuple[I2dOpMode, ...] = (
    I2dOpMode.SCHEDULE,
    I2dOpMode.CUSTOM,
    I2dOpMode.STOP,
)


class I2dPump(I2dDevice, AqualinkPump):
    def __init__(self, system: I2dSystem, data: DeviceData) -> None:
        super().__init__(system, data)
        self.system: I2dSystem = system

    @property
    def name(self) -> str:
        return self.data["name"]  # serial number

    @property
    def label(self) -> str:
        return self.system.name  # human-readable name from device list

    @property
    def state(self) -> str:
        return self.data.get("opmode", "")

    state_enum = I2dOpMode

    @property
    def supports_turn_on(self) -> bool:
        return True

    @property
    def supports_turn_off(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.data.get("runstate") == I2dRunState.ON

    # --- Configuration ---

    @property
    def rpm_min(self) -> int | None:
        val = self.data.get("globalrpmmin")
        return int(val) if val is not None else None

    @property
    def rpm_max(self) -> int | None:
        val = self.data.get("globalrpmmax")
        return int(val) if val is not None else None

    @property
    def custom_speed_rpm(self) -> int | None:
        val = self.data.get("customspeedrpm")
        return int(val) if val is not None else None

    # --- Control ---

    async def turn_on(self) -> None:
        if not self.is_on:
            r = await self.system.send_control_command(
                "/opmode/write", f"value={I2dOpMode.CUSTOM}"
            )
            r.raise_for_status()

    async def turn_off(self) -> None:
        if self.is_on:
            r = await self.system.send_control_command(
                "/opmode/write", f"value={I2dOpMode.STOP}"
            )
            r.raise_for_status()

    # --- Speed percentage ---

    @property
    def supports_set_speed_percentage(self) -> bool:
        return True

    async def set_speed_percentage(self, percentage: int) -> None:
        if not 0 <= percentage <= 100:
            raise AqualinkInvalidParameterException(
                f"Percentage {percentage} out of range (0-100)."
            )
        rpm_min = self.rpm_min or _RPM_HARDWARE_MIN_DEFAULT
        rpm_max = self.rpm_max or _RPM_HARDWARE_MAX
        raw = rpm_min + (rpm_max - rpm_min) * percentage / 100
        rounded = round(raw / _RPM_STEP) * _RPM_STEP
        rpm = max(rpm_min, min(rpm_max, rounded))
        r = await self.system.send_control_command(
            "/customspeedrpm/write", f"value={rpm}"
        )
        r.raise_for_status()

    # --- Presets (user-settable opmodes) ---

    @property
    def supports_presets(self) -> bool:
        return True

    @property
    def supported_presets(self) -> list[str]:
        return [m.name for m in SETTABLE_OPMODES]

    @property
    def current_preset(self) -> str | None:
        return self.state_translated

    async def set_preset(self, preset: str) -> None:
        if preset not in self.supported_presets:
            raise AqualinkInvalidParameterException(
                f"{preset!r} is not a valid preset. Valid: {self.supported_presets}"
            )
        r = await self.system.send_control_command(
            "/opmode/write", f"value={I2dOpMode[preset]}"
        )
        r.raise_for_status()


class I2dNumber(I2dDevice, AqualinkNumber):
    """Writable numeric setting on an iQPump, read via /alldata/read."""

    def __init__(
        self,
        system: I2dSystem,
        data: DeviceData,
        key: str,
        label: str,
        min_value: float | None = None,
        max_value: float | None = None,
        min_key: str | None = None,
        max_key: str | None = None,
        step: float = 1.0,
        unit: str | None = None,
    ) -> None:
        if min_key is None and min_value is None:
            raise ValueError(f"Either min_value or min_key required for {key}")
        if max_key is None and max_value is None:
            raise ValueError(f"Either max_value or max_key required for {key}")
        super().__init__(system, data)
        self.system: I2dSystem = system
        self._key = key
        self._label = label
        self._min_value = min_value
        self._max_value = max_value
        self._min_key = min_key
        self._max_key = max_key
        self._step = step
        self._unit = unit

    @property
    def name(self) -> str:
        return self._key

    @property
    def label(self) -> str:
        return self._label

    @property
    def state(self) -> str:
        val = self.current_value
        return "" if val is None else str(int(val))

    @property
    def current_value(self) -> float | None:
        val = self.data.get(self._key)
        return float(val) if val is not None else None

    @property
    def min_value(self) -> float:
        if self._min_key is not None:
            return float(self.data[self._min_key])
        return self._min_value  # type: ignore[return-value]

    @property
    def max_value(self) -> float:
        if self._max_key is not None:
            return float(self.data[self._max_key])
        return self._max_value  # type: ignore[return-value]

    @property
    def step(self) -> float:
        return self._step

    @property
    def unit(self) -> str | None:
        return self._unit

    async def _set_value(self, value: float) -> None:
        r = await self.system.send_control_command(
            f"/{self._key}/write", f"value={int(value)}"
        )
        r.raise_for_status()


class I2dSwitch(I2dDevice, AqualinkSwitch):
    """Writable on/off setting on an iQPump, read via /alldata/read."""

    def __init__(
        self,
        system: I2dSystem,
        data: DeviceData,
        key: str,
        label: str,
    ) -> None:
        super().__init__(system, data)
        self.system: I2dSystem = system
        self._key = key
        self._label = label

    @property
    def name(self) -> str:
        return self._key

    @property
    def label(self) -> str:
        return self._label

    @property
    def state(self) -> str:
        return "on" if self.is_on else "off"

    @property
    def is_on(self) -> bool:
        return self.data.get(self._key) == I2dBinaryState.ON

    async def turn_on(self) -> None:
        r = await self.system.send_control_command(
            f"/{self._key}/write", f"value={I2dBinaryState.ON}"
        )
        r.raise_for_status()

    async def turn_off(self) -> None:
        r = await self.system.send_control_command(
            f"/{self._key}/write", f"value={I2dBinaryState.OFF}"
        )
        r.raise_for_status()
