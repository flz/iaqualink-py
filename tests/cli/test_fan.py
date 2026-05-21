from __future__ import annotations

import json
from pathlib import Path

import iaqualink.cli.app as cli_module
from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    invoke_with_jar,
    make_fan,
    make_switch,
)

# ---------------------------------------------------------------------------
# _format_device_line
# ---------------------------------------------------------------------------


def test_format_device_line_fan_with_preset_shows_preset() -> None:
    fan = make_fan(
        "VSP",
        supports_presets=True,
        presets=["LOW", "CUSTOM"],
        preset_mode="CUSTOM",
    )
    text = cli_module._format_device_line("vsp", fan)
    assert "VSP" in text.plain
    assert "CUSTOM" in text.plain


def test_format_device_line_fan_without_preset_no_crash() -> None:
    fan = make_fan(
        "VSP", is_on=True, supports_presets=False, supports_turn_on=True
    )
    text = cli_module._format_device_line("vsp", fan)
    assert "VSP" in text.plain
    assert "on" in text.plain


def test_format_device_line_fan_no_controls_shows_dim() -> None:
    fan = make_fan("VSP", supports_presets=False)
    text = cli_module._format_device_line("vsp", fan)
    assert "VSP" in text.plain
    assert ": " not in text.plain


def test_format_device_line_fan_preset_and_percentage() -> None:
    fan = make_fan(
        "VSP",
        supports_presets=True,
        presets=["CUSTOM"],
        preset_mode="CUSTOM",
        supports_percentage=True,
        percentage=65,
    )
    text = cli_module._format_device_line("vsp", fan)
    assert "CUSTOM" in text.plain
    assert "65%" in text.plain


# ---------------------------------------------------------------------------
# turn-on / turn-off
# ---------------------------------------------------------------------------


def test_turn_on_pump_with_support(tmp_path: Path) -> None:
    pump = make_fan("VSP", is_on=False, supports_turn_on=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "turn-on", "vsp")
    assert result.exit_code == 0
    assert "VSP" in result.output


def test_turn_on_pump_without_support_exits(tmp_path: Path) -> None:
    pump = make_fan("VSP", is_on=False, supports_turn_on=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "turn-on", "vsp")
    assert result.exit_code == 1
    assert "does not support turn on" in result.stderr


def test_turn_off_pump_with_support(tmp_path: Path) -> None:
    pump = make_fan("VSP", is_on=True, supports_turn_off=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "turn-off", "vsp")
    assert result.exit_code == 0
    assert "VSP" in result.output


def test_turn_off_pump_without_support_exits(tmp_path: Path) -> None:
    pump = make_fan("VSP", is_on=True, supports_turn_off=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "turn-off", "vsp")
    assert result.exit_code == 1
    assert "does not support turn off" in result.stderr


# ---------------------------------------------------------------------------
# set-speed
# ---------------------------------------------------------------------------


def test_set_speed_pump_with_support(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_percentage=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-speed", "vsp", "75")
    assert result.exit_code == 0
    assert "75%" in result.output
    assert "VSP" in result.output


def test_set_speed_pump_without_support_exits(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_percentage=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-speed", "vsp", "75")
    assert result.exit_code == 1
    assert "does not support speed control" in result.stderr


def test_set_speed_non_pump_exits(tmp_path: Path) -> None:
    switch = make_switch("Filter", is_on=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"filter": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-speed", "filter", "50")
    assert result.exit_code == 1
    assert "is not a fan/pump" in result.stderr


def test_set_speed_saves_jar(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_percentage=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, cookie_jar = invoke_with_jar(tmp_path, "set-speed", "vsp", "50")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


def test_set_speed_out_of_range_exits(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_percentage=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-speed", "vsp", "150")
    assert result.exit_code == 2
    assert "150" in result.output


# ---------------------------------------------------------------------------
# set-preset
# ---------------------------------------------------------------------------


def test_set_preset_pump_with_support(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_presets=True, presets=["Low", "High"])
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-preset", "vsp", "Low")
    assert result.exit_code == 0
    assert "Low" in result.output
    assert "VSP" in result.output


def test_set_preset_pump_without_support_exits(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_presets=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-preset", "vsp", "Low")
    assert result.exit_code == 1
    assert "does not support presets" in result.stderr


def test_set_preset_non_pump_exits(tmp_path: Path) -> None:
    switch = make_switch("Filter", is_on=True)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"filter": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-preset", "filter", "Low")
    assert result.exit_code == 1
    assert "is not a fan/pump" in result.stderr


def test_set_preset_saves_jar(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_presets=True, presets=["Low", "High"])
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, cookie_jar = invoke_with_jar(tmp_path, "set-preset", "vsp", "High")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


def test_set_preset_invalid_preset_exits(tmp_path: Path) -> None:
    pump = make_fan("VSP", supports_presets=True, presets=["Low", "High"])
    pump.set_preset_mode.side_effect = AqualinkInvalidParameterException(
        "Bogus"
    )
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"vsp": pump})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-preset", "vsp", "Bogus")
    assert result.exit_code == 1
    assert "Bogus" in result.stderr
