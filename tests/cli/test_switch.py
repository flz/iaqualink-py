from __future__ import annotations

import json
from pathlib import Path

import iaqualink.cli.app as cli_module

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    invoke_with_jar,
    make_switch,
)


def test_format_device_line_switch_shows_on_off() -> None:
    device = make_switch("Pool Pump", is_on=True)
    text = cli_module._format_device_line("pump", device)
    assert "Pool Pump" in text.plain
    assert "on" in text.plain


def test_turn_on_saves_jar_after_command(tmp_path: Path) -> None:
    switch = make_switch("Pump", is_on=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"pump": switch})
        }
    )
    result, cookie_jar = invoke_with_jar(tmp_path, "turn-on", "pump")
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"
