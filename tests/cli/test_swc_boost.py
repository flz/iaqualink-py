from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import FakeClient, FakeSystemWithAqualink, invoke_with_jar


class _SwcSystem(FakeSystemWithAqualink):
    def __init__(self, serial: str, name: str) -> None:
        super().__init__(serial, name)
        self.control_swc_boost = AsyncMock()


def test_swc_boost_start_calls_system(tmp_path: Path) -> None:
    system = _SwcSystem("SN001", "Pool")
    FakeClient.systems_factory = staticmethod(lambda: {"SN001": system})
    result, _ = invoke_with_jar(
        tmp_path, "swc-boost", "start", "--hours", "4", "--mode", "pool"
    )
    assert result.exit_code == 0
    system.control_swc_boost.assert_awaited_once_with(
        "start", boosthrs=4, boostmode="pool"
    )
    assert "Pool" in result.output


def test_swc_boost_stop_without_hours_or_mode(tmp_path: Path) -> None:
    system = _SwcSystem("SN001", "Pool")
    FakeClient.systems_factory = staticmethod(lambda: {"SN001": system})
    result, _ = invoke_with_jar(tmp_path, "swc-boost", "stop")
    assert result.exit_code == 0
    system.control_swc_boost.assert_awaited_once_with(
        "stop", boosthrs=None, boostmode=None
    )


def test_swc_boost_propagates_validation_error(tmp_path: Path) -> None:
    system = _SwcSystem("SN001", "Pool")
    system.control_swc_boost.side_effect = AqualinkInvalidParameterException(
        "Starting a boost requires both boosthrs and boostmode."
    )
    FakeClient.systems_factory = staticmethod(lambda: {"SN001": system})
    result, _ = invoke_with_jar(tmp_path, "swc-boost", "start")
    assert result.exit_code == 1
    assert "requires both boosthrs and boostmode" in result.stderr


def test_swc_boost_unsupported_system_exits(tmp_path: Path) -> None:
    system = FakeSystemWithAqualink("SN001", "Pool")
    FakeClient.systems_factory = staticmethod(lambda: {"SN001": system})
    result, _ = invoke_with_jar(tmp_path, "swc-boost", "start")
    assert result.exit_code == 1
    assert "does not support SWC boost control" in result.stderr


def test_swc_boost_saves_jar(tmp_path: Path) -> None:
    system = _SwcSystem("SN001", "Pool")
    FakeClient.systems_factory = staticmethod(lambda: {"SN001": system})
    result, cookie_jar = invoke_with_jar(tmp_path, "swc-boost", "stop")
    assert result.exit_code == 0
    assert cookie_jar.exists()
