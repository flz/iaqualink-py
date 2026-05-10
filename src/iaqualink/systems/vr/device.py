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
    from iaqualink.systems.vr.system import VrSystem

LOGGER = logging.getLogger("iaqualink")

_BINARY_NAMES = {"running", "returning"}
_ERROR_NAMES = {"error_state"}


class VrDevice(AqualinkDevice):
    def __init__(self, system: VrSystem, data: DeviceData):
        super().__init__(system, data)
        self.system: VrSystem = system

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
        return "Zodiac"

    @property
    def model(self) -> str:
        return self.__class__.__name__.replace("Vr", "")

    @classmethod
    def from_data(cls, system: VrSystem, data: DeviceData) -> VrDevice:
        class_: type[VrDevice]
        if data["name"] in _BINARY_NAMES:
            class_ = VrBinarySensor
        elif data["name"] in _ERROR_NAMES:
            class_ = VrErrorSensor
        else:
            class_ = VrAttributeSensor
        return class_(system, data)


class VrAttributeSensor(VrDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""


class VrErrorSensor(VrAttributeSensor):
    """Robot error state; non-zero / non-empty indicates a fault."""


class VrBinarySensor(VrDevice, AqualinkBinarySensor):
    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
