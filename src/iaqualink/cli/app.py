from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
import yaml

from iaqualink.client import AqualinkAuthState, AqualinkClient
from iaqualink.device import AqualinkDevice, AqualinkSwitch, AqualinkThermostat
from iaqualink.exception import (
    AqualinkException,
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.cyclobat.system import CyclobatSystem
from iaqualink.systems.cyclonext.const import (
    CYCLE_FLOOR,
    CYCLE_FLOOR_AND_WALLS,
    CYCLE_LABELS,
    MODE_LABELS,
)
from iaqualink.systems.cyclonext.system import CyclonextSystem
from iaqualink.systems.i2d_robot.system import I2dRobotSystem
from iaqualink.systems.vortrax.system import VortraxSystem
from iaqualink.systems.vr.system import VrSystem
from iaqualink.version import __version__

app = typer.Typer(
    add_completion=False,
    help="Command line client for Jandy iAqualink systems.",
    no_args_is_help=True,
)

LOGGER = logging.getLogger("iaqualink.cli")
DEBUG_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
DEBUG_HANDLER_NAME = "iaqualink.cli.debug"

APP_DIR = Path(typer.get_app_dir("iaqualink"))
DEFAULT_CONFIG_PATH = APP_DIR / "config.yaml"
USERNAME_ENV_VAR = "IAQUALINK_USERNAME"
PASSWORD_ENV_VAR = "IAQUALINK_PASSWORD"
DEFAULT_COOKIE_JAR = APP_DIR / "session.json"

UsernameOption = Annotated[
    str | None,
    typer.Option(help="iAqualink username or email."),
]
PasswordOption = Annotated[
    str | None,
    typer.Option(help="iAqualink password."),
]
ConfigOption = Annotated[
    Path,
    typer.Option(help="Path to a YAML config file with username/password."),
]
CookieJarOption = Annotated[
    Path,
    typer.Option(
        "--cookie-jar",
        help=(
            f"Path to session cookie jar file (default: {DEFAULT_COOKIE_JAR})."
        ),
    ),
]
SystemOption = Annotated[
    str | None,
    typer.Option(
        "--system",
        help="System serial number. Required when multiple systems exist.",
    ),
]
DeviceArgument = Annotated[
    str,
    typer.Argument(help="Device key or label."),
]


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


def main() -> None:
    app()


def _configure_logging(debug: bool) -> None:
    if not debug:
        return

    iaqualink_logger = logging.getLogger("iaqualink")
    iaqualink_logger.setLevel(logging.DEBUG)
    iaqualink_logger.propagate = False

    for handler in iaqualink_logger.handlers:
        if handler.get_name() == DEBUG_HANDLER_NAME:
            handler.setLevel(logging.DEBUG)
            break
    else:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(DEBUG_LOG_FORMAT))
        handler.set_name(DEBUG_HANDLER_NAME)
        iaqualink_logger.addHandler(handler)

    LOGGER.debug("Debug logging enabled")


def _exit_with_error(message: str, code: int = 1) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=code)


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    try:
        with config_path.open(encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle) or {}
    except OSError as exc:
        _exit_with_error(f"Could not read config file {config_path}: {exc}")
    except yaml.YAMLError as exc:
        _exit_with_error(f"Could not parse config file {config_path}: {exc}")

    if not isinstance(data, dict):
        _exit_with_error(
            f"Config file {config_path} must contain a mapping.",
        )

    return data


def _resolve_credentials(
    username: str | None,
    password: str | None,
    config_path: Path,
) -> Credentials:
    config = _load_config(config_path)

    resolved_username = (
        username or os.getenv(USERNAME_ENV_VAR) or config.get("username")
    )
    resolved_password = (
        password or os.getenv(PASSWORD_ENV_VAR) or config.get("password")
    )

    if not resolved_username:
        _exit_with_error(
            "Missing username. Use --username, set IAQUALINK_USERNAME, "
            f"or add username to {config_path}.",
        )
    if not resolved_password:
        _exit_with_error(
            "Missing password. Use --password, set IAQUALINK_PASSWORD, "
            f"or add password to {config_path}.",
        )

    return Credentials(
        username=str(resolved_username),
        password=str(resolved_password),
    )


def _run_async(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except AqualinkServiceUnauthorizedException:
        _exit_with_error("Authentication failed.")
    except AqualinkServiceThrottledException as exc:
        _exit_with_error(str(exc))
    except AqualinkSystemOfflineException as exc:
        _exit_with_error(str(exc))
    except AqualinkInvalidParameterException as exc:
        _exit_with_error(str(exc))
    except AqualinkOperationNotSupportedException:
        _exit_with_error("This device does not support that operation.")
    except AqualinkException as exc:
        _exit_with_error(str(exc) or exc.__class__.__name__)


async def _fetch_systems(
    credentials: Credentials,
    cookie_jar: Path,
) -> dict[str, AqualinkSystem]:
    client = AqualinkClient(
        username=credentials.username,
        password=credentials.password,
    )
    session_state = _load_session_jar(cookie_jar, credentials.username)
    restored_session = session_state is not None
    if session_state is not None:
        client.auth_state = session_state

    async with client:
        try:
            systems = await client.get_systems()
        except AqualinkServiceUnauthorizedException:
            if not restored_session:
                raise

            LOGGER.debug("Restored CLI session was stale, reauthenticating")
            await client.login()
            systems = await client.get_systems()

        _save_session_jar(cookie_jar, client.auth_state)
        return systems


async def _load_devices_for_system(
    system: AqualinkSystem,
) -> dict[str, AqualinkDevice]:
    return await system.get_devices()


def _sorted_systems(
    systems: dict[str, AqualinkSystem],
) -> list[tuple[str, AqualinkSystem]]:
    return sorted(
        systems.items(),
        key=lambda item: (item[1].name.casefold(), item[0]),
    )


def _sorted_devices(
    devices: dict[str, AqualinkDevice],
) -> list[tuple[str, AqualinkDevice]]:
    return sorted(
        devices.items(),
        key=lambda item: (item[1].label.casefold(), item[0]),
    )


def _format_system_line(system: AqualinkSystem) -> str:
    system_type = system.data.get("device_type", "unknown")
    return f"{system.name} ({system.serial}) [{system_type}]"


def _format_device_line(device_name: str, device: AqualinkDevice) -> str:
    line = f"{device.label} [{device_name}]"
    if device.state:
        line += f": {device.state}"
    return line


def _render_device_tree(
    systems: list[tuple[str, AqualinkSystem]],
    devices_by_system: dict[str, dict[str, AqualinkDevice]],
) -> str:
    lines: list[str] = []
    for index, (serial, system) in enumerate(systems):
        system_prefix = "└──" if index == len(systems) - 1 else "├──"
        child_indent = "    " if index == len(systems) - 1 else "│   "
        lines.append(f"{system_prefix} {_format_system_line(system)}")

        devices = _sorted_devices(devices_by_system.get(serial, {}))
        if not devices:
            lines.append(f"{child_indent}└── No devices found")
            continue

        for device_index, (device_name, device) in enumerate(devices):
            device_prefix = "└──" if device_index == len(devices) - 1 else "├──"
            lines.append(
                f"{child_indent}{device_prefix} "
                f"{_format_device_line(device_name, device)}"
            )

    return "\n".join(lines)


def _resolve_system(
    systems: dict[str, AqualinkSystem],
    selector: str | None,
) -> AqualinkSystem:
    if not systems:
        _exit_with_error("No systems found for this account.")

    if selector is not None:
        if selector in systems:
            return systems[selector]

        matching_systems = [
            system
            for _, system in _sorted_systems(systems)
            if system.name.casefold() == selector.casefold()
        ]
        if len(matching_systems) == 1:
            return matching_systems[0]
        if len(matching_systems) > 1:
            _exit_with_error(
                f"System name {selector!r} matches multiple systems. "
                "Use --system with the serial number instead.",
            )

        available = ", ".join(serial for serial, _ in _sorted_systems(systems))
        _exit_with_error(
            f"Unknown system {selector!r}. Available systems: {available}",
        )

    if len(systems) == 1:
        return next(iter(systems.values()))

    available = ", ".join(serial for serial, _ in _sorted_systems(systems))
    _exit_with_error(
        f"Multiple systems found. Use --system with one of: {available}",
    )


def _normalize_selector(value: str) -> str:
    return value.strip().casefold().replace(" ", "_")


def _load_session_jar(
    jar_path: Path,
    username: str,
) -> AqualinkAuthState | None:
    if not jar_path.exists():
        return None

    try:
        with jar_path.open(encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except (json.JSONDecodeError, OSError) as exc:
        LOGGER.debug("Could not load session jar %s: %s", jar_path, exc)
        return None

    if not isinstance(data, dict):
        return None

    if data.get("username") != username:
        return None

    try:
        return AqualinkAuthState.from_dict(data)
    except ValueError as exc:
        LOGGER.debug("Could not restore session jar %s: %s", jar_path, exc)
        return None


def _save_session_jar(
    jar_path: Path,
    auth_state: AqualinkAuthState | None,
) -> None:
    if not auth_state:
        return

    try:
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = jar_path.with_suffix(".tmp")
        fd = os.open(
            temp_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as file_handle:
            json.dump(auth_state.to_dict(), file_handle, indent=2)
        temp_path.replace(jar_path)
    except OSError as exc:
        LOGGER.warning("Could not save session jar to %s: %s", jar_path, exc)


def _resolve_device(
    devices: dict[str, AqualinkDevice],
    selector: str,
) -> tuple[str, AqualinkDevice]:
    if selector in devices:
        return selector, devices[selector]

    normalized_selector = _normalize_selector(selector)
    for device_name, device in _sorted_devices(devices):
        if _normalize_selector(device_name) == normalized_selector:
            return device_name, device

    label_matches = [
        (device_name, device)
        for device_name, device in _sorted_devices(devices)
        if _normalize_selector(device.label) == normalized_selector
    ]
    if len(label_matches) == 1:
        return label_matches[0]
    if len(label_matches) > 1:
        _exit_with_error(
            f"Device label {selector!r} is ambiguous. Use the device key instead.",
        )

    available = ", ".join(name for name, _ in _sorted_devices(devices))
    _exit_with_error(
        f"Unknown device {selector!r}. Available devices: {available}",
    )


async def _list_systems(
    credentials: Credentials,
    cookie_jar: Path,
) -> list[str]:
    systems = await _fetch_systems(credentials, cookie_jar)
    return [
        _format_system_line(system) for _, system in _sorted_systems(systems)
    ]


async def _list_devices(
    credentials: Credentials,
    system_selector: str | None,
    cookie_jar: Path,
) -> str:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    return _render_device_tree(
        [(system.serial, system)], {system.serial: devices}
    )


async def _status(
    credentials: Credentials,
    system_selector: str | None,
    cookie_jar: Path,
) -> str:
    systems = await _fetch_systems(credentials, cookie_jar)
    if system_selector is not None:
        system = _resolve_system(systems, system_selector)
        selected_systems = [(system.serial, system)]
    else:
        selected_systems = _sorted_systems(systems)

    devices_by_system: dict[str, dict[str, AqualinkDevice]] = {}
    for serial, system in selected_systems:
        devices_by_system[serial] = await _load_devices_for_system(system)

    return _render_device_tree(selected_systems, devices_by_system)


async def _run_switch_command(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    target_state: str,
    cookie_jar: Path,
) -> str:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkSwitch):
        _exit_with_error(
            f"Device {device_name!r} does not support power controls.",
        )

    if target_state == "on":
        await device.turn_on()
    else:
        await device.turn_off()

    return (
        f"Sent {target_state} command to {device.label} "
        f"[{device_name}] on {_format_system_line(system)}"
    )


async def _set_temperature(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    temperature: int,
    cookie_jar: Path,
) -> str:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkThermostat):
        _exit_with_error(
            f"Device {device_name!r} does not support temperature changes.",
        )

    await device.set_temperature(temperature)
    return (
        f"Set {device.label} [{device_name}] to {temperature}{device.unit} "
        f"on {_format_system_line(system)}"
    )


@app.callback()
def callback(
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug logging.",
            is_eager=True,
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the CLI version and exit.",
            is_eager=True,
        ),
    ] = False,
) -> None:
    _configure_logging(debug)

    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command("list-systems")
def list_systems(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    lines = _run_async(_list_systems(credentials, cookie_jar))
    for line in lines:
        typer.echo(line)


@app.command("list-devices")
def list_devices(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(_run_async(_list_devices(credentials, system, cookie_jar)))


@app.command()
def status(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(_run_async(_status(credentials, system, cookie_jar)))


@app.command("turn-on")
def turn_on(
    device: DeviceArgument,
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(
        _run_async(
            _run_switch_command(credentials, system, device, "on", cookie_jar)
        )
    )


@app.command("turn-off")
def turn_off(
    device: DeviceArgument,
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(
        _run_async(
            _run_switch_command(credentials, system, device, "off", cookie_jar)
        )
    )


@app.command("set-temperature")
def set_temperature(
    device: DeviceArgument,
    temperature: Annotated[int, typer.Argument(help="Target temperature.")],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(
        _run_async(
            _set_temperature(
                credentials, system, device, temperature, cookie_jar
            )
        )
    )


robot_app = typer.Typer(
    help="Cyclonext robot control commands.",
    no_args_is_help=True,
)
app.add_typer(robot_app, name="robot")


_ROBOT_CYCLE_CHOICES: dict[str, int] = {
    "floor": CYCLE_FLOOR,
    "floor-wall": CYCLE_FLOOR_AND_WALLS,
}


_ROBOT_SYSTEM_TYPES: tuple[type[AqualinkSystem], ...] = (
    CyclonextSystem,
    VrSystem,
    VortraxSystem,
    CyclobatSystem,
    I2dRobotSystem,
)


def _resolve_robot_system(
    systems: dict[str, AqualinkSystem],
    selector: str | None,
) -> AqualinkSystem:
    system = _resolve_system(systems, selector)
    if not isinstance(system, _ROBOT_SYSTEM_TYPES):
        _exit_with_error(
            f"System {system.serial!r} is not a supported robot.",
        )
    return system


def _resolve_cyclonext_system(
    systems: dict[str, AqualinkSystem],
    selector: str | None,
) -> CyclonextSystem:
    # Narrows further than _resolve_robot_system; returned type is
    # CyclonextSystem so callers get its full method surface from ty.
    system = _resolve_robot_system(systems, selector)
    if not isinstance(system, CyclonextSystem):
        _exit_with_error(
            f"System {system.serial!r} is not a cyclonext robot.",
        )
    return system


async def _robot_set_mode(
    credentials: Credentials,
    selector: str | None,
    cookie_jar: Path,
    action: str,
    cycle: int | None = None,
) -> str:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_cyclonext_system(systems, selector)
    if action == "start":
        await system.start_cleaning(cycle=cycle)
        suffix = (
            f" with cycle={CYCLE_LABELS.get(cycle, cycle)}"
            if cycle is not None
            else ""
        )
        return f"Started cleaning on {system.name} ({system.serial}){suffix}."
    if action == "stop":
        await system.stop_cleaning()
        return f"Stopped {system.name} ({system.serial})."
    if action == "pause":
        await system.pause_cleaning()
        return f"Paused {system.name} ({system.serial})."
    raise ValueError(f"unknown robot action: {action}")  # pragma: no cover


async def _robot_status(
    credentials: Credentials,
    selector: str | None,
    cookie_jar: Path,
) -> str:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_cyclonext_system(systems, selector)
    try:
        await system.update()
    except (
        AqualinkServiceException,
        AqualinkSystemOfflineException,
        AqualinkServiceUnauthorizedException,
        AqualinkServiceThrottledException,
    ) as exc:
        _exit_with_error(f"Could not refresh {system.serial}: {exc}")

    devices = system.devices
    mode_value = devices["mode"].state if "mode" in devices else "?"
    cycle_value = devices["cycle"].state if "cycle" in devices else "?"
    remaining = devices.get("time_remaining_sec")
    remaining_str = (
        "n/a" if remaining is None else _format_seconds(int(remaining.state))
    )

    try:
        mode_label = MODE_LABELS[int(mode_value)]
    except (KeyError, ValueError):
        mode_label = str(mode_value)
    try:
        cycle_label = CYCLE_LABELS[int(cycle_value)]
    except (KeyError, ValueError):
        cycle_label = str(cycle_value)

    lines = [
        f"{system.name} ({system.serial})",
        f"  mode      : {mode_label} ({mode_value})",
        f"  cycle     : {cycle_label} ({cycle_value})",
        f"  remaining : {remaining_str}",
    ]
    if "model_number" in devices:
        lines.append(f"  model     : {devices['model_number'].state}")
    if "totRunTime" in devices:
        total_min = int(devices["totRunTime"].state)
        lines.append(f"  total run : {total_min // 60}h {total_min % 60}m")
    return "\n".join(lines)


def _format_seconds(secs: int) -> str:
    if secs <= 0:
        return "0:00"
    minutes, seconds = divmod(secs, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _parse_cycle(value: str | None) -> int | None:
    if value is None:
        return None
    key = value.lower()
    if key not in _ROBOT_CYCLE_CHOICES:
        choices = ", ".join(sorted(_ROBOT_CYCLE_CHOICES))
        _exit_with_error(
            f"Unknown cycle {value!r}. Choose one of: {choices}.",
        )
    return _ROBOT_CYCLE_CHOICES[key]


@robot_app.command("start")
def robot_start(
    cycle: Annotated[
        str | None,
        typer.Option(
            "--cycle",
            help="Cycle preset to set before starting (floor or floor-wall).",
        ),
    ] = None,
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    cycle_id = _parse_cycle(cycle)
    typer.echo(
        _run_async(
            _robot_set_mode(credentials, system, cookie_jar, "start", cycle_id)
        )
    )


@robot_app.command(
    "stop",
    help=(
        "Stop the robot. Single canonical exit: stops a running cycle "
        "and also exits Remote or Lift mode (sends mode=0)."
    ),
)
def robot_stop(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(
        _run_async(_robot_set_mode(credentials, system, cookie_jar, "stop"))
    )


@robot_app.command("pause")
def robot_pause(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(
        _run_async(_robot_set_mode(credentials, system, cookie_jar, "pause"))
    )


@robot_app.command("status")
def robot_status(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    typer.echo(_run_async(_robot_status(credentials, system, cookie_jar)))


@robot_app.command("extend")
def robot_extend(
    minutes: Annotated[
        int,
        typer.Argument(
            help="Absolute runtime extension in minutes. Must be a "
            "non-negative multiple of 15. Use 0 to clear.",
        ),
    ],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)

    async def _run() -> str:
        systems = await _fetch_systems(credentials, cookie_jar)
        sys_obj = _resolve_cyclonext_system(systems, system)
        try:
            await sys_obj.set_runtime_extension(minutes)
        except AqualinkInvalidParameterException as exc:
            _exit_with_error(str(exc))
        return (
            f"Set runtime extension to {minutes} min on "
            f"{sys_obj.name} ({sys_obj.serial})."
        )

    typer.echo(_run_async(_run()))


@robot_app.command(
    "adjust-time",
    context_settings={"ignore_unknown_options": True},
)
def robot_adjust_time(
    delta: Annotated[
        str,
        typer.Argument(
            help='Delta minutes — pass as "+15" or "-15". Multiples of 15 only.',
        ),
    ],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    try:
        delta_min = int(delta.lstrip("+"))
    except ValueError:
        _exit_with_error(f"Invalid delta {delta!r}. Use e.g. +15 or -15.")

    async def _run() -> str:
        systems = await _fetch_systems(credentials, cookie_jar)
        sys_obj = _resolve_cyclonext_system(systems, system)
        try:
            await sys_obj.update()
        except AqualinkException as exc:
            _exit_with_error(f"Could not refresh {sys_obj.serial}: {exc}")
        try:
            new_value = await sys_obj.adjust_runtime(delta_min)
        except AqualinkInvalidParameterException as exc:
            _exit_with_error(str(exc))
        return (
            f"Adjusted runtime extension by {delta_min:+d} min "
            f"(now {new_value} min) on {sys_obj.name} ({sys_obj.serial})."
        )

    typer.echo(_run_async(_run()))


@robot_app.command("set-cycle")
def robot_set_cycle(
    cycle: Annotated[
        str,
        typer.Argument(help="Cycle preset (floor or floor-wall)."),
    ],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    cycle_id = _parse_cycle(cycle)
    assert cycle_id is not None  # _parse_cycle exits on invalid input

    async def _run() -> str:
        systems = await _fetch_systems(credentials, cookie_jar)
        sys_obj = _resolve_cyclonext_system(systems, system)
        await sys_obj.set_cycle(cycle_id)
        return (
            f"Set cycle to {CYCLE_LABELS.get(cycle_id, cycle_id)} "
            f"on {sys_obj.name} ({sys_obj.serial})."
        )

    typer.echo(_run_async(_run()))


_REMOTE_ACTIONS: dict[str, str] = {
    "forward": "remote_forward",
    "backward": "remote_backward",
    "left": "remote_rotate_left",
    "right": "remote_rotate_right",
    "stop": "remote_stop",
}

_LIFT_ACTIONS: dict[str, str] = {
    "eject": "lift_eject",
    "left": "lift_rotate_left",
    "right": "lift_rotate_right",
    "stop": "lift_stop",
}


@robot_app.command("remote")
def robot_remote(
    action: Annotated[
        str,
        typer.Argument(
            help="Direction: forward, backward, left, right, stop.",
        ),
    ],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    method_name = _REMOTE_ACTIONS.get(action.lower())
    if method_name is None:
        choices = ", ".join(sorted(_REMOTE_ACTIONS))
        _exit_with_error(
            f"Unknown remote action {action!r}. Choose: {choices}."
        )

    async def _run() -> str:
        systems = await _fetch_systems(credentials, cookie_jar)
        sys_obj = _resolve_cyclonext_system(systems, system)
        if not isinstance(sys_obj, CyclonextSystem):
            _exit_with_error(
                "Remote control is only available on cyclonext robots.",
            )
        await getattr(sys_obj, method_name)()
        return f"Sent remote {action} to {sys_obj.name} ({sys_obj.serial})."

    typer.echo(_run_async(_run()))


@robot_app.command("lift")
def robot_lift(
    action: Annotated[
        str,
        typer.Argument(
            help="Lift action: eject, left, right, stop.",
        ),
    ],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    method_name = _LIFT_ACTIONS.get(action.lower())
    if method_name is None:
        choices = ", ".join(sorted(_LIFT_ACTIONS))
        _exit_with_error(f"Unknown lift action {action!r}. Choose: {choices}.")

    async def _run() -> str:
        systems = await _fetch_systems(credentials, cookie_jar)
        sys_obj = _resolve_cyclonext_system(systems, system)
        if not isinstance(sys_obj, CyclonextSystem):
            _exit_with_error(
                "Lift system is only available on cyclonext robots.",
            )
        await getattr(sys_obj, method_name)()
        return f"Sent lift {action} to {sys_obj.name} ({sys_obj.serial})."

    typer.echo(_run_async(_run()))
