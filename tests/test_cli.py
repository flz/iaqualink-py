from __future__ import annotations

import importlib
import json
import stat
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from iaqualink.client import AqualinkAuthState
from iaqualink.system import UnsupportedSystem

cli_module = importlib.import_module("iaqualink.cli.app")

app = cli_module.app


class FakeSystem:
    supported = True

    def __init__(self, serial: str, name: str) -> None:
        self.serial = serial
        self.name = name
        self.data = {"device_type": "iaqua"}

    async def get_devices(self) -> dict[str, object]:
        return {}


class FakeClient:
    systems_factory = staticmethod(dict[str, FakeSystem])
    login_call_count = 0

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
        type(self).login_call_count += 1
        self._auth_state = AqualinkAuthState(
            username=self.username,
            client_id="session-id",
            authentication_token="token",
            user_id="user-id",
            id_token="id-token",
            refresh_token="refresh-token",
        )

    async def get_systems(self) -> dict[str, FakeSystem]:
        return type(self).systems_factory()


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.login_call_count = 0
    FakeClient.systems_factory = staticmethod(dict[str, FakeSystem])
    monkeypatch.setattr(cli_module, "AqualinkClient", FakeClient)


def test_list_systems_ignores_malformed_session_jar(tmp_path: Path) -> None:
    cookie_jar = tmp_path / "session.json"
    cookie_jar.write_text(json.dumps({"username": "user@example.com"}))

    FakeClient.systems_factory = staticmethod(
        lambda: {"serial-1": FakeSystem("serial-1", "Backyard")}
    )

    result = CliRunner().invoke(
        app,
        [
            "list-systems",
            "--username",
            "user@example.com",
            "--password",
            "secret",
            "--cookie-jar",
            str(cookie_jar),
        ],
    )

    assert result.exit_code == 0
    assert "Backyard (serial-1) [iaqua]" in result.stdout
    assert FakeClient.login_call_count == 1


def test_list_systems_writes_owner_only_cookie_jar(tmp_path: Path) -> None:
    cookie_jar = tmp_path / "session.json"
    FakeClient.systems_factory = staticmethod(
        lambda: {"serial-1": FakeSystem("serial-1", "Backyard")}
    )

    result = CliRunner().invoke(
        app,
        [
            "list-systems",
            "--username",
            "user@example.com",
            "--password",
            "secret",
            "--cookie-jar",
            str(cookie_jar),
        ],
    )

    assert result.exit_code == 0
    assert stat.S_IMODE(cookie_jar.stat().st_mode) == 0o600


def test_list_devices_reports_ambiguous_system_name(tmp_path: Path) -> None:
    cookie_jar = tmp_path / "session.json"
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "serial-1": FakeSystem("serial-1", "Backyard"),
            "serial-2": FakeSystem("serial-2", "Backyard"),
        }
    )

    result = CliRunner().invoke(
        app,
        [
            "list-devices",
            "--username",
            "user@example.com",
            "--password",
            "secret",
            "--system",
            "Backyard",
            "--cookie-jar",
            str(cookie_jar),
        ],
    )

    assert result.exit_code == 1
    assert (
        "System name 'Backyard' matches multiple systems. "
        "Use --system with the serial number instead."
    ) in result.stderr


def _make_unsupported_system(
    serial: str = "SN001", name: str = "Pool"
) -> UnsupportedSystem:
    data = {"serial_number": serial, "name": name, "device_type": "foo"}
    return UnsupportedSystem(MagicMock(), data)


def test_format_system_line_unsupported() -> None:
    system = _make_unsupported_system()
    line = cli_module._format_system_line(system)
    assert "(unsupported)" in line
    assert "foo" in line


def test_render_device_tree_unsupported_system() -> None:
    system = _make_unsupported_system(serial="SN001", name="Pool")
    output = cli_module._render_device_tree(
        [("SN001", system)],
        {"SN001": {}},
    )
    assert "System type not supported" in output
    assert "No devices found" not in output


def test_list_systems_shows_unsupported_note(tmp_path: Path) -> None:
    cookie_jar = tmp_path / "session.json"
    FakeClient.systems_factory = staticmethod(
        lambda: {"SN001": _make_unsupported_system()}
    )

    result = CliRunner().invoke(
        app,
        [
            "list-systems",
            "--username",
            "user@example.com",
            "--password",
            "secret",
            "--cookie-jar",
            str(cookie_jar),
        ],
    )

    assert result.exit_code == 0
    assert "(unsupported)" in result.output
