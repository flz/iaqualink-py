# 🏊 iaqualink-py

> Asynchronous Python library for Jandy iAqualink pool control systems

[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)

## 📖 Overview

**iaqualink-py** is a modern, fully asynchronous Python library for interacting with Jandy iAqualink pool and spa control systems. It provides a clean, Pythonic interface to monitor and control your pool equipment from your Python applications.

### ✨ Features

- 🔄 **Fully Asynchronous** - Built with `asyncio` and `httpx` for efficient, non-blocking I/O
- 🔐 **401 Replay for Auth-Bearing Requests** - Rebuilds and replays systems discovery and iaqua/exo system requests after auth refresh
- 🏗️ **Multi-System Support**
  - **iAqua** systems (iaqualink.net API)
  - **eXO** systems (zodiac-io.com API)
- 🌡️ **Comprehensive Device Support**
  - Temperature sensors (pool, spa, air)
  - Thermostats with adjustable set points
  - Pumps and heaters
  - Lights with toggle control
  - Auxiliary switches
  - Water chemistry sensors (pH, ORP, salinity)
  - Freeze protection monitoring
- 🔌 **Context Manager Support** - Automatic resource cleanup
- 🛡️ **Type Safe** - Full type hints for modern Python development

## 📦 Installation

```bash
pip install iaqualink
```

Or using [uv](https://github.com/astral-sh/uv):

```bash
uv add iaqualink
```

To install the optional CLI as well:

```bash
pip install 'iaqualink[cli]'
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add 'iaqualink[cli]'
```

## 💻 CLI

The optional `cli` extra installs an `iaqualink` command for common discovery and control tasks.

Credentials can be provided in this order:
- command-line options such as `--username` and `--password`
- environment variables `IAQUALINK_USERNAME` and `IAQUALINK_PASSWORD`
- a YAML config file, defaulting to `typer.get_app_dir("iaqualink") / "config.yaml"`

Example config:

```yaml
username: user@example.com
password: super-secret-password
```

Example commands:

```bash
# Enable verbose debug logging
iaqualink --debug list-systems

# List the systems on the account
iaqualink list-systems

# Show devices for a system
iaqualink list-devices --system YOUR-SERIAL

# Show a tree view of all systems and devices
iaqualink status

# Turn on a device by key or label
iaqualink turn-on pool_pump --system YOUR-SERIAL

# Change a thermostat set point
iaqualink set-temperature spa_set_point 102 --system YOUR-SERIAL
```

## Session Persistence

The CLI can persist login state across runs so repeated commands do not need to authenticate every time.

By default, session state is stored at `typer.get_app_dir("iaqualink") / "session.json"`, which resolves to an app-specific config directory on macOS, Linux, and Windows.

All commands accept `--cookie-jar` to override that location:

```bash
iaqualink list-systems --cookie-jar ~/.cache/iaqualink/session.json
```

Session lifecycle:

1. First run logs in normally and writes the current auth state to the jar.
2. Later runs restore that state when the saved username matches the requested username.
3. If a restored session is stale during systems discovery, the CLI reauthenticates and updates the jar automatically.

Security notes:

- The cookie jar stores authentication tokens in plain text.
- On shared systems, use a location with appropriate file permissions.
- If you change credentials or want to force a fresh login, delete the jar file.
- Use `--debug` on any command to enable verbose logging while troubleshooting CLI or API behavior.

## 🚀 Quick Start

### Basic Usage

```python
from iaqualink import AqualinkClient

async with AqualinkClient('user@example.com', 'password') as client:
    # Discover your pool systems
    systems = await client.get_systems()

    # Get the first system
    system = list(systems.values())[0]
    print(f"Found system: {system.name}")

    # Get all devices
    devices = await system.get_devices()

    # Access specific devices
    pool_temp = devices.get('pool_temp')
    if pool_temp:
        print(f"Pool temperature: {pool_temp.state}°F")

    spa_heater = devices.get('spa_heater')
    if spa_heater:
        print(f"Spa heater: {'ON' if spa_heater.is_on else 'OFF'}")
```

### Controlling Devices

```python
# Turn on pool pump
pool_pump = devices.get('pool_pump')
if pool_pump:
    await pool_pump.turn_on()

# Set spa temperature
spa_thermostat = devices.get('spa_set_point')
if spa_thermostat:
    await spa_thermostat.set_temperature(102)

# Toggle pool light
pool_light = devices.get('aux_3')
if pool_light:
    await pool_light.toggle()
```

### Monitoring System Status

```python
# Update system state
await system.update()

# Check if system is online
if system.online:
    print(f"System {system.name} is online")

    # Get all temperature readings
    for device_name, device in devices.items():
        if 'temp' in device_name and device.state:
            print(f"{device.label}: {device.state}°")
```

## 🔧 Advanced Usage

### Working with Multiple Systems

```python
async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()

    for serial, system in systems.items():
        print(f"System: {system.name} ({serial})")
        print(f"Type: {system.data.get('device_type')}")

        devices = await system.get_devices()
        print(f"Devices: {len(devices)}")
```

## 🏗️ Architecture

The library uses a plugin-style architecture with base classes and system-specific implementations:

- **AqualinkClient** - Authentication and system discovery
- **AqualinkSystem** - Base class with iAqua and eXO implementations
- **AqualinkDevice** - Device hierarchy with type-specific subclasses

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

## 🧪 Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/flz/iaqualink-py.git
cd iaqualink-py

# Install dependencies
uv sync --group dev --group test
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov-report=xml --cov=iaqualink

# Run specific test file
uv run pytest tests/test_client.py

# Run CLI tests
uv run pytest tests/test_cli.py
```

### Code Quality

```bash
# Run all pre-commit hooks (ruff, mypy)
uv run pre-commit run --all-files

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type checking
uv run mypy src/
```

## 📋 Requirements

- Python 3.14 or higher
- httpx with HTTP/2 support

## 📄 License

This project is licensed under the BSD 3-Clause License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🔗 Links

- **Homepage**: https://github.com/flz/iaqualink-py
- **Issues**: https://github.com/flz/iaqualink-py/issues

## ⚠️ Disclaimer

This is an unofficial library and is not affiliated with or endorsed by Jandy, Zodiac Pool Systems, or Fluidra. Use at your own risk.

---

Made with ❤️ by [Florent Thoumie](https://github.com/flz)
