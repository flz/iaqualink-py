"""i2d_robot device classes (read-only sensors)."""

from __future__ import annotations

__all__ = ["I2dBinarySensor", "I2dDevice", "I2dRobot", "I2dSensor"]

from typing import TYPE_CHECKING, NamedTuple

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkRobot,
    AqualinkRobotActivity,
    AqualinkSensor,
)

if TYPE_CHECKING:
    from iaqualink.systems.i2d_robot.system import I2dRobotSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running", "canister_full"})

# Wire state-byte values (data[2]) for HA activity mapping.
_STATE_CLEANING = frozenset({0x02, 0x04})
_STATE_ERROR = frozenset({0x0D, 0x0E})
_STATE_PAUSED = 0x0C
_STATE_DOCKED = 0x01

_MEAS = "measurement"
_DUR = "duration"


class _Meta(NamedTuple):
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    numeric: bool = False


# HA SensorEntity hints by sensor name. total_hours is hours; the *_min /
# *_minutes counters are minutes (distinct wire fields).
_SENSOR_META: dict[str, _Meta] = {
    "time_remaining_min": _Meta(_DUR, "min", _MEAS, numeric=True),
    "uptime_minutes": _Meta(_DUR, "min", _MEAS, numeric=True),
    "total_hours": _Meta(_DUR, "h", "total_increasing", numeric=True),
    "error_code": _Meta(numeric=True),
}

# Identifiers + raw hex codes + state that duplicates the robot's `activity`.
_DIAGNOSTIC_NAMES = frozenset(
    {
        "state_code",
        "mode_code",
        "error_code",
        "hardware_id",
        "firmware_id",
        "model_number",
        "running",
        "uptime_minutes",
        "state",
    }
)

# HA BinarySensorDeviceClass by binary-sensor name.
_BINARY_DEVICE_CLASS = {"running": "running", "canister_full": "problem"}


class I2dDevice(AqualinkDevice):
    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def label(self) -> str:
        return " ".join(p.capitalize() for p in self.name.split("_"))

    @property
    def manufacturer(self) -> str:
        return "Polaris"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("I2d", "")

    @property
    def entity_category(self) -> str | None:
        if self.name in _DIAGNOSTIC_NAMES:
            return "diagnostic"
        return None

    @classmethod
    def from_data(
        cls, system: I2dRobotSystem, data: DeviceData
    ) -> AqualinkDevice:
        if data["name"] == "robot":
            return I2dRobot(system, data)
        if data["name"] in _BINARY_NAMES:
            return I2dBinarySensor(system, data)
        return I2dSensor(system, data)


class I2dSensor(I2dDevice, AqualinkSensor):
    @property
    def _meta(self) -> _Meta:
        return _SENSOR_META.get(self.name, _Meta())

    @property
    def value(self) -> str:
        return str(self.data["state"])

    @property
    def device_class(self) -> str | None:
        return self._meta.device_class

    @property
    def unit_of_measurement(self) -> str | None:
        return self._meta.unit

    @property
    def state_class(self) -> str | None:
        return self._meta.state_class

    @property
    def native_value(self) -> float | int | str | None:
        if not self._meta.numeric:
            return self.value
        try:
            num = float(self.value)
        except (TypeError, ValueError):
            return None
        return int(num) if num.is_integer() else num


class I2dBinarySensor(I2dDevice, AqualinkBinarySensor):
    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))

    @property
    def device_class(self) -> str | None:
        return _BINARY_DEVICE_CLASS.get(self.name)


class I2dRobot(I2dDevice, AqualinkRobot):
    """Polaris iqPump cleaner exposed as an HA vacuum.

    Reads live state off ``system._state_code`` / ``_error_code`` (last parsed
    hex status); start/stop/return delegate to the system's HTTP commands. i2d
    has no pause or cycle-select command, so those caps stay off — a paused
    state is observe-only via ``activity``.
    """

    @property
    def activity(self) -> AqualinkRobotActivity:
        if self.system._error_code or self.system._state_code in _STATE_ERROR:
            return AqualinkRobotActivity.ERROR
        code = self.system._state_code
        if code in _STATE_CLEANING:
            return AqualinkRobotActivity.CLEANING
        if code == _STATE_PAUSED:
            return AqualinkRobotActivity.PAUSED
        if code == _STATE_DOCKED:
            return AqualinkRobotActivity.DOCKED
        # finished / unknown / None -> idle.
        return AqualinkRobotActivity.IDLE

    @property
    def supports_start(self) -> bool:
        return True

    @property
    def supports_stop(self) -> bool:
        return True

    @property
    def supports_return(self) -> bool:
        return True

    async def _start(self) -> None:
        await self.system.start_cleaning()

    async def _stop(self) -> None:
        await self.system.stop_cleaning()

    async def _return_to_base(self) -> None:
        await self.system.return_to_base()
