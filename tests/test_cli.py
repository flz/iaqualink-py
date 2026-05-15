from __future__ import annotations

import importlib
import json
import stat
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console as RichConsole
from typer.testing import CliRunner

from iaqualink.client import AqualinkAuthState
from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkLight,
    AqualinkNumber,
    AqualinkPump,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)
from iaqualink.system import SystemStatus, UnsupportedSystem

cli_module = importlib.import_module("iaqualink.cli.app")

app = cli_module.app


class FakeSystem:
    supported = True
    status = SystemStatus.UNKNOWN

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
    assert "Backyard" in result.stdout
    assert "serial-1" in result.stdout
    assert "iaqua" in result.stdout
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
    assert "matches multiple systems." in result.stderr
    assert "Use --system with the serial number instead." in result.stderr


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
    tree = cli_module._render_device_tree(
        [("SN001", system)],
        {"SN001": {}},
    )
    buf = StringIO()
    RichConsole(file=buf, no_color=True, width=120).print(tree)
    output = buf.getvalue()
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


# ---------------------------------------------------------------------------
# Helpers for unit tests below
# ---------------------------------------------------------------------------


def _make_device(
    cls: type,
    label: str = "Dev",
    state: str | None = "1",
) -> AqualinkDevice:
    """Minimal concrete device of a given base class (bypasses __init__)."""

    class _Impl(cls):  # type: ignore[valid-type]
        @property
        def label(self) -> str:
            return label

        @property
        def state(self) -> str | None:
            return state

        @property
        def name(self) -> str:
            return label

        @property
        def manufacturer(self) -> str:
            return ""

        @property
        def model(self) -> str:
            return ""

        @property
        def is_on(self) -> bool:
            return bool(state)

        async def turn_on(self) -> None:
            pass

        async def turn_off(self) -> None:
            pass

        @property
        def unit(self) -> str:
            return "F"

        @property
        def current_temperature(self) -> str:
            return ""

        @property
        def target_temperature(self) -> str:
            return ""

        @property
        def max_temperature(self) -> int:
            return 104

        @property
        def min_temperature(self) -> int:
            return 40

        async def set_temperature(self, _: int) -> None:
            pass

        @property
        def brightness(self) -> int | None:
            return None

        async def set_brightness(self, _: int) -> None:
            pass

    return object.__new__(_Impl)


def _render_plain(renderable: object) -> str:
    buf = StringIO()
    RichConsole(file=buf, no_color=True, width=120).print(renderable)
    return buf.getvalue()


# Auth state returned by FakeSystemWithAqualink.aqualink — distinct from the
# state FakeClient writes during _fetch_systems so tests can tell them apart.
_POST_DEVICE_AUTH = AqualinkAuthState(
    username="user@example.com",
    client_id="post-device-session",
    authentication_token="post-device-token",
    user_id="user-id",
    id_token="post-device-id-token",
    refresh_token="post-device-refresh-token",
)


class FakeSystemWithAqualink(FakeSystem):
    """FakeSystem that exposes an aqualink client with a known auth state
    and can return configurable devices from get_devices()."""

    def __init__(
        self,
        serial: str,
        name: str,
        devices: dict | None = None,
    ) -> None:
        super().__init__(serial, name)
        self._devices = devices or {}

    @property
    def aqualink(self) -> MagicMock:
        m = MagicMock()
        m.auth_state = _POST_DEVICE_AUTH
        return m

    async def get_devices(self) -> dict:
        return self._devices


# ---------------------------------------------------------------------------
# _group_devices
# ---------------------------------------------------------------------------


def test_group_devices_all_types() -> None:
    devices = [
        ("t1", _make_device(AqualinkThermostat, "Heater")),
        ("l1", _make_device(AqualinkLight, "Light")),
        ("s1", _make_device(AqualinkSwitch, "Switch")),
        ("p1", _make_device(AqualinkPump, "Pump")),
        ("nb1", _make_device(AqualinkNumber, "RPM")),
        ("n1", _make_device(AqualinkSensor, "Temp")),
    ]
    groups = cli_module._group_devices(devices)
    assert [label for _, label, _ in groups] == [
        "Thermostats",
        "Lights",
        "Switches",
        "Pumps",
        "Numbers",
        "Sensors",
    ]
    for _, _, members in groups:
        assert len(members) == 1


def test_group_devices_thermostat_not_swallowed_by_switch() -> None:
    thermostat = _make_device(AqualinkThermostat, "Heater")
    groups = cli_module._group_devices([("h", thermostat)])
    assert len(groups) == 1
    assert groups[0][1] == "Thermostats"


def test_group_devices_light_not_swallowed_by_switch() -> None:
    light = _make_device(AqualinkLight, "Spa Light")
    groups = cli_module._group_devices([("l", light)])
    assert len(groups) == 1
    assert groups[0][1] == "Lights"


def test_group_devices_pump_grouped_as_pump() -> None:
    pump = _make_device(AqualinkPump, "Filter Pump")
    groups = cli_module._group_devices([("p", pump)])
    assert len(groups) == 1
    assert groups[0][1] == "Pumps"


def test_group_devices_number_grouped_as_number() -> None:
    number = _make_device(AqualinkNumber, "RPM")
    groups = cli_module._group_devices([("nb", number)])
    assert len(groups) == 1
    assert groups[0][1] == "Numbers"


def test_group_devices_binary_sensor_covered_by_sensor_group() -> None:
    # AqualinkBinarySensor extends AqualinkSensor; no separate _DEVICE_GROUPS
    # entry is needed — it is matched by the AqualinkSensor entry.
    binary = _make_device(AqualinkBinarySensor, "Freeze")
    groups = cli_module._group_devices([("b", binary)])
    assert len(groups) == 1
    assert groups[0][1] == "Sensors"


# AqualinkPump and AqualinkNumber extend AqualinkDevice directly and share no
# IS-A relationship with AqualinkSensor or AqualinkSwitch, so there is no risk
# of them being swallowed by another group. No "not swallowed" tests are needed
# for those types (unlike AqualinkThermostat/AqualinkLight which extend
# AqualinkSwitch and do require such guards).


def test_group_devices_unknown_type_goes_to_other() -> None:
    class _Unknown(AqualinkDevice):
        @property
        def label(self) -> str:
            return "X"

        @property
        def state(self) -> str:
            return "x"

        @property
        def name(self) -> str:
            return "X"

        @property
        def manufacturer(self) -> str:
            return ""

        @property
        def model(self) -> str:
            return ""

    device = object.__new__(_Unknown)
    groups = cli_module._group_devices([("x", device)])
    assert len(groups) == 1
    assert groups[0][1] == "Other"


def test_group_devices_empty() -> None:
    assert cli_module._group_devices([]) == []


# ---------------------------------------------------------------------------
# _format_device_line
# ---------------------------------------------------------------------------


def test_format_device_line_with_state() -> None:
    device = _make_device(AqualinkSwitch, "Pool Pump", "1")
    text = cli_module._format_device_line("pump", device)
    assert "Pool Pump" in text.plain
    assert "[pump]" in text.plain
    assert "1" in text.plain
    assert ": " in text.plain


def test_format_device_line_none_state() -> None:
    device = _make_device(AqualinkSwitch, "Pool Pump", None)
    text = cli_module._format_device_line("pump", device)
    assert "Pool Pump" in text.plain
    assert "[pump]" in text.plain
    assert ": " not in text.plain


def test_format_device_line_empty_state() -> None:
    device = _make_device(AqualinkSwitch, "Pool Pump", "")
    text = cli_module._format_device_line("pump", device)
    assert "Pool Pump" in text.plain
    assert ": " not in text.plain


# ---------------------------------------------------------------------------
# _render_device_tree — multi-system path
# ---------------------------------------------------------------------------


def test_render_device_tree_single_system_has_systems_root() -> None:
    system = _make_unsupported_system(serial="SN001", name="Pool")
    tree = cli_module._render_device_tree([("SN001", system)], {"SN001": {}})
    output = _render_plain(tree)
    assert "Systems" in output
    assert "Pool" in output


def test_render_device_tree_multiple_systems() -> None:
    sys1 = _make_unsupported_system(serial="SN001", name="Pool")
    sys2 = _make_unsupported_system(serial="SN002", name="Spa")
    tree = cli_module._render_device_tree(
        [("SN001", sys1), ("SN002", sys2)],
        {"SN001": {}, "SN002": {}},
    )
    output = _render_plain(tree)
    assert "Pool" in output
    assert "Spa" in output
    assert "Systems" in output


def test_render_device_tree_no_systems() -> None:
    tree = cli_module._render_device_tree([], {})
    output = _render_plain(tree)
    assert "No systems found" in output


# ---------------------------------------------------------------------------
# Session jar saved after device / control operations
# ---------------------------------------------------------------------------


def _invoke_with_jar(tmp_path: Path, *args: str) -> tuple:
    cookie_jar = tmp_path / "session.json"
    result = CliRunner().invoke(
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
    return result, cookie_jar


def test_list_devices_saves_jar_after_device_load(tmp_path: Path) -> None:
    FakeClient.systems_factory = staticmethod(
        lambda: {"SN001": FakeSystemWithAqualink("SN001", "Pool")}
    )
    result, cookie_jar = _invoke_with_jar(tmp_path, "list-devices")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


def test_status_saves_jar_after_device_load(tmp_path: Path) -> None:
    FakeClient.systems_factory = staticmethod(
        lambda: {"SN001": FakeSystemWithAqualink("SN001", "Pool")}
    )
    result, cookie_jar = _invoke_with_jar(tmp_path, "status")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


def test_turn_on_saves_jar_after_command(tmp_path: Path) -> None:
    switch = _make_device(AqualinkSwitch, "Pump", "0")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"pump": switch})
        }
    )
    result, cookie_jar = _invoke_with_jar(tmp_path, "turn-on", "pump")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


def test_set_temperature_saves_jar_after_command(tmp_path: Path) -> None:
    thermostat = _make_device(AqualinkThermostat, "Heater", "72")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink(
                "SN001", "Pool", {"heater": thermostat}
            )
        }
    )
    result, cookie_jar = _invoke_with_jar(
        tmp_path, "set-temperature", "heater", "78"
    )
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"
