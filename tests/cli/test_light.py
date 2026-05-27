from __future__ import annotations

import json
from pathlib import Path

import iaqualink.cli.app as cli_module
from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import (
    FakeClient,
    FakeSystemWithAqualink,
    invoke_with_jar,
    make_light,
    make_rgbw_light,
    make_switch,
)


def test_format_device_line_light_shows_on_off() -> None:
    device = make_light("Spa Light", is_on=True)
    text = cli_module._format_device_line("spa_light", device)
    assert "Spa Light" in text.plain
    assert "on" in text.plain


# ---------------------------------------------------------------------------
# set-brightness
# ---------------------------------------------------------------------------


def test_set_brightness_succeeds_on_dimmable_light(tmp_path: Path) -> None:
    light = make_light("Spa Light", supports_brightness=True, brightness=100)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-brightness", "light", "75")
    assert result.exit_code == 0
    assert "75%" in result.stdout
    light.set_brightness_percentage.assert_called_once_with(75)  # type: ignore[attr-defined, unresolved-attribute]  # ty: ignore


def test_set_brightness_fails_on_non_light(tmp_path: Path) -> None:
    switch = make_switch("Pump", is_on=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"pump": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-brightness", "pump", "50")
    assert result.exit_code == 1
    assert "not a light" in result.stderr


def test_set_brightness_fails_on_non_dimmable_light(tmp_path: Path) -> None:
    light = make_light("Pool Light", supports_brightness=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-brightness", "light", "50")
    assert result.exit_code == 1
    assert "does not support brightness" in result.stderr


def test_set_brightness_saves_jar_after_command(tmp_path: Path) -> None:
    light = make_light("Spa Light", supports_brightness=True, brightness=100)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, cookie_jar = invoke_with_jar(
        tmp_path, "set-brightness", "light", "50"
    )
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


# ---------------------------------------------------------------------------
# set-effect
# ---------------------------------------------------------------------------


def test_set_effect_succeeds_on_color_light(tmp_path: Path) -> None:
    light = make_light(
        "Color Light",
        supports_effect=True,
        effect="Alpine White",
        effect_list=["Alpine White", "Off"],
    )
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-effect", "light", "Alpine White")
    assert result.exit_code == 0
    assert "Alpine White" in result.stdout
    light.set_effect.assert_called_once_with("Alpine White")  # type: ignore[attr-defined, unresolved-attribute]  # ty: ignore


def test_set_effect_fails_on_non_light(tmp_path: Path) -> None:
    switch = make_switch("Pump", is_on=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"pump": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-effect", "pump", "Alpine White")
    assert result.exit_code == 1
    assert "not a light" in result.stderr


def test_set_effect_fails_on_non_color_light(tmp_path: Path) -> None:
    light = make_light("Pool Light", supports_effect=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-effect", "light", "Alpine White")
    assert result.exit_code == 1
    assert "does not support color effects" in result.stderr


def test_set_effect_saves_jar_after_command(tmp_path: Path) -> None:
    light = make_light(
        "Color Light",
        supports_effect=True,
        effect="Alpine White",
        effect_list=["Alpine White", "Off"],
    )
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, cookie_jar = invoke_with_jar(
        tmp_path, "set-effect", "light", "Alpine White"
    )
    assert result.exit_code == 0
    data = json.loads(cookie_jar.read_text())
    assert data["client_id"] == "post-device-session"


def test_set_effect_rejects_unknown_effect_name(tmp_path: Path) -> None:
    light = make_light(
        "Color Light",
        supports_effect=True,
        effect="Alpine White",
        effect_list=["Alpine White", "Off"],
    )
    light.set_effect.side_effect = AqualinkInvalidParameterException(  # type: ignore[attr-defined, unresolved-attribute]  # ty: ignore
        "'Bogus' isn't a valid effect."
    )
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-effect", "light", "Bogus")
    assert result.exit_code == 1
    assert "Bogus" in result.stderr


# ---------------------------------------------------------------------------
# set-rgbw
# ---------------------------------------------------------------------------


def test_set_rgbw_succeeds(tmp_path: Path) -> None:
    light = make_rgbw_light()
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(
        tmp_path, "set-rgbw", "light", "255", "0", "128"
    )
    assert result.exit_code == 0
    assert "(255, 0, 128, 0)" in result.stdout
    light.set_rgbw.assert_awaited_once_with(255, 0, 128, 0)


def test_set_rgbw_succeeds_with_white(tmp_path: Path) -> None:
    light = make_rgbw_light()
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(
        tmp_path, "set-rgbw", "light", "100", "150", "200", "50"
    )
    assert result.exit_code == 0
    assert "(100, 150, 200, 50)" in result.stdout
    light.set_rgbw.assert_awaited_once_with(100, 150, 200, 50)


def test_set_rgbw_fails_on_non_light(tmp_path: Path) -> None:
    switch = make_switch("Filter", is_on=False)
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"filter": switch})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-rgbw", "filter", "255", "0", "0")
    assert result.exit_code == 1
    assert "is not a light" in result.stderr


def test_set_rgbw_fails_on_non_rgbw_light(tmp_path: Path) -> None:
    light = make_light()
    FakeClient.systems_factory = staticmethod(
        lambda: {
            "SN001": FakeSystemWithAqualink("SN001", "Pool", {"light": light})
        }
    )
    result, _ = invoke_with_jar(tmp_path, "set-rgbw", "light", "255", "0", "0")
    assert result.exit_code == 1
    assert "does not support RGBW" in result.stderr
