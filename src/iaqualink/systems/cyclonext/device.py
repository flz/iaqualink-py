"""Cyclonext device classes (read-only sensors)."""

from __future__ import annotations

__all__ = [
    "CyclonextBinarySensor",
    "CyclonextDevice",
    "CyclonextErrorSensor",
    "CyclonextRobot",
    "CyclonextSensor",
]

from typing import TYPE_CHECKING, Any, NamedTuple

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkRobot,
    AqualinkRobotActivity,
    AqualinkSensor,
)
from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.systems.cyclonext.const import (
    CYCLE_LABELS,
    MODE_REMOTE,
    MODE_START,
)

if TYPE_CHECKING:
    from iaqualink.systems.cyclonext.system import CyclonextSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running"})
_ERROR_NAMES = frozenset({"error_code"})

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
    "time_remaining_sec": _Meta(_DUR, "s", _MEAS, numeric=True),
    "stepper": _Meta(_DUR, "min", _MEAS, numeric=True),
    "error_code": _Meta(numeric=True),
}

# Sensors marked HA diagnostic: firmware/identifiers + state that merely
# duplicates the robot's `activity`. `ebox_*` are hardware identifiers.
_DIAGNOSTIC_NAMES = frozenset(
    {"error_code", "running", "control_box_vr", "model_number"}
)

# HA BinarySensorDeviceClass by binary-sensor name.
_BINARY_DEVICE_CLASS = {"running": "running"}


class CyclonextDevice(AqualinkDevice):
    """Base for cyclonext devices. Concrete subclasses mix in sensor type."""

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
        return self.__class__.__name__.replace("Cyclonext", "")

    @property
    def entity_category(self) -> str | None:
        if self.name in _DIAGNOSTIC_NAMES or self.name.startswith("ebox_"):
            return "diagnostic"
        return None

    @classmethod
    def from_data(
        cls, system: CyclonextSystem, data: DeviceData
    ) -> AqualinkDevice:
        if data["name"] == "robot":
            return CyclonextRobot(system, data)
        if data["name"] in _BINARY_NAMES:
            return CyclonextBinarySensor(system, data)
        if data["name"] in _ERROR_NAMES:
            return CyclonextErrorSensor(system, data)
        return CyclonextSensor(system, data)


class CyclonextSensor(CyclonextDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""

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


class CyclonextErrorSensor(CyclonextSensor):
    """Robot error code; non-zero indicates a fault."""


class CyclonextBinarySensor(CyclonextDevice, AqualinkBinarySensor):
    """Binary indicator derived from the shadow state (running)."""

    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))

    @property
    def device_class(self) -> str | None:
        return _BINARY_DEVICE_CLASS.get(self.name)


class CyclonextRobot(CyclonextDevice, AqualinkRobot):
    """Wired Zodiac cleaner exposed as an HA vacuum.

    Reads live runtime off ``system._robot_state`` (the equipment.robot[1]
    dict) so ``activity`` and ``fan_speed`` reflect the latest shadow. Write
    commands delegate to the system, which owns the WebSocket transport.
    """

    @property
    def _robot(self) -> dict[str, Any]:
        return self.system._robot_state or {}

    @property
    def activity(self) -> AqualinkRobotActivity:
        if int((self._robot.get("errors") or {}).get("code") or 0) != 0:
            return AqualinkRobotActivity.ERROR
        mode = self._robot.get("mode")
        if mode == MODE_START:
            return AqualinkRobotActivity.CLEANING
        # Remote-control surface (mode 2): mid-job, manually driven, not
        # autonomously cleaning -> paused. Lift-system (mode 3) and stop are
        # not a "paused cycle", and a wired robot has no dock -> idle.
        if mode == MODE_REMOTE:
            return AqualinkRobotActivity.PAUSED
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
        # Wired robot: no dock. "Return" maps to the canonical stop frame.
        await self.system.stop_cleaning()

    @property
    def fan_speed(self) -> str | None:
        cycle = self._robot.get("cycle")
        if cycle is None:
            return None
        return CYCLE_LABELS.get(int(cycle))

    @property
    def fan_speed_list(self) -> list[str] | None:
        return list(CYCLE_LABELS.values())

    async def _set_fan_speed(self, fan_speed: str) -> None:
        cycle = _FAN_SPEED_TO_CYCLE.get(fan_speed)
        if cycle is None:
            raise AqualinkInvalidParameterException(fan_speed)
        await self.system.set_cycle(cycle)
