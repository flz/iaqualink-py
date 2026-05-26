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
from rich.console import Console
from rich.text import Text
from rich.tree import Tree

from iaqualink.cli.capture import CaptureSession
from iaqualink.client import AqualinkAuthState, AqualinkClient
from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkClimate,
    AqualinkDevice,
    AqualinkFan,
    AqualinkLight,
    AqualinkNumber,
    AqualinkRobot,
    AqualinkSensor,
    AqualinkSwitch,
)
from iaqualink.exception import (
    AqualinkException,
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclobat.system import CyclobatSystem
from iaqualink.systems.cyclonext.const import (
    CYCLE_FLOOR,
    CYCLE_FLOOR_AND_WALLS,
    CYCLE_LABELS,
    MODE_LABELS,
)
from iaqualink.systems.cyclonext.system import CyclonextSystem
from iaqualink.systems.vortrax.system import VortraxSystem
from iaqualink.systems.vr.system import VrSystem
from iaqualink.version import __version__

_console = Console()
_error_console = Console(stderr=True, soft_wrap=True)

app = typer.Typer(
    add_completion=False,
    help="Command line client for Jandy iAqualink systems.",
    no_args_is_help=True,
)

LOGGER = logging.getLogger("iaqualink.cli")
DEBUG_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
DEBUG_HANDLER_NAME = "iaqualink.cli.debug"

_capture_session: CaptureSession | None = None

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
    _error_console.print(f"[bold red]Error:[/bold red] {message}")
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
        event_hooks=_capture_session.make_hooks() if _capture_session else None,
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

        if _capture_session is not None:
            _capture_session.register_serials(*systems.keys())
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


# IMPORTANT: Every concrete AqualinkDevice subclass in device.py must have a
# matching entry here so devices never silently fall through to "Other".
# When adding a new base device type, add its entry to this list.
_DEVICE_GROUPS: list[tuple[type[AqualinkDevice], str, str]] = [
    (AqualinkClimate, "🌡️", "Climate"),
    (AqualinkLight, "💡", "Lights"),
    (AqualinkSwitch, "⚡", "Switches"),
    (AqualinkFan, "⚙️", "Fans"),
    (AqualinkRobot, "🤖", "Vacuums"),
    (AqualinkNumber, "🔢", "Numbers"),
    (AqualinkBinarySensor, "📊", "Sensors"),
    (AqualinkSensor, "📊", "Sensors"),
]


_STATUS_DOT = "●"

_STATUS_DOT_STYLE: dict[SystemStatus, str] = {
    SystemStatus.CONNECTED: "bold green",
    SystemStatus.ONLINE: "bold green",
    SystemStatus.DISCONNECTED: "bold red",
    SystemStatus.OFFLINE: "bold red",
    SystemStatus.UNKNOWN: "bold red",
    SystemStatus.SERVICE: "bold yellow",
    SystemStatus.FIRMWARE_UPDATE: "bold yellow",
    SystemStatus.IN_PROGRESS: "dim",
}


def _format_system_line(system: AqualinkSystem) -> Text:
    t = Text()
    dot_style = _STATUS_DOT_STYLE[system.status]
    t.append(f"{_STATUS_DOT} ", style=dot_style)
    t.append(system.name, style="bold")
    t.append(f" ({system.serial})", style="dim")
    t.append(f" [{system.data.get('device_type', 'unknown')}]", style="cyan")
    t.append(f" {system.status_translated}", style=dot_style)
    if not system.supported:
        t.append(" (unsupported)", style="bold red")
    return t


def _format_device_line(device_name: str, device: AqualinkDevice) -> Text:
    if isinstance(device, AqualinkSensor):
        state_str: str | None = device.value
        translated: str | None = device.value_translated
    elif isinstance(device, AqualinkFan):
        parts: list[str] = []
        if device.supports_presets and device.preset_mode:
            parts.append(device.preset_mode)
        if device.supports_percentage:
            pct = device.percentage
            if pct is not None:
                parts.append(f"{pct}%")
        if not parts:
            if device.supports_turn_on or device.supports_turn_off:
                parts.append("on" if device.is_on else "off")
        state_str = " / ".join(parts) if parts else None
        translated = None
    elif isinstance(device, AqualinkClimate):
        if device.is_on:
            cur = device.current_temperature
            tgt = device.target_temperature
            unit = f"°{device.temperature_unit}"
            if cur is not None and tgt is not None:
                state_str = f"{cur}{unit} → {tgt}{unit} (on)"
            elif cur is not None:
                state_str = f"{cur}{unit} (on)"
            else:
                state_str = "on"
        else:
            state_str = "off"
        translated = None
    elif isinstance(
        device,
        (AqualinkSwitch, AqualinkBinarySensor, AqualinkLight),
    ):
        state_str = "on" if device.is_on else "off"
        translated = None
    elif isinstance(device, AqualinkNumber):
        cv = device.current_value
        if cv is not None:
            unit = device.unit_of_measurement
            state_str = f"{cv:g} {unit}" if unit else f"{cv:g}"
        else:
            state_str = None
        translated = None
    else:
        state_str = None
        translated = None

    if not state_str:
        t = Text()
        t.append(device.label, style="bold dim")
        t.append(f" [{device_name}]", style="dim")
        return t
    t = Text()
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    t.append(": ")
    t.append(state_str, style="yellow")
    if translated is not None:
        t.append(f" ({translated})", style="yellow")
    return t


def _group_devices(
    devices: list[tuple[str, AqualinkDevice]],
) -> list[tuple[str, str, list[tuple[str, AqualinkDevice]]]]:
    assigned: set[str] = set()
    # label → (icon, members) — preserves insertion order, merges same-label entries
    groups: dict[str, tuple[str, list[tuple[str, AqualinkDevice]]]] = {}
    for cls, icon, label in _DEVICE_GROUPS:
        members = [
            (name, dev)
            for name, dev in devices
            if isinstance(dev, cls) and name not in assigned
        ]
        for name, _ in members:
            assigned.add(name)
        if members:
            if label in groups:
                groups[label][1].extend(members)
            else:
                groups[label] = (icon, members)
    result = [
        (icon, label, members) for label, (icon, members) in groups.items()
    ]
    remaining = [(name, dev) for name, dev in devices if name not in assigned]
    if remaining:
        result.append(("•", "Other", remaining))
    return result


def _add_devices_to_tree(
    branch: Tree,
    serial: str,
    system: AqualinkSystem,
    devices_by_system: dict[str, dict[str, AqualinkDevice]],
) -> None:
    devices = _sorted_devices(devices_by_system.get(serial, {}))
    if not devices:
        msg = (
            "System type not supported"
            if not system.supported
            else "No devices found"
        )
        branch.add(Text(msg, style="dim"))
        return
    for icon, label, members in _group_devices(devices):
        group_label = Text()
        group_label.append(f"{icon} {label}", style="bold")
        group_branch = branch.add(group_label)
        for device_name, device in members:
            group_branch.add(_format_device_line(device_name, device))


def _render_device_tree(
    systems: list[tuple[str, AqualinkSystem]],
    devices_by_system: dict[str, dict[str, AqualinkDevice]],
) -> Tree:
    root = Tree(Text("Systems", style="bold"))
    if not systems:
        root.add(Text("No systems found", style="dim"))
        return root
    for serial, system in systems:
        branch = root.add(_format_system_line(system))
        _add_devices_to_tree(branch, serial, system, devices_by_system)
    return root


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
) -> list[Text]:
    systems = await _fetch_systems(credentials, cookie_jar)
    return [
        _format_system_line(system) for _, system in _sorted_systems(systems)
    ]


async def _list_devices(
    credentials: Credentials,
    system_selector: str | None,
    cookie_jar: Path,
) -> Tree:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    return _render_device_tree(
        [(system.serial, system)], {system.serial: devices}
    )


async def _status(
    credentials: Credentials,
    system_selector: str | None,
    cookie_jar: Path,
) -> Tree:
    systems = await _fetch_systems(credentials, cookie_jar)
    if system_selector is not None:
        system = _resolve_system(systems, system_selector)
        selected_systems = [(system.serial, system)]
    else:
        selected_systems = _sorted_systems(systems)

    devices_by_system: dict[str, dict[str, AqualinkDevice]] = {}
    for serial, system in selected_systems:
        devices_by_system[serial] = await _load_devices_for_system(system)

    if selected_systems:
        _, any_system = selected_systems[0]
        _save_session_jar(cookie_jar, any_system.aqualink.auth_state)
    return _render_device_tree(selected_systems, devices_by_system)


async def _run_switch_command(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    target_state: str,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if isinstance(device, (AqualinkSwitch, AqualinkLight, AqualinkClimate)):
        if target_state == "on":
            await device.turn_on()
        else:
            await device.turn_off()
    elif isinstance(device, AqualinkFan):
        if target_state == "on":
            if not device.supports_turn_on:
                _exit_with_error(
                    f"Fan {device_name!r} does not support turn on.",
                )
            await device.turn_on()
        else:
            if not device.supports_turn_off:
                _exit_with_error(
                    f"Fan {device_name!r} does not support turn off.",
                )
            await device.turn_off()
    else:
        _exit_with_error(
            f"Device {device_name!r} does not support power controls.",
        )

    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    t = Text()
    t.append("✓ ", style="bold green")
    t.append(f"Sent {target_state} command to ")
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    t.append(" on ")
    t.append_text(_format_system_line(system))
    return t


async def _set_pump_speed(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    percentage: int,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkFan):
        _exit_with_error(f"Device {device_name!r} is not a fan/pump.")

    if not device.supports_percentage:
        _exit_with_error(
            f"Fan {device_name!r} does not support speed control.",
        )

    await device.set_percentage(percentage)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    t = Text()
    t.append("✓ ", style="bold green")
    t.append("Set speed of ")
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    t.append(f" to {percentage}% on ")
    t.append_text(_format_system_line(system))
    return t


async def _set_pump_preset(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    preset: str,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkFan):
        _exit_with_error(f"Device {device_name!r} is not a fan/pump.")

    if not device.supports_presets:
        _exit_with_error(
            f"Fan {device_name!r} does not support presets.",
        )

    await device.set_preset_mode(preset)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    t = Text()
    t.append("✓ ", style="bold green")
    t.append("Set preset of ")
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    t.append(f" to {preset!r} on ")
    t.append_text(_format_system_line(system))
    return t


async def _set_number_value(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    value: float,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkNumber):
        _exit_with_error(
            f"Device {device_name!r} does not support numeric values.",
        )

    await device.set_value(value)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    t = Text()
    t.append("✓ ", style="bold green")
    t.append("Set ")
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    unit = device.unit_of_measurement
    value_str = f" to {value:g} {unit}" if unit else f" to {value:g}"
    t.append(f"{value_str} on ")
    t.append_text(_format_system_line(system))
    return t


async def _set_temperature(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    temperature: int,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkClimate):
        _exit_with_error(
            f"Device {device_name!r} does not support temperature changes.",
        )

    await device.set_temperature(temperature)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    t = Text()
    t.append("✓ ", style="bold green")
    t.append("Set ")
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    t.append(f" to {temperature}°{device.temperature_unit} on ")
    t.append_text(_format_system_line(system))
    return t


async def _set_brightness(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    brightness: int,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkLight):
        _exit_with_error(
            f"Device {device_name!r} is not a light.",
        )

    if not device.supports_brightness:
        _exit_with_error(
            f"Device {device_name!r} does not support brightness control.",
        )

    await device.set_brightness_percentage(brightness)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    t = Text()
    t.append("✓ ", style="bold green")
    t.append("Set brightness of ")
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    t.append(f" to {brightness}% on ")
    t.append_text(_format_system_line(system))
    return t


async def _set_effect(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    effect: str,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)

    if not isinstance(device, AqualinkLight):
        _exit_with_error(
            f"Device {device_name!r} is not a light.",
        )

    if not device.supports_effect:
        _exit_with_error(
            f"Device {device_name!r} does not support color effects.",
        )

    await device.set_effect(effect)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    t = Text()
    t.append("✓ ", style="bold green")
    t.append("Set effect of ")
    t.append(device.label, style="bold")
    t.append(f" [{device_name}]", style="dim")
    t.append(f" to {effect!r} on ")
    t.append_text(_format_system_line(system))
    return t


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
    capture: Annotated[
        Path | None,
        typer.Option(
            "--capture",
            help=(
                "Write all HTTP requests/responses to a JSONL file (sensitive "
                "values redacted). Useful for reviewing traffic or building "
                "regression fixtures."
            ),
            writable=True,
        ),
    ] = None,
) -> None:
    global _capture_session
    _configure_logging(debug)

    if capture is not None:
        _capture_session = CaptureSession(path=capture)

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
        _console.print(line)


@app.command("list-devices")
def list_devices(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    _console.print(_run_async(_list_devices(credentials, system, cookie_jar)))


@app.command()
def status(
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    _console.print(_run_async(_status(credentials, system, cookie_jar)))


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
    _console.print(
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
    _console.print(
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
    _console.print(
        _run_async(
            _set_temperature(
                credentials, system, device, temperature, cookie_jar
            )
        )
    )


@app.command("set-brightness")
def set_brightness(
    device: DeviceArgument,
    brightness: Annotated[
        int,
        typer.Argument(help="Brightness percentage (0-100).", min=0, max=100),
    ],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    _console.print(
        _run_async(
            _set_brightness(credentials, system, device, brightness, cookie_jar)
        )
    )


@app.command("set-effect")
def set_effect(
    device: DeviceArgument,
    effect: Annotated[str, typer.Argument(help="Effect name.")],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    _console.print(
        _run_async(_set_effect(credentials, system, device, effect, cookie_jar))
    )


@app.command("set-speed")
def set_speed(
    device: DeviceArgument,
    percentage: Annotated[
        int,
        typer.Argument(help="Pump speed percentage (0-100).", min=0, max=100),
    ],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    _console.print(
        _run_async(
            _set_pump_speed(credentials, system, device, percentage, cookie_jar)
        )
    )


@app.command("set-preset")
def set_preset(
    device: DeviceArgument,
    preset: Annotated[str, typer.Argument(help="Pump preset name.")],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    _console.print(
        _run_async(
            _set_pump_preset(credentials, system, device, preset, cookie_jar)
        )
    )


@app.command("set-value")
def set_value(
    device: DeviceArgument,
    value: Annotated[float, typer.Argument(help="Numeric value to set.")],
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    credentials = _resolve_credentials(username, password, config)
    _console.print(
        _run_async(
            _set_number_value(credentials, system, device, value, cookie_jar)
        )
    )


async def _get_device_state(
    credentials: Credentials,
    system_selector: str | None,
    device_selector: str,
    cookie_jar: Path,
) -> Text:
    systems = await _fetch_systems(credentials, cookie_jar)
    system = _resolve_system(systems, system_selector)
    devices = await _load_devices_for_system(system)
    device_name, device = _resolve_device(devices, device_selector)
    _save_session_jar(cookie_jar, system.aqualink.auth_state)
    return _format_device_line(device_name, device)


@app.command("get")
def get(
    device: DeviceArgument,
    username: UsernameOption = None,
    password: PasswordOption = None,
    config: ConfigOption = DEFAULT_CONFIG_PATH,
    system: SystemOption = None,
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    """Print the current state of a single device."""
    credentials = _resolve_credentials(username, password, config)
    _console.print(
        _run_async(_get_device_state(credentials, system, device, cookie_jar))
    )


@app.command("logout")
def logout(
    cookie_jar: CookieJarOption = DEFAULT_COOKIE_JAR,
) -> None:
    """Remove the saved session cookie jar and force fresh authentication."""
    if cookie_jar.exists():
        cookie_jar.unlink()
        _console.print(
            f"[bold green]✓[/bold green] Removed session jar {cookie_jar}"
        )
    else:
        _console.print(f"[dim]No session jar found at {cookie_jar}[/dim]")


# ---------------------------------------------------------------------------
# Robot subcommand group
# (cyclobat / cyclonext / vortrax / vr — i2d_robot deferred to follow-up PR)
# ---------------------------------------------------------------------------

robot_app = typer.Typer(
    help="Robot pool cleaner control commands.",
    no_args_is_help=True,
)
app.add_typer(robot_app, name="robot")


_ROBOT_CYCLE_CHOICES: dict[str, int] = {
    "floor": CYCLE_FLOOR,
    "floor-wall": CYCLE_FLOOR_AND_WALLS,
}

# i2d_robot is intentionally excluded — its write API differs and CLI hookup
# is deferred until PR #233 merges.
_ROBOT_SYSTEM_TYPES: tuple[type[AqualinkSystem], ...] = (
    CyclonextSystem,
    VrSystem,
    VortraxSystem,
    CyclobatSystem,
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
    system = _resolve_robot_system(systems, selector)
    if not isinstance(system, CyclonextSystem):
        _exit_with_error(
            f"System {system.serial!r} is not a cyclonext robot.",
        )
    return system


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
        await system.refresh()
    except (
        AqualinkServiceException,
        AqualinkServiceUnauthorizedException,
        AqualinkServiceThrottledException,
    ) as exc:
        _exit_with_error(f"Could not refresh {system.serial}: {exc}")

    devices = system.devices
    mode_value = devices["mode"].value if "mode" in devices else "?"
    cycle_value = devices["cycle"].value if "cycle" in devices else "?"
    remaining = devices.get("time_remaining_sec")
    remaining_str = (
        "n/a" if remaining is None else _format_seconds(int(remaining.value))
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
        f"  status    : {system.status.name}",
        f"  mode      : {mode_label} ({mode_value})",
        f"  cycle     : {cycle_label} ({cycle_value})",
        f"  remaining : {remaining_str}",
    ]
    if "model_number" in devices:
        lines.append(f"  model     : {devices['model_number'].value}")
    if "totRunTime" in devices:
        total_min = int(devices["totRunTime"].value)
        lines.append(f"  total run : {total_min // 60}h {total_min % 60}m")
    return "\n".join(lines)


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
            help=(
                "Absolute runtime extension in minutes. Must be a "
                "non-negative multiple of 15. Use 0 to clear."
            ),
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
            await sys_obj.refresh()
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
        await getattr(sys_obj, method_name)()
        return f"Sent lift {action} to {sys_obj.name} ({sys_obj.serial})."

    typer.echo(_run_async(_run()))
