"""i2d_robot device classes (read-only sensors)."""

from __future__ import annotations

__all__ = ["I2dBinarySensor", "I2dDevice", "I2dSensor"]

from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
)

if TYPE_CHECKING:
    from iaqualink.systems.i2d_robot.system import I2dRobotSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running", "canister_full"})


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

    @classmethod
    def from_data(
        cls, system: I2dRobotSystem, data: DeviceData
    ) -> AqualinkDevice:
        if data["name"] in _BINARY_NAMES:
            return I2dBinarySensor(system, data)
        return I2dSensor(system, data)


class I2dSensor(I2dDevice, AqualinkSensor):
    @property
    def value(self) -> str:
        return str(self.data["state"])


class I2dBinarySensor(I2dDevice, AqualinkBinarySensor):
    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
