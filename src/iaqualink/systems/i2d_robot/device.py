from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
)
from iaqualink.typing import DeviceData

if TYPE_CHECKING:
    from iaqualink.systems.i2d_robot.system import I2dRobotSystem

LOGGER = logging.getLogger("iaqualink")

_BINARY_NAMES = {"running", "canister_full"}


class I2dDevice(AqualinkDevice):
    def __init__(self, system: I2dRobotSystem, data: DeviceData):
        super().__init__(system, data)
        self.system: I2dRobotSystem = system

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def label(self) -> str:
        return " ".join(p.capitalize() for p in self.name.split("_"))

    @property
    def state(self) -> str:
        return str(self.data["state"])

    @property
    def manufacturer(self) -> str:
        return "Polaris"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("I2d", "")

    @classmethod
    def from_data(cls, system: I2dRobotSystem, data: DeviceData) -> I2dDevice:
        class_: type[I2dDevice]
        if data["name"] in _BINARY_NAMES:
            class_ = I2dBinarySensor
        else:
            class_ = I2dAttributeSensor
        return class_(system, data)


class I2dAttributeSensor(I2dDevice, AqualinkSensor):
    """Read-only scalar attribute parsed from the hex status response."""


class I2dBinarySensor(I2dDevice, AqualinkBinarySensor):
    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
