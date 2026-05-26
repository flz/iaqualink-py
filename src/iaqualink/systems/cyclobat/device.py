"""Cyclobat device classes (read-only sensors)."""

from __future__ import annotations

__all__ = ["CyclobatBinarySensor", "CyclobatDevice", "CyclobatSensor"]

from typing import TYPE_CHECKING

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
)

if TYPE_CHECKING:
    from iaqualink.systems.cyclobat.system import CyclobatSystem
    from iaqualink.typing import DeviceData

_BINARY_NAMES = frozenset({"running", "returning"})


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
        if data["name"] in _BINARY_NAMES:
            return CyclobatBinarySensor(system, data)
        return CyclobatSensor(system, data)


class CyclobatSensor(CyclobatDevice, AqualinkSensor):
    """Read-only scalar attribute from the robot shadow."""

    @property
    def value(self) -> str:
        return str(self.data["state"])


class CyclobatBinarySensor(CyclobatDevice, AqualinkBinarySensor):
    """Binary indicator derived from the shadow state (running, returning)."""

    @property
    def is_on(self) -> bool:
        return bool(int(self.data["state"]))
