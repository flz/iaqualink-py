"""VR device classes (read-only sensors)."""

from __future__ import annotations

__all__ = [
    "VrBinarySensor",
    "VrDevice",
    "VrErrorSensor",
    "VrRobot",
    "VrSensor",
]

from typing import TYPE_CHECKING, Any, NamedTuple

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
    AqualinkVacuum,
)
from iaqualink.enums import AqualinkRobotActivity
from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.systems.vr.const import (
    CYCLE_LABELS,
    VR_STATE_CLEANING,
    VR_STATE_PAUSED,
    VR_STATE_RETURNING,
)

if TYPE_CHECKING:
    from iaqualink.systems.vr.system import VrSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running", "returning"})
_ERROR_NAMES = frozenset({"error_state"})

# Reverse of CYCLE_LABELS: cleaning-mode name -> cycle id, for set_fan_speed.
_FAN_SPEED_TO_CYCLE = {label: cid for cid, label in CYCLE_LABELS.items()}

# HA SensorEntity hints by sensor name (plain strings the HA integration maps
# onto SensorDeviceClass / SensorStateClass — library stays standalone).
# stepper is the runtime stepper in minutes; time_remaining_sec in seconds.
_MEAS = "measurement"
_DUR = "duration"


class _Meta(NamedTuple):
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    numeric: bool = False


_SENSOR_META: dict[str, _Meta] = {
    "temperature": _Meta("temperature", "°C", _MEAS, numeric=True),
    "time_remaining_sec": _Meta(_DUR, "s", _MEAS, numeric=True),
    "stepper": _Meta(_DUR, "min", _MEAS, numeric=True),
    "error_state": _Meta(numeric=True),
}

# Sensors marked HA diagnostic: firmware/identifiers + state that merely
# duplicates the robot's `activity`. (product_number is the vortrax subclass's
# eboxData identifier.)
_DIAGNOSTIC_NAMES = frozenset(
    {
        "error_state",
        "running",
        "returning",
        "vr",
        "model_number",
        "product_number",
    }
)

# HA BinarySensorDeviceClass by binary-sensor name.
_BINARY_DEVICE_CLASS = {"running": "running"}


class VrDevice(AqualinkDevice):
    """Base for vr devices. Concrete subclasses mix in sensor type."""

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def label(self) -> str:
        return " ".join(p.capitalize() for p in self.name.split("_"))

    @property
    def manufacturer(self) -> str:
        return "Zodiac"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Vr", "")

    @property
    def entity_category(self) -> str | None:
        if self.name in _DIAGNOSTIC_NAMES:
            return "diagnostic"
        return None

    @classmethod
    def from_data(cls, system: VrSystem, data: DeviceData) -> AqualinkDevice:
        if data["name"] == "robot":
            return VrRobot(system, data)
        if data["name"] in _BINARY_NAMES:
            return VrBinarySensor(system, data)
        if data["name"] in _ERROR_NAMES:
            return VrErrorSensor(system, data)
        return VrSensor(system, data)


class VrSensor(VrDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""

    @property
    def _meta(self) -> _Meta:
        return _SENSOR_META.get(self.name, _Meta())

    @property
    def value(self) -> float | int | str | None:
        raw = str(self.data["state"])
        if not self._meta.numeric:
            return raw
        try:
            num = float(raw)
        except (TypeError, ValueError):
            return None
        return int(num) if num.is_integer() else num

    @property
    def device_class(self) -> str | None:
        return self._meta.device_class

    @property
    def unit_of_measurement(self) -> str | None:
        return self._meta.unit

    @property
    def state_class(self) -> str | None:
        return self._meta.state_class


class VrErrorSensor(VrSensor):
    """Robot error state; non-zero indicates a fault."""


class VrBinarySensor(VrDevice, AqualinkBinarySensor):
    """Binary indicator derived from the shadow state (running, returning)."""

    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))

    @property
    def device_class(self) -> str | None:
        return _BINARY_DEVICE_CLASS.get(self.name)


class VrRobot(VrDevice, AqualinkVacuum):
    """Polaris VRX variable-speed cleaner exposed as an HA vacuum.

    Reads live runtime off ``system._robot_state`` (the equipment.robot dict)
    so ``activity`` and ``fan_speed`` reflect the latest shadow. Write commands
    delegate to the system, which owns the WebSocket transport. Unlike the
    other robots, vr has native paused and returning states, so it maps onto
    the full HA vacuum surface (including a real ``return_to_base``).
    """

    @property
    def _robot(self) -> dict[str, Any]:
        return self.system._robot_state or {}

    @property
    def activity(self) -> AqualinkRobotActivity:
        if int(self._robot.get("errorState") or 0) != 0:
            return AqualinkRobotActivity.ERROR
        state = self._robot.get("state")
        if state == VR_STATE_CLEANING:
            return AqualinkRobotActivity.CLEANING
        if state == VR_STATE_PAUSED:
            return AqualinkRobotActivity.PAUSED
        if state == VR_STATE_RETURNING:
            return AqualinkRobotActivity.RETURNING
        # Stopped/unknown: VR robots have no charging dock -> idle.
        return AqualinkRobotActivity.IDLE

    @property
    def supports_start(self) -> bool:
        return True

    @property
    def supports_stop(self) -> bool:
        return True

    @property
    def supports_pause(self) -> bool:
        return True

    @property
    def supports_return(self) -> bool:
        return True

    async def _start(self) -> None:
        await self.system.start_cleaning()

    async def _stop(self) -> None:
        await self.system.stop_cleaning()

    async def _pause(self) -> None:
        await self.system.pause_cleaning()

    async def _return_to_base(self) -> None:
        await self.system.return_to_base()

    @property
    def fan_speed(self) -> str | None:
        cycle = self._robot.get("prCyc")
        if cycle is None:
            return None
        return CYCLE_LABELS.get(int(cycle))

    @property
    def fan_speed_list(self) -> list[str]:
        return list(CYCLE_LABELS.values())

    async def _set_fan_speed(self, fan_speed: str) -> None:
        cycle = _FAN_SPEED_TO_CYCLE.get(fan_speed)
        if cycle is None:
            raise AqualinkInvalidParameterException(fan_speed)
        await self.system.set_cycle(cycle)
