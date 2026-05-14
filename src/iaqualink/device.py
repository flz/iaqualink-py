from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
)

if TYPE_CHECKING:
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink")


class AqualinkDevice:
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
    def label(self) -> str:
        raise NotImplementedError

    @property
    def state(self) -> str:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def manufacturer(self) -> str:
        raise NotImplementedError

    @property
    def model(self) -> str:
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
    def is_on(self) -> bool:
        raise NotImplementedError


class AqualinkSwitch(AqualinkBinarySensor, AqualinkDevice):
    async def turn_on(self) -> None:
        raise NotImplementedError

    async def turn_off(self) -> None:
        raise NotImplementedError


class AqualinkLight(AqualinkSwitch, AqualinkDevice):
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


class AqualinkThermostat(AqualinkSwitch, AqualinkDevice):
    @property
    def unit(self) -> str:
        raise NotImplementedError

    @property
    def current_temperature(self) -> str:
        raise NotImplementedError

    @property
    def target_temperature(self) -> str:
        raise NotImplementedError

    @property
    def max_temperature(self) -> int:
        raise NotImplementedError

    @property
    def min_temperature(self) -> int:
        raise NotImplementedError

    async def set_temperature(self, _: int) -> None:
        raise NotImplementedError


class AqualinkNumber(AqualinkDevice):
    @property
    def current_value(self) -> float | None:
        raise NotImplementedError

    @property
    def min_value(self) -> float:
        raise NotImplementedError

    @property
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
            msg = (
                f"{value} is out of range ({self.min_value}-{self.max_value})."
            )
            raise AqualinkInvalidParameterException(msg)
        await self._set_value(value)

    async def _set_value(self, value: float) -> None:
        raise NotImplementedError


class AqualinkPump(AqualinkSwitch, AqualinkDevice):
    # Some pump models are always-on; supports_turn_off=False signals this.
    # Unlike AqualinkSwitch (which raises NotImplementedError unconditionally),
    # AqualinkPump gates turn_on/turn_off behind capability flags so subclasses
    # can advertise non-switchable pumps without overriding both methods.
    @property
    def supports_turn_on(self) -> bool:
        return True

    @property
    def supports_turn_off(self) -> bool:
        return True

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
        if self.supports_presets:
            raise NotImplementedError
        return []

    @property
    def current_preset(self) -> str | None:
        if self.supports_presets:
            raise NotImplementedError
        return None

    @property
    def supports_set_speed(self) -> bool:
        return False

    async def set_speed(self, _: int) -> None:
        """Set absolute speed (e.g. RPM). Valid range is device-specific."""
        if self.supports_set_speed:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    @property
    def supports_set_speed_percentage(self) -> bool:
        return False

    async def set_speed_percentage(self, percentage: int) -> None:
        """Set speed as a percentage (0-100)."""
        if self.supports_set_speed_percentage:
            if not 0 <= percentage <= 100:
                raise AqualinkInvalidParameterException(percentage)
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException

    async def set_preset(self, _: str) -> None:
        if self.supports_presets:
            raise NotImplementedError
        raise AqualinkOperationNotSupportedException
