"""Contract tests for the AqualinkVacuum base device.

AqualinkVacuum is an abstract base (no system implements it generically), so
its capability-gating logic is exercised here with local stubs rather than the
per-system factory fixtures used by the other conformance modules.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pytest

from iaqualink.device import AqualinkDevice, AqualinkVacuum
from iaqualink.enums import AqualinkRobotActivity
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
)


class _ConcreteDevice(AqualinkDevice):
    @property
    def label(self) -> str:
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


class _ConcreteRobot(_ConcreteDevice, AqualinkVacuum):
    """Robot stub with no capabilities advertised (all supports_* False)."""

    @property
    def activity(self) -> AqualinkRobotActivity:
        return AqualinkRobotActivity.DOCKED


class _CapableRobot(_ConcreteRobot):
    """Advertises every capability but overrides no private hook."""

    @property
    def supports_start(self) -> bool:
        return True

    @property
    def supports_stop(self) -> bool:
        return True

    @property
    def supports_pause(self) -> bool:
        return True

    @property
    def supports_return(self) -> bool:
        return True

    @property
    def supports_clean_spot(self) -> bool:
        return True

    @property
    def supports_locate(self) -> bool:
        return True

    @property
    def fan_speed_list(self) -> list[str]:
        return ["floor", "smart"]


class TestAqualinkRobotActivity(unittest.TestCase):
    def test_mirrors_ha_vacuum_activity(self) -> None:
        assert {a.value for a in AqualinkRobotActivity} == {
            "cleaning",
            "docked",
            "idle",
            "paused",
            "returning",
            "error",
        }


class TestAqualinkVacuum(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.robot = _ConcreteRobot(MagicMock(), {})

    def test_activity(self) -> None:
        assert self.robot.activity is AqualinkRobotActivity.DOCKED

    def test_capabilities_default_false(self) -> None:
        assert self.robot.supports_start is False
        assert self.robot.supports_stop is False
        assert self.robot.supports_pause is False
        assert self.robot.supports_return is False
        assert self.robot.supports_clean_spot is False
        assert self.robot.supports_locate is False
        assert self.robot.supports_fan_speed is False
        assert self.robot.supports_battery is False

    def test_fan_speed_defaults(self) -> None:
        assert self.robot.fan_speed is None
        assert self.robot.fan_speed_list == []

    def test_battery_level_defaults_none(self) -> None:
        assert self.robot.battery_level is None

    async def test_unsupported_commands_raise_not_supported(self) -> None:
        for coro in (
            self.robot.start(),
            self.robot.stop(),
            self.robot.pause(),
            self.robot.return_to_base(),
            self.robot.clean_spot(),
            self.robot.locate(),
            self.robot.set_fan_speed("floor"),
        ):
            with pytest.raises(AqualinkOperationNotSupportedException):
                await coro

    async def test_supported_but_unimplemented_raise_not_implemented(
        self,
    ) -> None:
        robot = _CapableRobot(MagicMock(), {})
        assert robot.supports_fan_speed is True
        for coro in (
            robot.start(),
            robot.stop(),
            robot.pause(),
            robot.return_to_base(),
            robot.clean_spot(),
            robot.locate(),
            robot.set_fan_speed("floor"),
        ):
            with pytest.raises(NotImplementedError):
                await coro

    async def test_set_fan_speed_rejects_value_not_in_list(self) -> None:
        robot = _CapableRobot(MagicMock(), {})
        with pytest.raises(AqualinkInvalidParameterException):
            await robot.set_fan_speed("turbo")
