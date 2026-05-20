from __future__ import annotations

from pathlib import Path

import iaqualink.cli.app as cli_module

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    _invoke_with_jar,
    make_binary_sensor,
    make_sensor,
)


def test_format_device_line_sensor_with_value() -> None:
    device = make_sensor("Pool Temp", "82")
    text = cli_module._format_device_line("temp", device)
    assert "Pool Temp" in text.plain
    assert "[temp]" in text.plain
    assert "82" in text.plain
    assert ": " in text.plain


def test_format_device_line_sensor_none_value() -> None:
    device = make_sensor("Pool Temp", None)
    text = cli_module._format_device_line("temp", device)
    assert "Pool Temp" in text.plain
    assert "[temp]" in text.plain
    assert ": " not in text.plain


def test_format_device_line_sensor_empty_value() -> None:
    device = make_sensor("Pool Temp", "")
    text = cli_module._format_device_line("temp", device)
    assert "Pool Temp" in text.plain
    assert ": " not in text.plain


def test_format_device_line_sensor_uses_translated_value() -> None:
    device = make_sensor("Pool Temp", "1", value_translated="ON")
    text = cli_module._format_device_line("temp", device)
    assert "1" in text.plain
    assert "(ON)" in text.plain


def test_format_device_line_sensor_no_translation_omits_parentheses() -> None:
    device = make_sensor("Pool Temp", "82")
    text = cli_module._format_device_line("temp", device)
    assert "82" in text.plain
    assert "(" not in text.plain


def test_format_device_line_sensor_unknown_enum_value_omits_parentheses() -> (
    None
):
    device = make_sensor("Pool Temp", "99")
    text = cli_module._format_device_line("temp", device)
    assert "99" in text.plain
    assert "(" not in text.plain


def test_format_device_line_binary_sensor_shows_on_off() -> None:
    device = make_binary_sensor("Freeze", is_on=True)
    text = cli_module._format_device_line("freeze", device)
    assert "Freeze" in text.plain
    assert "on" in text.plain


def test_turn_on_sensor_exits(tmp_path: Path) -> None:
    sensor = make_sensor("Temp", "72")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"temp": sensor})
        }
    )
    result, _ = _invoke_with_jar(tmp_path, "turn-on", "temp")
    assert result.exit_code == 1
    assert "does not support power controls" in result.stderr


def test_turn_off_sensor_exits(tmp_path: Path) -> None:
    sensor = make_sensor("Temp", "72")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"temp": sensor})
        }
    )
    result, _ = _invoke_with_jar(tmp_path, "turn-off", "temp")
    assert result.exit_code == 1
    assert "does not support power controls" in result.stderr
