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
    from iaqualink.systems.cyclobat.system import CyclobatSystem

LOGGER = logging.getLogger("iaqualink")

_BINARY_NAMES = {"running", "returning"}


class CyclobatDevice(AqualinkDevice):
    def __init__(self, system: CyclobatSystem, data: DeviceData):
        super().__init__(system, data)
        self.system: CyclobatSystem = system

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
        return self.__class__.__name__.replace("Cyclobat", "")

    @classmethod
    def from_data(
        cls, system: CyclobatSystem, data: DeviceData
    ) -> CyclobatDevice:
        class_: type[CyclobatDevice]
        if data["name"] in _BINARY_NAMES:
            class_ = CyclobatBinarySensor
        else:
            class_ = CyclobatAttributeSensor
        return class_(system, data)


class CyclobatAttributeSensor(CyclobatDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""


class CyclobatBinarySensor(CyclobatDevice, AqualinkBinarySensor):
    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
