from __future__ import annotations

import json
from pathlib import Path

import iaqualink.cli.app as cli_module
from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    invoke_with_jar,
    make_number,
    make_switch,
)

# ---------------------------------------------------------------------------
# _format_device_line
# ---------------------------------------------------------------------------


def test_format_device_line_number_with_unit() -> None:
    device = make_number("Filter RPM", 1500.0, unit="RPM")
    text = cli_module._format_device_line("rpm", device)
    assert "Filter RPM" in text.plain
    assert "1500" in text.plain
    assert "RPM" in text.plain


def test_format_device_line_number_without_unit() -> None:
    device = make_number("Pump Speed", 75.0, unit=None)
    text = cli_module._format_device_line("speed", device)
    assert "Pump Speed" in text.plain
    assert "75" in text.plain


def test_format_device_line_number_none_value_shows_dim() -> None:
    device = make_number("Pump Speed", None)
    text = cli_module._format_device_line("speed", device)
    assert "Pump Speed" in text.plain
    assert ": " not in text.plain


# ---------------------------------------------------------------------------
# set-value
# ---------------------------------------------------------------------------


def test_set_value_number_device(tmp_path: Path) -> None:
    number = make_number("RPM", 1500.0, max_value=3450.0, unit="RPM")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"rpm": number})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-value", "rpm", "2000")
    assert result.exit_code == 0
    assert "2000 RPM" in result.output


def test_set_value_number_device_without_unit(tmp_path: Path) -> None:
    number = make_number("Level", 5.0, max_value=10.0, unit=None)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"level": number})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-value", "level", "7")
    assert result.exit_code == 0
    assert "7" in result.output


def test_set_value_non_number_exits(tmp_path: Path) -> None:
    switch = make_switch("Filter", is_on=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"filter": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-value", "filter", "50")
    assert result.exit_code == 1
    assert "does not support numeric values" in result.stderr


def test_set_value_out_of_range_exits(tmp_path: Path) -> None:
    number = make_number("RPM", 1500.0, max_value=3450.0, unit="RPM")
    number.set_value.side_effect = AqualinkInvalidParameterException(  # type: ignore[attr-defined, unresolved-attribute]  # ty: ignore
        "9999.0 is out of range (0.0-3450.0)."
    )
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"rpm": number})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-value", "rpm", "9999")
    assert result.exit_code == 1
    assert "out of range" in result.stderr


def test_set_value_saves_jar(tmp_path: Path) -> None:
    number = make_number("RPM", 1500.0, max_value=3450.0, unit="RPM")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"rpm": number})
        }
    )
    result, cookie_jar = invoke_with_jar(tmp_path, "set-value", "rpm", "2000")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"
