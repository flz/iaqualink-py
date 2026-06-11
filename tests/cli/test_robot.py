"""Tests for `iaqualink robot` subcommand group."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import iaqualink.cli.app as cli_module
from iaqualink.system import SystemStatus

from .conftest import FakeClient, invoke_with_jar

# ---------------------------------------------------------------------------
# Fake robot system
# ---------------------------------------------------------------------------


class FakeCyclonext:
    supported = True

    def __init__(self, serial: str, name: str) -> None:
        self.serial = serial
        self.name = name
        self.data = {"device_type": "cyclonext"}
        self.devices: dict[str, object] = {}
        self.start_cleaning = AsyncMock()
        self.stop_cleaning = AsyncMock()
        self.pause_cleaning = AsyncMock()
        self.set_cycle = AsyncMock()
        self.set_runtime_extension = AsyncMock()
        self.adjust_runtime = AsyncMock(return_value=30)
        self.remote_forward = AsyncMock()
        self.remote_backward = AsyncMock()
        self.remote_rotate_left = AsyncMock()
        self.remote_rotate_right = AsyncMock()
        self.remote_stop = AsyncMock()
        self.lift_eject = AsyncMock()
        self.lift_rotate_left = AsyncMock()
        self.lift_rotate_right = AsyncMock()
        self.lift_stop = AsyncMock()
        self.refresh = AsyncMock()
        self._status = SystemStatus.ONLINE

    @property
    def status(self) -> SystemStatus:
        return self._status

    @status.setter
    def status(self, value: SystemStatus) -> None:
        self._status = value


class _FakeNonCyclonext:
    supported = True

    def __init__(self, serial: str, name: str) -> None:
        self.serial = serial
        self.name = name
        self.data = {"device_type": "iaqua"}

    async def get_devices(self) -> dict[str, object]:
        return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_robot_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat FakeCyclonext as a recognised robot system type."""
    monkeypatch.setattr(cli_module, "CyclonextSystem", FakeCyclonext)
    monkeypatch.setattr(
        cli_module,
        "_ROBOT_SYSTEM_TYPES",
        (FakeCyclonext, *cli_module._ROBOT_SYSTEM_TYPES[1:]),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Dev:
    """Minimal device stub with .value attribute."""

    def __init__(self, value: str | int) -> None:
        self.value = str(value)


def _robot(serial: str = "KL-1", name: str = "splish") -> FakeCyclonext:
    return FakeCyclonext(serial, name)


def _set_system(robot: FakeCyclonext | _FakeNonCyclonext) -> None:
    FakeClient.systems_factory = staticmethod(  # ty: ignore[invalid-assignment]
        lambda: {robot.serial: robot}  # type: ignore[dict-item]
    )


# ---------------------------------------------------------------------------
# robot start
# ---------------------------------------------------------------------------


def test_robot_start_invokes_start_cleaning(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "start")

    assert result.exit_code == 0, result.output
    robot.start_cleaning.assert_awaited_once_with(cycle=None)
    assert "Started cleaning on splish (KL-1)" in result.output


def test_robot_start_with_cycle_floor_wall(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(
        tmp_path, "robot", "start", "--cycle", "floor-wall"
    )

    assert result.exit_code == 0, result.output
    robot.start_cleaning.assert_awaited_once_with(cycle=3)
    assert "floor_and_walls" in result.output


def test_robot_start_with_cycle_floor(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "start", "--cycle", "floor")

    assert result.exit_code == 0, result.output
    robot.start_cleaning.assert_awaited_once_with(cycle=1)


def test_robot_start_invalid_cycle_exits(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "start", "--cycle", "deep")

    assert result.exit_code == 1
    assert "Unknown cycle" in result.output
    assert "deep" in result.output


# ---------------------------------------------------------------------------
# robot stop
# ---------------------------------------------------------------------------


def test_robot_stop_invokes_stop_cleaning(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "stop")

    assert result.exit_code == 0, result.output
    robot.stop_cleaning.assert_awaited_once()


# ---------------------------------------------------------------------------
# robot pause
# ---------------------------------------------------------------------------


def test_robot_pause_invokes_pause_cleaning(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "pause")

    assert result.exit_code == 0, result.output
    robot.pause_cleaning.assert_awaited_once()


# ---------------------------------------------------------------------------
# robot status
# ---------------------------------------------------------------------------


def test_robot_status_renders_summary(tmp_path: Path) -> None:
    robot = _robot()
    robot.devices = {
        "mode": _Dev(1),
        "cycle": _Dev(1),
        "time_remaining_sec": _Dev(120),
        "totRunTime": _Dev(15041),
    }
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "status")

    assert result.exit_code == 0, result.output
    out = result.output
    assert "splish (KL-1)" in out
    assert "ONLINE" in out
    assert "mode      : running (1)" in out
    assert "cycle     : floor (1)" in out
    assert "remaining : 02:00" in out
    assert "total run : 250h 41m" in out


def test_robot_status_no_devices_shows_unknowns(tmp_path: Path) -> None:
    robot = _robot()
    robot.devices = {}
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "status")

    assert result.exit_code == 0, result.output
    out = result.output
    assert "mode      : ? (?)" in out
    assert "cycle     : ? (?)" in out
    assert "remaining : n/a" in out


def test_robot_status_non_robot_system_exits(tmp_path: Path) -> None:
    non_robot = _FakeNonCyclonext("serial-x", "pool")
    _set_system(non_robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "status")

    assert result.exit_code == 1
    assert "is not a supported robot" in result.output


# ---------------------------------------------------------------------------
# robot extend
# ---------------------------------------------------------------------------


def test_robot_extend_calls_set_runtime_extension(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "extend", "30")

    assert result.exit_code == 0, result.output
    robot.set_runtime_extension.assert_awaited_once_with(30)
    assert "Set runtime extension to 30 min" in result.output


def test_robot_extend_invalid_value_exits(tmp_path: Path) -> None:
    from iaqualink.exception import AqualinkInvalidParameterException

    robot = _robot()
    robot.set_runtime_extension = AsyncMock(
        side_effect=AqualinkInvalidParameterException("bad")
    )
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "extend", "7")

    assert result.exit_code == 1
    assert "bad" in result.output


# ---------------------------------------------------------------------------
# robot adjust-time
# ---------------------------------------------------------------------------


def test_robot_adjust_time_positive_delta(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "adjust-time", "+15")

    assert result.exit_code == 0, result.output
    robot.refresh.assert_awaited_once()
    robot.adjust_runtime.assert_awaited_once_with(15)
    assert "Adjusted runtime extension by +15" in result.output


def test_robot_adjust_time_negative_delta(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "adjust-time", "-15")

    assert result.exit_code == 0, result.output
    robot.adjust_runtime.assert_awaited_once_with(-15)
    assert "Adjusted runtime extension by -15" in result.output


def test_robot_adjust_time_invalid_delta_exits(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "adjust-time", "abc")

    assert result.exit_code == 1
    assert "Invalid delta" in result.output


# ---------------------------------------------------------------------------
# robot set-cycle
# ---------------------------------------------------------------------------


def test_robot_set_cycle_floor(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "set-cycle", "floor")

    assert result.exit_code == 0, result.output
    robot.set_cycle.assert_awaited_once_with(1)
    assert "Set cycle to floor" in result.output


def test_robot_set_cycle_floor_wall(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "set-cycle", "floor-wall")

    assert result.exit_code == 0, result.output
    robot.set_cycle.assert_awaited_once_with(3)
    assert "floor_and_walls" in result.output


def test_robot_set_cycle_invalid_exits(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "set-cycle", "deep")

    assert result.exit_code == 1
    assert "Unknown cycle" in result.output


# ---------------------------------------------------------------------------
# robot remote
# ---------------------------------------------------------------------------


def test_robot_remote_forward(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "remote", "forward")

    assert result.exit_code == 0, result.output
    robot.remote_forward.assert_awaited_once()
    assert "Sent remote forward" in result.output


def test_robot_remote_backward(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "remote", "backward")

    assert result.exit_code == 0, result.output
    robot.remote_backward.assert_awaited_once()


def test_robot_remote_left(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "remote", "left")

    assert result.exit_code == 0, result.output
    robot.remote_rotate_left.assert_awaited_once()


def test_robot_remote_right(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "remote", "right")

    assert result.exit_code == 0, result.output
    robot.remote_rotate_right.assert_awaited_once()


def test_robot_remote_stop(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "remote", "stop")

    assert result.exit_code == 0, result.output
    robot.remote_stop.assert_awaited_once()


def test_robot_remote_unknown_action_exits(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "remote", "diagonal")

    assert result.exit_code == 1
    assert "Unknown remote action" in result.output


# ---------------------------------------------------------------------------
# robot lift
# ---------------------------------------------------------------------------


def test_robot_lift_eject(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "lift", "eject")

    assert result.exit_code == 0, result.output
    robot.lift_eject.assert_awaited_once()
    assert "Sent lift eject" in result.output


def test_robot_lift_left(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "lift", "left")

    assert result.exit_code == 0, result.output
    robot.lift_rotate_left.assert_awaited_once()


def test_robot_lift_right(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "lift", "right")

    assert result.exit_code == 0, result.output
    robot.lift_rotate_right.assert_awaited_once()


def test_robot_lift_stop(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "lift", "stop")

    assert result.exit_code == 0, result.output
    robot.lift_stop.assert_awaited_once()


def test_robot_lift_unknown_action_exits(tmp_path: Path) -> None:
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "lift", "spin")

    assert result.exit_code == 1
    assert "Unknown lift action" in result.output


# ---------------------------------------------------------------------------
# Non-robot system error path
# ---------------------------------------------------------------------------


def test_robot_command_rejects_non_robot_system(tmp_path: Path) -> None:
    non_robot = _FakeNonCyclonext("serial-x", "pool")
    _set_system(non_robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "stop")

    assert result.exit_code == 1
    assert "is not a supported robot" in result.output


def test_robot_exit_remote_command_removed(tmp_path: Path) -> None:
    """`exit-remote` was unified into `stop` (T26). Verify it's gone."""
    robot = _robot()
    _set_system(robot)

    result, _ = invoke_with_jar(tmp_path, "robot", "exit-remote")

    assert result.exit_code != 0
