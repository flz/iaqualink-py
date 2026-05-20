from __future__ import annotations

import json
from pathlib import Path

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    _invoke_with_jar,
    make_climate,
)


def test_set_temperature_saves_jar_after_command(tmp_path: Path) -> None:
    thermostat = make_climate("Heater")
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
