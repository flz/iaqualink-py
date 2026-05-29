"""Cyclobat device classes."""

from __future__ import annotations

__all__ = [
    "CyclobatBinarySensor",
    "CyclobatDevice",
    "CyclobatRobot",
    "CyclobatSensor",
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
from iaqualink.systems.cyclobat.const import (
    CYCLE_LABELS,
    CYCLOBAT_STATE_CLEANING,
    CYCLOBAT_STATE_RETURNING,
)

if TYPE_CHECKING:
    from iaqualink.systems.cyclobat.system import CyclobatSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running", "returning"})

# Reverse of CYCLE_LABELS: cleaning-mode name -> mode id, for set_fan_speed.
_FAN_SPEED_TO_CYCLE = {label: cid for cid, label in CYCLE_LABELS.items()}

# HA SensorEntity hints, keyed by sensor name. Plain strings the HA
# integration maps onto SensorDeviceClass / SensorStateClass — the library
# stays standalone (no homeassistant dependency). Durations are stored in the
# shadow's native units: time_remaining_sec in seconds, cycle durations and
# totRunTime ("total_runtime") in minutes.
_MEAS = "measurement"
_DUR = "duration"


class _Meta(NamedTuple):
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    numeric: bool = False


_SENSOR_META: dict[str, _Meta] = {
    "battery_percentage": _Meta("battery", "%", _MEAS, numeric=True),
    "temperature": _Meta("temperature", "°C", _MEAS, numeric=True),
    "time_remaining_sec": _Meta(_DUR, "s", _MEAS, numeric=True),
    "total_runtime": _Meta(_DUR, "min", "total_increasing", numeric=True),
    "floor_duration": _Meta(_DUR, "min", _MEAS, numeric=True),
    "floor_walls_duration": _Meta(_DUR, "min", _MEAS, numeric=True),
    "smart_duration": _Meta(_DUR, "min", _MEAS, numeric=True),
    "waterline_duration": _Meta(_DUR, "min", _MEAS, numeric=True),
    "last_cycle_duration": _Meta(_DUR, "min", _MEAS, numeric=True),
}

# HA BinarySensorDeviceClass hints, keyed by binary-sensor name.
_BINARY_DEVICE_CLASS = {"running": "running"}


class CyclobatDevice(AqualinkDevice):
    """Base for cyclobat devices. Concrete subclasses mix in sensor type."""

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
        return self.__class__.__name__.replace("Cyclobat", "")

    @classmethod
    def from_data(
        cls, system: CyclobatSystem, data: DeviceData
    ) -> AqualinkDevice:
        if data["name"] == "robot":
            return CyclobatRobot(system, data)
        if data["name"] in _BINARY_NAMES:
            return CyclobatBinarySensor(system, data)
        return CyclobatSensor(system, data)


class CyclobatSensor(CyclobatDevice, AqualinkSensor):
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


class CyclobatBinarySensor(CyclobatDevice, AqualinkBinarySensor):
    """Binary indicator derived from the shadow state (running, returning)."""

    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))

    @property
    def device_class(self) -> str | None:
        return _BINARY_DEVICE_CLASS.get(self.name)

    @property
    def entity_category(self) -> str | None:
        # running/returning duplicate the robot's `activity` — diagnostic only.
        return "diagnostic"


class CyclobatRobot(CyclobatDevice, AqualinkRobot):
    """Battery Zodiac cleaner exposed as an HA vacuum.

    Reads live runtime off ``system._robot_state["main"]`` so ``activity`` and
    ``fan_speed`` always reflect the latest shadow. Write commands delegate to
    the system, which owns the WebSocket transport.
    """

    @property
    def _main(self) -> dict[str, Any]:
        return self.system._robot_state.get("main") or {}

    @property
    def activity(self) -> AqualinkRobotActivity:
        if int(self._main.get("error") or 0) != 0:
            return AqualinkRobotActivity.ERROR
        state = self._main.get("state")
        if state == CYCLOBAT_STATE_CLEANING:
            return AqualinkRobotActivity.CLEANING
        if state == CYCLOBAT_STATE_RETURNING:
            return AqualinkRobotActivity.RETURNING
        # Battery cleaner idles on its charger; treat stopped as docked.
        return AqualinkRobotActivity.DOCKED

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

    @property
    def fan_speed(self) -> str | None:
        mode = self._main.get("mode")
        if mode is None:
            return None
        return CYCLE_LABELS.get(int(mode))

    @property
    def fan_speed_list(self) -> list[str] | None:
        return list(CYCLE_LABELS.values())

    async def _set_fan_speed(self, fan_speed: str) -> None:
        cycle = _FAN_SPEED_TO_CYCLE.get(fan_speed)
        if cycle is None:
            raise AqualinkInvalidParameterException(fan_speed)
        await self.system.set_cleaning_mode(cycle)
