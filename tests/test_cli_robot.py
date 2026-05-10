from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from iaqualink.client import AqualinkAuthState

cli_module = importlib.import_module("iaqualink.cli.app")
app = cli_module.app


class FakeCyclonext:
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
        self.update = AsyncMock()


class _FakeNonCyclonext:
    def __init__(self, serial: str, name: str) -> None:
        self.serial = serial
        self.name = name
        self.data = {"device_type": "iaqua"}

    async def get_devices(self) -> dict[str, object]:
        return {}


class FakeClient:
    systems_factory = staticmethod(dict)

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self._auth_state: AqualinkAuthState | None = None

    @property
    def auth_state(self) -> AqualinkAuthState | None:
        return self._auth_state

    @auth_state.setter
    def auth_state(self, state: AqualinkAuthState | None) -> None:
        self._auth_state = state

    async def __aenter__(self) -> FakeClient:
        if self._auth_state is None:
            await self.login()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool | None:
        return None

    async def login(self) -> None:
        self._auth_state = AqualinkAuthState(
            username=self.username,
            client_id="session-id",
            authentication_token="token",
            user_id="user-id",
            id_token="id-token",
            refresh_token="refresh-token",
        )

    async def get_systems(self):
        return type(self).systems_factory()


@pytest.fixture(autouse=True)
def patch_client_and_isinstance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module, "AqualinkClient", FakeClient)
    # Treat FakeCyclonext as one of the recognised robot system types.
    monkeypatch.setattr(cli_module, "CyclonextSystem", FakeCyclonext)
    monkeypatch.setattr(
        cli_module,
        "_ROBOT_SYSTEM_TYPES",
        (FakeCyclonext, *cli_module._ROBOT_SYSTEM_TYPES[1:]),
    )


def _invoke(*args: str, cookie_jar: Path) -> object:
    return CliRunner().invoke(
        app,
        [
            *args,
            "--username",
            "user@example.com",
            "--password",
            "secret",
            "--cookie-jar",
            str(cookie_jar),
        ],
    )


def test_robot_start_invokes_start_cleaning(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "start", cookie_jar=tmp_path / "j.json")

    assert result.exit_code == 0, result.stderr
    robot.start_cleaning.assert_awaited_once_with(cycle=None)
    assert "Started cleaning on splish (KL-1)" in result.stdout


def test_robot_start_with_cycle_floor_wall(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke(
        "robot",
        "start",
        "--cycle",
        "floor-wall",
        cookie_jar=tmp_path / "j.json",
    )

    assert result.exit_code == 0, result.stderr
    robot.start_cleaning.assert_awaited_once_with(cycle=3)
    assert "floor_and_walls" in result.stdout


def test_robot_start_invalid_cycle_exits(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke(
        "robot",
        "start",
        "--cycle",
        "deep",
        cookie_jar=tmp_path / "j.json",
    )

    assert result.exit_code == 1
    assert "Unknown cycle 'deep'" in result.stderr


def test_robot_stop_invokes_stop_cleaning(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "stop", cookie_jar=tmp_path / "j.json")

    assert result.exit_code == 0
    robot.stop_cleaning.assert_awaited_once()


def test_robot_pause_invokes_pause_cleaning(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "pause", cookie_jar=tmp_path / "j.json")

    assert result.exit_code == 0
    robot.pause_cleaning.assert_awaited_once()


def test_robot_set_cycle_floor(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke(
        "robot", "set-cycle", "floor", cookie_jar=tmp_path / "j.json"
    )

    assert result.exit_code == 0, result.stderr
    robot.set_cycle.assert_awaited_once_with(1)
    assert "Set cycle to floor" in result.stdout


def test_robot_status_renders_summary(tmp_path: Path) -> None:
    class _Dev:
        def __init__(self, state: str | int) -> None:
            self.state = str(state)

    robot = FakeCyclonext("KL-1", "splish")
    robot.devices = {
        "mode": _Dev(1),
        "cycle": _Dev(1),
        "time_remaining_sec": _Dev(120),
        "totRunTime": _Dev(15041),
    }
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "status", cookie_jar=tmp_path / "j.json")

    assert result.exit_code == 0, result.stderr
    out = result.stdout
    assert "splish (KL-1)" in out
    assert "mode      : running (1)" in out
    assert "cycle     : floor (1)" in out
    assert "remaining : 02:00" in out
    assert "total run : 250h 41m" in out


def test_robot_extend_calls_set_runtime_extension(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "extend", "30", cookie_jar=tmp_path / "j.json")

    assert result.exit_code == 0, result.stderr
    robot.set_runtime_extension.assert_awaited_once_with(30)
    assert "Set runtime extension to 30 min" in result.stdout


def test_robot_extend_invalid_value_exits(tmp_path: Path) -> None:
    from iaqualink.exception import AqualinkInvalidParameterException

    robot = FakeCyclonext("KL-1", "splish")
    robot.set_runtime_extension = AsyncMock(
        side_effect=AqualinkInvalidParameterException("bad")
    )
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "extend", "7", cookie_jar=tmp_path / "j.json")

    assert result.exit_code == 1
    assert "bad" in result.stderr


def test_robot_adjust_time_positive_delta(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke(
        "robot", "adjust-time", "+15", cookie_jar=tmp_path / "j.json"
    )

    assert result.exit_code == 0, result.stderr
    robot.update.assert_awaited_once()
    robot.adjust_runtime.assert_awaited_once_with(15)
    assert "Adjusted runtime extension by +15" in result.stdout


def test_robot_adjust_time_negative_delta(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke(
        "robot", "adjust-time", "-15", cookie_jar=tmp_path / "j.json"
    )

    assert result.exit_code == 0, result.stderr
    robot.adjust_runtime.assert_awaited_once_with(-15)
    assert "Adjusted runtime extension by -15" in result.stdout


def test_robot_remote_forward(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke(
        "robot", "remote", "forward", cookie_jar=tmp_path / "j.json"
    )
    assert result.exit_code == 0, result.stderr
    robot.remote_forward.assert_awaited_once()
    assert "Sent remote forward" in result.stdout


def test_robot_remote_unknown_action_exits(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke(
        "robot", "remote", "diagonal", cookie_jar=tmp_path / "j.json"
    )
    assert result.exit_code == 1
    assert "Unknown remote action" in result.stderr


def test_robot_lift_eject(tmp_path: Path) -> None:
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "lift", "eject", cookie_jar=tmp_path / "j.json")
    assert result.exit_code == 0, result.stderr
    robot.lift_eject.assert_awaited_once()
    assert "Sent lift eject" in result.stdout


def test_robot_exit_remote_command_removed(tmp_path: Path) -> None:
    """`exit-remote` was unified into `stop` (T26). Make sure it's gone."""
    robot = FakeCyclonext("KL-1", "splish")
    FakeClient.systems_factory = staticmethod(lambda: {"KL-1": robot})

    result = _invoke("robot", "exit-remote", cookie_jar=tmp_path / "j.json")
    assert result.exit_code != 0


def test_robot_command_rejects_non_cyclonext(tmp_path: Path) -> None:
    FakeClient.systems_factory = staticmethod(
        lambda: {"serial-x": _FakeNonCyclonext("serial-x", "pool")}
    )

    result = _invoke("robot", "stop", cookie_jar=tmp_path / "j.json")

    assert result.exit_code == 1
    assert "is not a supported robot" in result.stderr
