from __future__ import annotations

import json
from pathlib import Path

import iaqualink.cli.app as cli_module
from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    invoke_with_jar,
    make_select,
    make_switch,
)

# ---------------------------------------------------------------------------
# _format_device_line
# ---------------------------------------------------------------------------


def test_format_device_line_select_with_option() -> None:
    device = make_select("Heat Pump Mode", "chill")
    text = cli_module._format_device_line("heatpump_mode", device)
    assert "Heat Pump Mode" in text.plain
    assert "chill" in text.plain


def test_format_device_line_select_none_option_shows_dim() -> None:
    device = make_select("Heat Pump Mode", None)
    text = cli_module._format_device_line("heatpump_mode", device)
    assert "Heat Pump Mode" in text.plain
    assert ": " not in text.plain


# ---------------------------------------------------------------------------
# select-option
# ---------------------------------------------------------------------------


def test_select_option_device(tmp_path: Path) -> None:
    mode = make_select("Heat Pump Mode", "heat")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink(
                "SN001", "Pool", {"heatpump_mode": mode}
            )
        }
    )
    result, _ = invoke_with_jar(
        tmp_path, "select-option", "heatpump_mode", "chill"
    )
    assert result.exit_code == 0
    assert "chill" in result.output


def test_select_option_non_select_exits(tmp_path: Path) -> None:
    switch = make_switch("Filter", is_on=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"filter": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "select-option", "filter", "chill")
    assert result.exit_code == 1
    assert "does not support selecting options" in result.stderr


def test_select_option_invalid_option_exits(tmp_path: Path) -> None:
    mode = make_select("Heat Pump Mode", "heat")
    mode.select_option.side_effect = AqualinkInvalidParameterException(  # type: ignore[attr-defined, unresolved-attribute]  # ty: ignore
        "'auto' isn't a valid option (heat, chill)."
    )
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink(
                "SN001", "Pool", {"heatpump_mode": mode}
            )
        }
    )
    result, _ = invoke_with_jar(
        tmp_path, "select-option", "heatpump_mode", "auto"
    )
    assert result.exit_code == 1
    assert "isn't a valid option" in result.stderr


def test_select_option_saves_jar(tmp_path: Path) -> None:
    mode = make_select("Heat Pump Mode", "heat")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink(
                "SN001", "Pool", {"heatpump_mode": mode}
            )
        }
    )
    result, cookie_jar = invoke_with_jar(
        tmp_path, "select-option", "heatpump_mode", "chill"
    )
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"
