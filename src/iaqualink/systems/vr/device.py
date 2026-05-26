"""VR device classes (read-only sensors)."""

from __future__ import annotations

__all__ = [
    "VrBinarySensor",
    "VrDevice",
    "VrErrorSensor",
    "VrSensor",
]

from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
)

if TYPE_CHECKING:
    from iaqualink.systems.vr.system import VrSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running", "returning"})
_ERROR_NAMES = frozenset({"error_state"})


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

    @classmethod
    def from_data(cls, system: VrSystem, data: DeviceData) -> AqualinkDevice:
        if data["name"] in _BINARY_NAMES:
            return VrBinarySensor(system, data)
        if data["name"] in _ERROR_NAMES:
            return VrErrorSensor(system, data)
        return VrSensor(system, data)


class VrSensor(VrDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""

    @property
    def value(self) -> str:
        return str(self.data["state"])


class VrErrorSensor(VrSensor):
    """Robot error state; non-zero indicates a fault."""


class VrBinarySensor(VrDevice, AqualinkBinarySensor):
    """Binary indicator derived from the shadow state (running, returning)."""

    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
