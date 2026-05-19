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
    """Abstract base for all Aqualink devices."""

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
        """Human-readable display name."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier within the system."""

    @property
    @abstractmethod
    def manufacturer(self) -> str:
        """Device manufacturer name."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Device model name."""


class AqualinkSensor(AqualinkDevice):
    """Read-only sensor. Maps to HA SensorEntity."""

    @property
    @abstractmethod
    def value(self) -> str:
        """Current sensor reading."""

    @property
    def value_enum(self) -> type[Enum] | None:
        return None

    @property
    def value_translated(self) -> str | None:
        cls = self.value_enum
        if cls is None:
            return None
        try:
            return cls(self.value).name
        except ValueError:
            return None

    @property
    def unit_of_measurement(self) -> str | None:
        return None


class AqualinkBinarySensor(AqualinkDevice):
    """Read-only binary sensor. Maps to HA BinarySensorEntity."""

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """True if the sensor is active/on."""


class AqualinkSwitch(AqualinkDevice):
    """Controllable on/off device. Maps to HA SwitchEntity."""

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """True if the device is on."""

    @abstractmethod
    async def turn_on(self) -> None:
        """Turn the device on."""

    @abstractmethod
    async def turn_off(self) -> None:
        """Turn the device off."""


class AqualinkLight(AqualinkDevice):
    """Controllable light. Maps to HA LightEntity."""

    # ── Required overrides ──────────────────────────────────────────────────

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """True if the light is on."""

    @abstractmethod
    async def turn_on(self) -> None:
        """Turn the light on."""

    @abstractmethod
    async def turn_off(self) -> None:
        """Turn the light off."""

    # ── Override if brightness is supported ─────────────────────────────────

    @property
    def brightness_percentage(self) -> int | None:
        return None

    @property
    def supports_brightness(self) -> bool:
        return self.brightness_percentage is not None

    async def set_brightness_percentage(self, brightness: int) -> None:
        """Set brightness as a percentage (0–100)."""
        if not self.supports_brightness:
            raise AqualinkOperationNotSupportedException
        if not 0 <= brightness <= 100:
            raise AqualinkInvalidParameterException(
                f"{brightness}% isn't a valid percentage."
            )
        await self._set_brightness_percentage(brightness)

    async def _set_brightness_percentage(self, brightness: int) -> None:
        """Send the brightness percentage to the device."""
        raise NotImplementedError

    # ── Override if effects are supported ────────────────────────────────────

    @property
    def effect(self) -> str | None:
        return None

    @property
    def effect_list(self) -> list[str] | None:
        return None

    @property
    def supports_effect(self) -> bool:
        return self.effect_list is not None

    async def set_effect(self, effect: str) -> None:
        """Activate a light effect by name."""
        if not self.supports_effect:
            raise AqualinkOperationNotSupportedException
        effect_list = self.effect_list
        if effect_list is not None and effect not in effect_list:
            raise AqualinkInvalidParameterException(
                f"{effect!r} isn't a valid effect."
            )
        await self._set_effect(effect)

    async def _set_effect(self, effect: str) -> None:
        """Send the named effect to the device."""
        raise NotImplementedError


class AqualinkClimate(AqualinkDevice):
    """Climate control. Maps to HA ClimateEntity."""

    # ── Required overrides ──────────────────────────────────────────────────

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """True if heating/cooling is active."""

    @abstractmethod
    async def turn_on(self) -> None:
        """Enable climate control."""

    @abstractmethod
    async def turn_off(self) -> None:
        """Disable climate control."""

    @property
    @abstractmethod
    def temperature_unit(self) -> str:
        """Unit of temperature: 'C' or 'F'."""

    @property
    @abstractmethod
    def current_temperature(self) -> str:
        """Current measured temperature."""

    @property
    @abstractmethod
    def target_temperature(self) -> str:
        """Desired set-point temperature."""

    @property
    @abstractmethod
    def max_temp(self) -> int:
        """Maximum allowed set-point."""

    @property
    @abstractmethod
    def min_temp(self) -> int:
        """Minimum allowed set-point."""

    @abstractmethod
    async def _set_temperature(self, temperature: int) -> None:
        """Send the validated temperature to the device."""

    # ── Template (do not override) ───────────────────────────────────────────

    async def set_temperature(self, temperature: int) -> None:
        """Set the target temperature."""
        low = self.min_temp
        high = self.max_temp
        unit = self.temperature_unit
        if temperature not in range(low, high + 1):
            msg = f"{temperature}{unit} isn't a valid temperature"
            msg += f" ({low}-{high}{unit})."
            raise AqualinkInvalidParameterException(msg)
        await self._set_temperature(temperature)


class AqualinkNumber(AqualinkDevice):
    """Writable numeric setting. Maps to HA NumberEntity."""

    # ── Required overrides ──────────────────────────────────────────────────

    @property
    @abstractmethod
    def current_value(self) -> float | None:
        """Current numeric value, or None if unavailable."""

    @property
    @abstractmethod
    def min_value(self) -> float:
        """Minimum allowed value."""

    @property
    @abstractmethod
    def max_value(self) -> float:
        """Maximum allowed value."""

    @abstractmethod
    async def _set_value(self, value: float) -> None:
        """Write the value to the device."""

    # ── Optional overrides ───────────────────────────────────────────────────

    @property
    def step(self) -> float:
        return 1.0

    @property
    def unit_of_measurement(self) -> str | None:
        return None

    # ── Template (do not override) ───────────────────────────────────────────

    async def set_value(self, value: float) -> None:
        """Set the numeric value (validates range and step)."""
        if not self.min_value <= value <= self.max_value:
            raise AqualinkInvalidParameterException(
                f"{value} is out of range ({self.min_value}-{self.max_value})."
            )
        if int(value) % int(self.step) != 0:
            raise AqualinkInvalidParameterException(
                f"{int(value)} is not a multiple of {int(self.step)}."
            )
        await self._set_value(value)


class AqualinkFan(AqualinkDevice):
    """Fan/pump control. Maps to HA FanEntity."""

    # HA has no PumpEntity; FanEntity is the closest available mapping.

    # ── Override if turn-on/off is supported (set supports_turn_on/off=True) ─

    @property
    def supports_turn_on(self) -> bool:
        return False

    @property
    def supports_turn_off(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        """True if the fan/pump is running."""
        if self.supports_turn_on or self.supports_turn_off:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def turn_on(self) -> None:
        """Turn the fan/pump on."""
        if self.supports_turn_on:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def turn_off(self) -> None:
        """Turn the fan/pump off."""
        if self.supports_turn_off:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    # ── Override if presets are supported (set supports_presets=True) ────────

    @property
    def supports_presets(self) -> bool:
        return False

    @property
    def preset_modes(self) -> list[str]:
        """List of available preset mode names."""
        # subclasses must override this when supports_presets returns True
        if self.supports_presets:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    @property
    def preset_mode(self) -> str | None:
        """Currently active preset mode."""
        if self.supports_presets:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def _set_preset_mode(self, preset_mode: str) -> None:
        """Send the preset mode to the device."""
        raise NotImplementedError

    # ── Override if speed control is supported (set supports_percentage=True) ─

    @property
    def supports_percentage(self) -> bool:
        return False

    async def _set_percentage(self, percentage: int) -> None:
        """Send the speed percentage to the device."""
        raise NotImplementedError

    # ── Templates (do not override) ──────────────────────────────────────────

    async def set_percentage(self, percentage: int) -> None:
        """Set fan/pump speed as a percentage (0–100)."""
        if not self.supports_percentage:
            raise AqualinkOperationNotSupportedException
        if not 0 <= percentage <= 100:
            raise AqualinkInvalidParameterException(
                f"Percentage {percentage} out of range (0-100)."
            )
        await self._set_percentage(percentage)

    async def set_preset_mode(self, preset_mode: str) -> None:
        """Activate a preset mode by name."""
        if not self.supports_presets:
            raise AqualinkOperationNotSupportedException
        if preset_mode not in self.preset_modes:
            raise AqualinkInvalidParameterException(preset_mode)
        await self._set_preset_mode(preset_mode)
