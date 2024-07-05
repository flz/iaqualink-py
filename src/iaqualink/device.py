from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iaqualink.exception import AqualinkOperationNotSupportedException

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
        return f'{self.__class__.__name__}({", ".join(attrs)})'

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
