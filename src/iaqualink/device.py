from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
)

if TYPE_CHECKING:
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink.device")


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

    @property
    def state_enum(self) -> type[Enum] | None:
        return None

    @property
    def state_translated(self) -> str | None:
        cls = self.state_enum
        if cls is None:
            return None
        try:
            return cls(self.state).name
        except ValueError:
            return None


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

    async def turn_on(self) -> None:
        if not self.is_on:
            await self._turn_on()

    async def turn_off(self) -> None:
        if self.is_on:
            await self._turn_off()

    @abstractmethod
    async def _turn_on(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def _turn_off(self) -> None:
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

    async def set_temperature(self, temperature: int) -> None:
        unit = self.unit
        low = self.min_temperature
        high = self.max_temperature
        if temperature not in range(low, high + 1):
            msg = f"{temperature}{unit} isn't a valid temperature ({low}-{high}{unit})."
            raise AqualinkInvalidParameterException(msg)
        await self._apply_temperature(temperature)

    @abstractmethod
    async def _apply_temperature(self, temperature: int) -> None:
        raise NotImplementedError


class AqualinkNumber(AqualinkDevice):
    @property
    @abstractmethod
    def current_value(self) -> float | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def min_value(self) -> float:
        raise NotImplementedError

    @property
    @abstractmethod
    def max_value(self) -> float:
        raise NotImplementedError

    @property
    def step(self) -> float:
        return 1.0

    @property
    def unit(self) -> str | None:
        return None

    async def set_value(self, value: float) -> None:
        if not self.min_value <= value <= self.max_value:
            raise AqualinkInvalidParameterException(
                f"{value} is out of range ({self.min_value}-{self.max_value})."
            )
        if int(value) % int(self.step) != 0:
            raise AqualinkInvalidParameterException(
                f"{int(value)} is not a multiple of {int(self.step)}."
            )
        await self._set_value(value)

    @abstractmethod
    async def _set_value(self, value: float) -> None:
        raise NotImplementedError


class AqualinkPump(AqualinkDevice):
    @property
    def supports_turn_on(self) -> bool:
        return False

    @property
    def supports_turn_off(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        if self.supports_turn_on or self.supports_turn_off:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def turn_on(self) -> None:
        if self.supports_turn_on:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def turn_off(self) -> None:
        if self.supports_turn_off:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    @property
    def supports_presets(self) -> bool:
        return False

    @property
    def supported_presets(self) -> list[str]:
        # subclasses must override this when supports_presets returns True
        if self.supports_presets:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    @property
    def current_preset(self) -> str | None:
        if self.supports_presets:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    @property
    def supports_set_speed_percentage(self) -> bool:
        return False

    async def set_speed_percentage(self, percentage: int) -> None:
        if self.supports_set_speed_percentage:
            if not 0 <= percentage <= 100:
                raise AqualinkInvalidParameterException(percentage)
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def set_preset(self, preset: str) -> None:
        if self.supports_presets:
            if preset not in self.supported_presets:
                raise AqualinkInvalidParameterException(preset)
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException
