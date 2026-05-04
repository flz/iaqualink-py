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
    from iaqualink.systems.cyclonext.system import CyclonextSystem

LOGGER = logging.getLogger("iaqualink")

_BINARY_NAMES = {"running"}
_ERROR_NAMES = {"error_code"}


class CyclonextDevice(AqualinkDevice):
    def __init__(self, system: CyclonextSystem, data: DeviceData):
        super().__init__(system, data)
        self.system: CyclonextSystem = system

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
        return self.__class__.__name__.replace("Cyclonext", "")

    @classmethod
    def from_data(
        cls, system: CyclonextSystem, data: DeviceData
    ) -> CyclonextDevice:
        class_: type[CyclonextDevice]

        if data["name"] in _BINARY_NAMES:
            class_ = CyclonextBinarySensor
        elif data["name"] in _ERROR_NAMES:
            class_ = CyclonextErrorSensor
        else:
            class_ = CyclonextAttributeSensor

        return class_(system, data)


class CyclonextAttributeSensor(CyclonextDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""


class CyclonextErrorSensor(CyclonextAttributeSensor):
    """Robot error code; non-zero indicates a fault."""


class CyclonextBinarySensor(CyclonextDevice, AqualinkBinarySensor):
    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
