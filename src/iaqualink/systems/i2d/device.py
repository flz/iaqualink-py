from __future__ import annotations

import logging
from enum import IntEnum, unique
from typing import TYPE_CHECKING

from iaqualink.device import AqualinkSwitch
from iaqualink.exception import AqualinkInvalidParameterException

if TYPE_CHECKING:
    from iaqualink.systems.i2d.system import I2DSystem
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink")


@unique
class IQPumpOpMode(IntEnum):
    SCHEDULE = 0
    CUSTOM = 1
    STOP = 2
    QUICK_CLEAN = 3
    TIMED_RUN = 4
    TIMEOUT = 5
    SERVICE_OFF = 7


class IQPumpDevice(AqualinkSwitch):
    def __init__(self, system: I2DSystem, data: DeviceData) -> None:
        super().__init__(system, data)
        self.system: I2DSystem = system

    @property
    def name(self) -> str:
        return self.data["name"]  # serial number

    @property
    def label(self) -> str:
        return self.system.name  # human-readable name from device list

    @property
    def state(self) -> str:
        return self.data.get("runstate", "off")

    @property
    def is_on(self) -> bool:
        return self.state == "on"

    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return "iQPump"

    # --- Motor telemetry (from motordata, flattened at parse time) ---

    @property
    def motor_speed(self) -> int | None:
        val = self.data.get("speed")
        return int(val) if val is not None else None

    @property
    def motor_power(self) -> int | None:
        val = self.data.get("power")
        return int(val) if val is not None else None

    @property
    def motor_temperature(self) -> int | None:
        val = self.data.get("temperature")
        return int(val) if val is not None else None

    @property
    def horsepower(self) -> float | None:
        val = self.data.get("horsepower")
        return float(val) if val is not None else None

    # --- Configuration ---

    @property
    def opmode(self) -> IQPumpOpMode | None:
        val = self.data.get("opmode")
        if val is None:
            return None
        try:
            return IQPumpOpMode(int(val))
        except ValueError:
            return None

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

    # --- Freeze protection ---

    @property
    def freeze_protect_enabled(self) -> bool:
        return self.data.get("freezeprotectenable") == "1"

    @property
    def freeze_protect_active(self) -> bool:
        return self.data.get("freezeprotectstatus") == "1"

    # --- Control ---

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_opmode(IQPumpOpMode.CUSTOM)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_opmode(IQPumpOpMode.STOP)

    async def set_speed(self, rpm: int) -> None:
        """Set custom speed RPM, validating against the pump's configured min/max."""
        low = self.rpm_min or 600
        high = self.rpm_max or 3450
        if rpm not in range(low, high + 1):
            msg = f"{rpm} RPM is out of range ({low}-{high} RPM)."
            raise AqualinkInvalidParameterException(msg)
        await self.system.set_custom_speed(rpm)
