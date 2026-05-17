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

LOGGER = logging.getLogger("iaqualink.device")


class AqualinkDevice:
    # Properties that form this class's public API surface, used by snapshot
    # tests and documentation. Each subclass declares only its own additions;
    # tests collect the full set by walking the MRO via vars().
    _own_snapshot_props: tuple[str, ...] = (
        "label",
        "state",
        "state_translated",
    )

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

    _own_snapshot_props: tuple[str, ...] = ("is_on",)

    @property
    def is_on(self) -> bool:
        raise NotImplementedError


class AqualinkSwitch(AqualinkBinarySensor, AqualinkDevice):
    async def turn_on(self) -> None:
        raise NotImplementedError

    async def turn_off(self) -> None:
        raise NotImplementedError


class AqualinkLight(AqualinkSwitch, AqualinkDevice):
    _own_snapshot_props: tuple[str, ...] = ("brightness", "effect")

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
    _own_snapshot_props: tuple[str, ...] = (
        "unit",
        "current_temperature",
        "target_temperature",
    )

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
    _own_snapshot_props: tuple[str, ...] = (
        "current_value",
        "min_value",
        "max_value",
        "step",
        "unit",
    )

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
            raise AqualinkInvalidParameterException(
                f"{value} is out of range ({self.min_value}-{self.max_value})."
            )
        if int(value) % int(self.step) != 0:
            raise AqualinkInvalidParameterException(
                f"{int(value)} is not a multiple of {int(self.step)}."
            )
        await self._set_value(value)

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
