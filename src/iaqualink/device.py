from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from iaqualink.exception import AqualinkOperationNotSupportedException

if TYPE_CHECKING:
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink")


class AqualinkDevice(ABC):
    """Abstract base class for all Aqualink devices."""

    def __init__(
        self,
        system: Any,  # Should be AqualinkSystem but causes mypy errors.
        data: DeviceData,
    ):
        self.system = system
        self.data = data

    def __repr__(self) -> str:
        attrs = ["data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({', '.join(attrs)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AqualinkDevice):
            return NotImplemented

        if (
            self.system.serial == other.system.serial
            and self.data == other.data
        ):
            return True
        return False

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-readable label for the device."""
        raise NotImplementedError

    @property
    @abstractmethod
    def state(self) -> str:
        """Current state of the device."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Internal name of the device."""
        raise NotImplementedError

    @property
    @abstractmethod
    def manufacturer(self) -> str:
        """Manufacturer of the device."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        """Model of the device."""
        raise NotImplementedError


class AqualinkSensor(AqualinkDevice):
    pass


class AqualinkBinarySensor(AqualinkSensor):
    """These are non-actionable sensors, essentially read-only on/off."""

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """Whether the sensor is in an 'on' state."""
        raise NotImplementedError


class AqualinkSwitch(AqualinkBinarySensor):
    """A device that can be turned on and off."""

    @abstractmethod
    async def turn_on(self) -> None:
        """Turn the device on."""
        raise NotImplementedError

    @abstractmethod
    async def turn_off(self) -> None:
        """Turn the device off."""
        raise NotImplementedError


class AqualinkLight(AqualinkSwitch):
    """A light device with optional brightness and effect controls."""

    @property
    def brightness(self) -> int | None:
        return None

    @property
    def supports_brightness(self) -> bool:
        return self.brightness is not None

    async def set_brightness(self, _: int) -> None:
        if self.supports_brightness is True:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    @property
    def effect(self) -> str | None:
        return None

    @property
    def supports_effect(self) -> bool:
        return self.effect is not None

    async def set_effect_by_name(self, _: str) -> None:
        if self.supports_effect is True:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def set_effect_by_id(self, _: int) -> None:
        if self.supports_effect is True:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException


class AqualinkThermostat(AqualinkSwitch):
    """A thermostat device that controls temperature."""

    @property
    @abstractmethod
    def unit(self) -> str:
        """Temperature unit (F or C)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def current_temperature(self) -> str:
        """Current temperature reading."""
        raise NotImplementedError

    @property
    @abstractmethod
    def target_temperature(self) -> str:
        """Target temperature setting."""
        raise NotImplementedError

    @property
    @abstractmethod
    def max_temperature(self) -> int:
        """Maximum allowed temperature."""
        raise NotImplementedError

    @property
    @abstractmethod
    def min_temperature(self) -> int:
        """Minimum allowed temperature."""
        raise NotImplementedError

    @abstractmethod
    async def set_temperature(self, temperature: int) -> None:
        """Set the target temperature."""
        raise NotImplementedError
