from __future__ import annotations

import importlib
import json
from pathlib import Path

from typer.testing import CliRunner

from iaqualink.client import AqualinkAuthState
from iaqualink.device import AqualinkDevice, AqualinkSwitch, AqualinkThermostat
from iaqualink.exception import AqualinkServiceUnauthorizedException

cli_app = importlib.import_module("iaqualink.cli.app")
runner = CliRunner()


class FakeClient:
    systems: dict[str, FakeSystem] = {}
    get_systems_side_effects: list[Exception | dict[str, FakeSystem]] = []
    last_credentials: tuple[str, str] | None = None
    login_call_count: int = 0

    def __init__(
        self,
        username: str,
        password: str,
        httpx_client: object | None = None,
    ) -> None:
        del httpx_client
        self.username = username
        self.password = password

        self._logged = False
        self._auth_state: AqualinkAuthState | None = None

    def _mark_logged_in(self) -> None:
        self._logged = True
        self._auth_state = AqualinkAuthState(
            username=self.username,
            client_id="session-id",
            authentication_token="token",
            user_id="user-id",
            id_token="id-token",
            refresh_token="refresh-token",
        )
        type(self).login_call_count += 1

    async def __aenter__(self) -> FakeClient:
        type(self).last_credentials = (self.username, self.password)
        if not self._logged:
            self._mark_logged_in()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    @property
    def auth_state(self) -> AqualinkAuthState | None:
        return self._auth_state

    @auth_state.setter
    def auth_state(self, state: AqualinkAuthState | None) -> None:
        self._auth_state = state
        if state:
            self._logged = True
        else:
            self._logged = False

    async def login(self) -> None:
        self._mark_logged_in()

    async def get_systems(self) -> dict[str, FakeSystem]:
        side_effects = type(self).get_systems_side_effects
        if side_effects:
            next_result = side_effects.pop(0)
            if isinstance(next_result, Exception):
                raise next_result
            return next_result

        return self.systems


class FakeSystem:
    def __init__(
        self,
        name: str,
        serial: str,
        device_type: str = "iaqua",
        devices: dict[str, AqualinkDevice] | None = None,
    ) -> None:
        self.data = {
            "name": name,
            "serial_number": serial,
            "device_type": device_type,
        }
        self.devices = devices or {}

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def serial(self) -> str:
        return self.data["serial_number"]

    async def get_devices(self) -> dict[str, AqualinkDevice]:
        return self.devices


class FakeDevice(AqualinkDevice):
    def __init__(
        self,
        system: FakeSystem,
        name: str,
        label: str,
        state: str = "",
    ) -> None:
        super().__init__(system, {"name": name, "label": label, "state": state})

    @property
    def label(self) -> str:
        return str(self.data["label"])

    @property
    def state(self) -> str:
        return str(self.data["state"])

    @property
    def name(self) -> str:
        return str(self.data["name"])

    @property
    def manufacturer(self) -> str:
        return "Fake"

    @property
    def model(self) -> str:
        return "FakeDevice"


class FakeSwitch(FakeDevice, AqualinkSwitch):
    def __init__(
        self,
        system: FakeSystem,
        name: str,
        label: str,
        state: str = "off",
    ) -> None:
        super().__init__(system, name, label, state)
        self.commands: list[str] = []

    async def turn_on(self) -> None:
        self.commands.append("on")
        self.data["state"] = "on"

    async def turn_off(self) -> None:
        self.commands.append("off")
        self.data["state"] = "off"


class FakeThermostat(FakeSwitch, AqualinkThermostat):
    @property
    def unit(self) -> str:
        return "F"

    @property
    def current_temperature(self) -> str:
        return str(self.data.get("current_temperature", self.state))

    @property
    def target_temperature(self) -> str:
        return self.state

    @property
    def max_temperature(self) -> int:
        return 104

    @property
    def min_temperature(self) -> int:
        return 34

    async def set_temperature(self, temperature: int) -> None:
        self.commands.append(f"temp:{temperature}")
        self.data["state"] = str(temperature)


def _write_config(
    tmp_path: Path,
    username: str = "config-user",
    password: str = "config-pass",
) -> Path:
    config_path = tmp_path / "iaqualink.yaml"
    config_path.write_text(
        f"username: {username}\npassword: {password}\n",
        encoding="utf-8",
    )
    return config_path


def _write_session_jar(tmp_path: Path, auth_state: dict[str, object]) -> Path:
    jar_path = tmp_path / "session.json"
    jar_path.write_text(json.dumps(auth_state), encoding="utf-8")
    return jar_path


def test_list_systems_uses_config_credentials(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = _write_config(tmp_path)
    FakeClient.systems = {
        "SER-2": FakeSystem("Back Pool", "SER-2", "exo"),
        "SER-1": FakeSystem("Front Pool", "SER-1", "iaqua"),
    }

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        ["list-systems", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert FakeClient.last_credentials == ("config-user", "config-pass")
    assert result.output.splitlines() == [
        "Back Pool (SER-2) [exo]",
        "Front Pool (SER-1) [iaqua]",
    ]


def test_env_credentials_override_config(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    FakeClient.systems = {"SER-1": FakeSystem("Front Pool", "SER-1")}

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)
    monkeypatch.setenv("IAQUALINK_USERNAME", "env-user")
    monkeypatch.setenv("IAQUALINK_PASSWORD", "env-pass")

    result = runner.invoke(
        cli_app.app,
        ["list-systems", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert FakeClient.last_credentials == ("env-user", "env-pass")


def test_debug_option_configures_logging(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    FakeClient.systems = {"SER-1": FakeSystem("Pool", "SER-1")}
    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    root_logger = cli_app.logging.getLogger()
    iaqualink_logger = cli_app.logging.getLogger("iaqualink")
    original_root_level = root_logger.level
    original_root_handlers = list(root_logger.handlers)
    original_iaqualink_level = iaqualink_logger.level
    original_iaqualink_handlers = list(iaqualink_logger.handlers)
    original_iaqualink_propagate = iaqualink_logger.propagate

    try:
        result = runner.invoke(
            cli_app.app,
            ["--debug", "list-systems", "--config", str(config_path)],
        )

        assert result.exit_code == 0
        assert root_logger.level == original_root_level
        assert root_logger.handlers == original_root_handlers
        assert iaqualink_logger.level == cli_app.logging.DEBUG
        assert iaqualink_logger.propagate is False
        debug_handlers = [
            handler
            for handler in iaqualink_logger.handlers
            if handler.get_name() == cli_app.DEBUG_HANDLER_NAME
        ]
        assert len(debug_handlers) == 1
        assert debug_handlers[0].level == cli_app.logging.DEBUG
        assert debug_handlers[0].formatter is not None
        assert debug_handlers[0].formatter._fmt == cli_app.DEBUG_LOG_FORMAT
    finally:
        root_logger.setLevel(original_root_level)
        root_logger.handlers[:] = original_root_handlers
        iaqualink_logger.setLevel(original_iaqualink_level)
        iaqualink_logger.handlers[:] = original_iaqualink_handlers
        iaqualink_logger.propagate = original_iaqualink_propagate


def test_list_devices_renders_tree(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    system = FakeSystem("Front Pool", "SER-1")
    system.devices = {
        "pool_temp": FakeDevice(system, "pool_temp", "Pool Temp", "82"),
        "pool_pump": FakeSwitch(system, "pool_pump", "Pool Pump", "on"),
    }
    FakeClient.systems = {system.serial: system}

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        ["list-devices", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "└── Front Pool (SER-1) [iaqua]",
        "    ├── Pool Pump [pool_pump]: on",
        "    └── Pool Temp [pool_temp]: 82",
    ]


def test_turn_on_resolves_device_by_label(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    system = FakeSystem("Front Pool", "SER-1")
    pool_pump = FakeSwitch(system, "pool_pump", "Pool Pump", "off")
    system.devices = {"pool_pump": pool_pump}
    FakeClient.systems = {system.serial: system}

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        ["turn-on", "Pool Pump", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert pool_pump.commands == ["on"]
    assert "Sent on command to Pool Pump [pool_pump]" in result.output


def test_set_temperature_rejects_non_thermostat(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    system = FakeSystem("Front Pool", "SER-1")
    system.devices = {"pool_pump": FakeSwitch(system, "pool_pump", "Pool Pump")}
    FakeClient.systems = {system.serial: system}

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        [
            "set-temperature",
            "pool_pump",
            "90",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 1
    assert "does not support temperature changes" in result.output


def test_turn_on_requires_system_selector_when_multiple(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    first_system = FakeSystem("Front Pool", "SER-1")
    second_system = FakeSystem("Back Pool", "SER-2")
    first_system.devices = {
        "pool_pump": FakeSwitch(first_system, "pool_pump", "Pool Pump")
    }
    second_system.devices = {
        "pool_pump": FakeSwitch(second_system, "pool_pump", "Pool Pump")
    }
    FakeClient.systems = {
        first_system.serial: first_system,
        second_system.serial: second_system,
    }

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        ["turn-on", "pool_pump", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "Multiple systems found. Use --system" in result.output


def test_cookie_jar_saves_session_on_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    jar_path = tmp_path / "session.json"
    FakeClient.systems = {"SER-1": FakeSystem("Pool", "SER-1")}
    FakeClient.login_call_count = 0

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )

    assert result.exit_code == 0
    assert jar_path.exists()
    assert json.loads(jar_path.read_text(encoding="utf-8"))["username"] == (
        "config-user"
    )


def test_cookie_jar_reuses_session_on_second_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    jar_path = tmp_path / "session.json"
    FakeClient.systems = {"SER-1": FakeSystem("Pool", "SER-1")}
    FakeClient.login_call_count = 0

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    first = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )
    assert first.exit_code == 0

    FakeClient.login_call_count = 0
    second = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )

    assert second.exit_code == 0
    assert FakeClient.login_call_count == 0


def test_cookie_jar_reauthenticates_stale_restored_session(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    jar_path = tmp_path / "session.json"
    systems = {"SER-1": FakeSystem("Pool", "SER-1")}
    FakeClient.systems = systems
    FakeClient.get_systems_side_effects = []

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    first = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )
    assert first.exit_code == 0

    FakeClient.login_call_count = 0
    FakeClient.get_systems_side_effects = [
        AqualinkServiceUnauthorizedException(),
        systems,
    ]

    second = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )

    assert second.exit_code == 0
    assert FakeClient.login_call_count == 1
    assert second.output.splitlines() == ["Pool (SER-1) [iaqua]"]


def test_cookie_jar_handles_missing_file_gracefully(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    jar_path = tmp_path / "missing" / "session.json"
    FakeClient.systems = {"SER-1": FakeSystem("Pool", "SER-1")}

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )

    assert result.exit_code == 0
    assert "Pool (SER-1)" in result.output


def test_cookie_jar_handles_invalid_json_gracefully(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    jar_path = tmp_path / "session.json"
    jar_path.write_text("{ invalid json }", encoding="utf-8")
    FakeClient.systems = {"SER-1": FakeSystem("Pool", "SER-1")}

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )

    assert result.exit_code == 0


def test_cookie_jar_creates_parent_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    jar_path = tmp_path / "nested" / "dir" / "session.json"
    FakeClient.systems = {"SER-1": FakeSystem("Pool", "SER-1")}

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )

    assert result.exit_code == 0
    assert jar_path.exists()


def test_cookie_jar_mismatched_username_not_restored(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path, username="current-user")
    jar_path = _write_session_jar(
        tmp_path,
        {
            "username": "other-user",
            "client_id": "session-id",
            "authentication_token": "token",
            "user_id": "user-id",
            "id_token": "id-token",
            "refresh_token": "refresh-token",
        },
    )
    FakeClient.systems = {"SER-1": FakeSystem("Pool", "SER-1")}
    FakeClient.login_call_count = 0

    monkeypatch.setattr(cli_app, "AqualinkClient", FakeClient)

    result = runner.invoke(
        cli_app.app,
        [
            "list-systems",
            "--config",
            str(config_path),
            "--cookie-jar",
            str(jar_path),
        ],
    )

    assert result.exit_code == 0
    assert FakeClient.login_call_count == 1
