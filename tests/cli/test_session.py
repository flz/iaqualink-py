from __future__ import annotations

import json
import stat
from pathlib import Path

from typer.testing import CliRunner

import iaqualink.cli.app as cli_module

from .conftest import (
    FakeClient,
    FakeSystem,
    FakeSystemWithAqualink,
    app,
    invoke_with_jar,
    make_switch,
    make_unsupported_system,
    render_plain,
)


def test_capture_flag_creates_file_and_registers_serials(
    tmp_path: Path,
) -> None:
    cookie_jar = tmp_path / "session.json"
    capture_file = tmp_path / "capture.jsonl"
    FakeClient.systems_factory = staticmethod(
        lambda: {"SN001": FakeSystem("SN001", "Pool")}
    )

    result = CliRunner().invoke(
        app,
        [
            "--capture",
            str(capture_file),
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
    assert capture_file.exists()
    session = cli_module._capture_session
    assert session is not None
    assert "SN001" in session._literals
    session.close()


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


def test_format_system_line_unsupported() -> None:
    system = make_unsupported_system()
    line = cli_module._format_system_line(system)
    assert "(unsupported)" in line
    assert "foo" in line


def test_render_device_tree_unsupported_system() -> None:
    system = make_unsupported_system(serial="SN001", name="Pool")
    tree = cli_module._render_device_tree(
        [("SN001", system)],
        {"SN001": {}},
    )
    output = render_plain(tree)
    assert "System type not supported" in output
    assert "No devices found" not in output


def test_list_systems_shows_unsupported_note(tmp_path: Path) -> None:
    cookie_jar = tmp_path / "session.json"
    FakeClient.systems_factory = staticmethod(  # ty: ignore
        lambda: {"SN001": make_unsupported_system()}  # type: ignore[dict-item]
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


def test_render_device_tree_single_system_has_systems_root() -> None:
    system = make_unsupported_system(serial="SN001", name="Pool")
    tree = cli_module._render_device_tree([("SN001", system)], {"SN001": {}})
    output = render_plain(tree)
    assert "Systems" in output
    assert "Pool" in output


def test_render_device_tree_multiple_systems() -> None:
    sys1 = make_unsupported_system(serial="SN001", name="Pool")
    sys2 = make_unsupported_system(serial="SN002", name="Spa")
    tree = cli_module._render_device_tree(
        [("SN001", sys1), ("SN002", sys2)],
        {"SN001": {}, "SN002": {}},
    )
    output = render_plain(tree)
    assert "Pool" in output
    assert "Spa" in output
    assert "Systems" in output


def test_render_device_tree_no_systems() -> None:
    tree = cli_module._render_device_tree([], {})
    output = render_plain(tree)
    assert "No systems found" in output


def test_list_devices_saves_jar_after_device_load(tmp_path: Path) -> None:
    FakeClient.systems_factory = staticmethod(
        lambda: {"SN001": FakeSystemWithAqualink("SN001", "Pool")}
    )
    result, cookie_jar = invoke_with_jar(tmp_path, "list-devices")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


def test_status_saves_jar_after_device_load(tmp_path: Path) -> None:
    FakeClient.systems_factory = staticmethod(
        lambda: {"SN001": FakeSystemWithAqualink("SN001", "Pool")}
    )
    result, cookie_jar = invoke_with_jar(tmp_path, "status")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


# ---------------------------------------------------------------------------
# get command
# ---------------------------------------------------------------------------


def test_get_device_prints_state(tmp_path: Path) -> None:
    switch = make_switch("Filter", is_on=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"filter": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "get", "filter")
    assert result.exit_code == 0
    assert "Filter" in result.output


def test_get_device_saves_jar(tmp_path: Path) -> None:
    switch = make_switch("Filter", is_on=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"filter": switch})
        }
    )
    result, cookie_jar = invoke_with_jar(tmp_path, "get", "filter")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


# ---------------------------------------------------------------------------
# logout command
# ---------------------------------------------------------------------------


def test_logout_removes_existing_jar(tmp_path: Path) -> None:
    cookie_jar = tmp_path / "session.json"
    cookie_jar.write_text("{}")
    result = CliRunner().invoke(
        app, ["logout", "--cookie-jar", str(cookie_jar)]
    )
    assert result.exit_code == 0
    assert not cookie_jar.exists()


def test_logout_missing_jar_prints_message(tmp_path: Path) -> None:
    cookie_jar = tmp_path / "session.json"
    result = CliRunner().invoke(
        app, ["logout", "--cookie-jar", str(cookie_jar)]
    )
    assert result.exit_code == 0
    assert "No session jar found" in result.output
