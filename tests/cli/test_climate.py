from __future__ import annotations

import json
from pathlib import Path

import iaqualink.cli.app as cli_module

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    invoke_with_jar,
    make_climate,
)


def test_format_device_line_climate_with_temps() -> None:
    thermostat = make_climate(
        current_temperature=78, target_temperature=82, is_on=True
    )
    text = cli_module._format_device_line("heater", thermostat)
    assert "78" in text.plain
    assert "82" in text.plain
    assert "on" in text.plain


def test_format_device_line_climate_cur_only_shows_cur() -> None:
    thermostat = make_climate(current_temperature=78, is_on=True)
    text = cli_module._format_device_line("heater", thermostat)
    assert "78" in text.plain
    assert "on" in text.plain


def test_format_device_line_climate_without_temps_shows_on_off() -> None:
    thermostat = make_climate(is_on=False)
    text = cli_module._format_device_line("heater", thermostat)
    assert "off" in text.plain


def test_set_temperature_saves_jar_after_command(tmp_path: Path) -> None:
    thermostat = make_climate("Heater")
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink(
                "SN001", "Pool", {"heater": thermostat}
            )
        }
    )
    result, cookie_jar = invoke_with_jar(
        tmp_path, "set-temperature", "heater", "78"
    )
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"
