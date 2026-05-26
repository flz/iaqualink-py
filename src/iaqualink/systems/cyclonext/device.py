"""Cyclonext device classes (read-only sensors)."""

from __future__ import annotations

__all__ = [
    "CyclonextBinarySensor",
    "CyclonextDevice",
    "CyclonextErrorSensor",
    "CyclonextSensor",
]

from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
)

if TYPE_CHECKING:
    from iaqualink.systems.cyclonext.system import CyclonextSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running"})
_ERROR_NAMES = frozenset({"error_code"})


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

    @classmethod
    def from_data(
        cls, system: CyclonextSystem, data: DeviceData
    ) -> AqualinkDevice:
        if data["name"] in _BINARY_NAMES:
            return CyclonextBinarySensor(system, data)
        if data["name"] in _ERROR_NAMES:
            return CyclonextErrorSensor(system, data)
        return CyclonextSensor(system, data)


class CyclonextSensor(CyclonextDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""

    @property
    def value(self) -> str:
        return str(self.data["state"])


class CyclonextErrorSensor(CyclonextSensor):
    """Robot error code; non-zero indicates a fault."""


class CyclonextBinarySensor(CyclonextDevice, AqualinkBinarySensor):
    """Binary indicator derived from the shadow state (running)."""

    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
