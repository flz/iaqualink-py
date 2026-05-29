from __future__ import annotations

import importlib
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
from rich.console import Console as RichConsole
from typer.testing import CliRunner

from iaqualink.client import AqualinkAuthState
from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkClimate,
    AqualinkFan,
    AqualinkLight,
    AqualinkNumber,
    AqualinkSensor,
    AqualinkSwitch,
)
from iaqualink.system import SystemStatus, UnsupportedSystem
from iaqualink.systems.iaqua.device import IaquaIclLight

cli_module = importlib.import_module("iaqualink.cli.app")
app = cli_module.app

_POST_DEVICE_AUTH = AqualinkAuthState(
    username="user@example.com",
    client_id="post-device-session",
    authentication_token="post-device-token",
    user_id="user-id",
    id_token="post-device-id-token",
    refresh_token="post-device-refresh-token",
)


class FakeSystem:
    supported = True

    def __init__(self, serial: str, name: str) -> None:
        self.serial = serial
        self.name = name
        self.data = {"device_type": "iaqua"}

    @property
    def status(self) -> SystemStatus:
        return SystemStatus.UNKNOWN

    @property
    def status_translated(self) -> str:
        return "Unknown"

    async def get_devices(self) -> dict[str, object]:
        return {}


class FakeClient:
    systems_factory = staticmethod(dict[str, FakeSystem])
    login_call_count = 0

    def __init__(
        self,
        username: str,
        password: str,
        event_hooks: dict | None = None,
    ) -> None:
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


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.login_call_count = 0
    FakeClient.systems_factory = staticmethod(dict[str, FakeSystem])
    monkeypatch.setattr(cli_module, "AqualinkClient", FakeClient)
    monkeypatch.setattr(cli_module, "_capture_session", None)


def make_unsupported_system(
    serial: str = "SN001", name: str = "Pool"
) -> UnsupportedSystem:
    data = {"serial_number": serial, "name": name, "device_type": "foo"}
    return UnsupportedSystem(MagicMock(), data)


def render_plain(renderable: object) -> str:
    buf = StringIO()
    RichConsole(file=buf, no_color=True, width=120).print(renderable)
    return buf.getvalue()


def invoke_with_jar(tmp_path: Path, *args: str) -> tuple:
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


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def make_switch(label: str = "Switch", *, is_on: bool = True) -> AqualinkSwitch:
    m = create_autospec(AqualinkSwitch, instance=True)
    m.label = m.name = label
    m.manufacturer = m.model = ""
    m.is_on = is_on
    return m


def make_binary_sensor(
    label: str = "Sensor", *, is_on: bool = True
) -> AqualinkBinarySensor:
    m = create_autospec(AqualinkBinarySensor, instance=True)
    m.label = m.name = label
    m.manufacturer = m.model = ""
    m.is_on = is_on
    return m


def make_sensor(
    label: str = "Sensor",
    value: str | None = "1",
    *,
    value_translated: str | None = None,
) -> AqualinkSensor:
    m = create_autospec(AqualinkSensor, instance=True)
    m.label = m.name = label
    m.manufacturer = m.model = ""
    m.value = value
    m.value_translated = value_translated
    return m


def make_light(
    label: str = "Light",
    *,
    is_on: bool = True,
    supports_brightness: bool = False,
    brightness: int | None = None,
    supports_effect: bool = False,
    effect: str | None = None,
    effect_list: list[str] | None = None,
) -> AqualinkLight:
    m = create_autospec(AqualinkLight, instance=True)
    m.label = m.name = label
    m.manufacturer = m.model = ""
    m.is_on = is_on
    m.supports_brightness = supports_brightness
    m.brightness_percentage = brightness
    m.supports_effect = supports_effect
    m.effect = effect
    m.effect_list = effect_list
    m.supports_rgbw = False
    return m


def make_rgbw_light(label: str = "ICL Light") -> IaquaIclLight:
    m = create_autospec(IaquaIclLight, instance=True)
    m.label = m.name = label
    m.rgbw = (0, 0, 0, 0)
    m.supports_rgbw = True
    return m


def make_fan(
    label: str = "VSP",
    *,
    is_on: bool = True,
    supports_turn_on: bool = False,
    supports_turn_off: bool = False,
    supports_percentage: bool = False,
    percentage: int | None = None,
    supports_presets: bool = False,
    presets: list[str] | None = None,
    preset_mode: str | None = None,
) -> AqualinkFan:
    m = create_autospec(AqualinkFan, instance=True)
    m.label = m.name = label
    m.manufacturer = m.model = ""
    m.is_on = is_on
    m.supports_turn_on = supports_turn_on
    m.supports_turn_off = supports_turn_off
    m.supports_percentage = supports_percentage
    m.percentage = percentage
    m.supports_presets = supports_presets
    m.preset_modes = presets or []
    m.preset_mode = preset_mode
    return m


def make_number(
    label: str = "RPM",
    current_value: float | None = 1500.0,
    *,
    min_value: float = 0.0,
    max_value: float = 3450.0,
    unit: str | None = "RPM",
) -> AqualinkNumber:
    m = create_autospec(AqualinkNumber, instance=True)
    m.label = m.name = label
    m.manufacturer = m.model = ""
    m.current_value = current_value
    m.min_value = min_value
    m.max_value = max_value
    m.unit_of_measurement = unit
    return m


def make_climate(
    label: str = "Heater",
    *,
    is_on: bool = True,
    temperature_unit: str = "F",
    min_temp: int = 40,
    max_temp: int = 104,
    current_temperature: str | None = None,
    target_temperature: str | None = None,
) -> AqualinkClimate:
    m = create_autospec(AqualinkClimate, instance=True)
    m.label = m.name = label
    m.manufacturer = m.model = ""
    m.is_on = is_on
    m.temperature_unit = temperature_unit
    m.min_temp = min_temp
    m.max_temp = max_temp
    m.current_temperature = current_temperature
    m.target_temperature = target_temperature
    return m
