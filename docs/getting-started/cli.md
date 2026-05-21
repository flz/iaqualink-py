# CLI Reference

The `iaqualink` command-line client lets you inspect and control your pool systems without writing Python code. It is also useful for scripting and automation.

## Installation

The CLI requires optional dependencies. Install them with the `cli` extra:

```bash
pip install "iaqualink[cli]"
```

## Configuration

Credentials can be supplied in three ways (highest priority first):

| Method | How |
|---|---|
| CLI flags | `--username USER --password PASS` |
| Environment variables | `IAQUALINK_USERNAME`, `IAQUALINK_PASSWORD` |
| Config file | `~/.config/iaqualink/config.yaml` |

Config file format:

```yaml
username: user@example.com
password: your_password
```

The config file and session jar are stored in `~/.config/iaqualink/` on Linux/macOS and in the platform app-data directory on Windows.

## Session Management

After the first successful login the session token is saved to `~/.config/iaqualink/session.json`. Subsequent commands reuse it without reauthenticating. The session is refreshed automatically if it has expired.

To force a fresh login:

```bash
iaqualink logout
```

To use a custom session file location:

```bash
iaqualink --cookie-jar /path/to/session.json status
```

## Global Flags

These flags apply to every command and must be placed before the command name:

| Flag | Description |
|---|---|
| `--debug` | Enable debug logging to stderr |
| `--version` | Show the installed version and exit |
| `--capture FILE` | Write all HTTP traffic (redacted) to a JSONL file |

```bash
iaqualink --debug status
iaqualink --capture traffic.jsonl status
```

## Commands

### `list-systems`

List all systems on the account.

```bash
iaqualink list-systems
```

Output:

```
● My Pool (ABC123456) [iaqua] online
● Spa Controller (XYZ789) [exo] online
```

---

### `list-devices`

List all devices for a system, grouped by type.

```bash
iaqualink list-devices
iaqualink list-devices --system ABC123456
```

---

### `status`

Show system status with current device states. Without `--system`, shows all systems.

```bash
iaqualink status
iaqualink status --system ABC123456
```

Output:

```
Systems
└── ● My Pool (ABC123456) [iaqua] online
    ├── 🌡️ Climate
    │   └── Pool Heater [pool_heater]: 78°F → 82°F (on)
    ├── 💡 Lights
    │   └── Pool Light [aux_3]: on
    ├── ⚡ Switches
    │   └── Spa Jets [aux_1]: off
    └── 📊 Sensors
        └── Pool Temp [pool_temp]: 78°F
```

---

### `get`

Print the current state of a single device. Useful for scripting.

```bash
iaqualink get pool_temp
iaqualink get "Pool Temp"
```

Devices can be identified by key (e.g., `pool_temp`) or label (e.g., `Pool Temp`). Labels are matched case-insensitively.

---

### `turn-on` / `turn-off`

Turn a device on or off. Works with switches, lights, climate zones, and fans/pumps.

```bash
iaqualink turn-on aux_1
iaqualink turn-off "Pool Light"
iaqualink turn-on pool_heater --system ABC123456
```

---

### `set-temperature`

Set the target temperature on a climate zone (heater/chiller).

```bash
iaqualink set-temperature pool_heater 82
iaqualink set-temperature spa_heater 104
```

The unit (°F or °C) matches the system configuration.

---

### `set-brightness`

Set the brightness of a dimmable light (0–100%).

```bash
iaqualink set-brightness aux_3 75
```

Returns an error if the light does not support brightness control.

---

### `set-effect`

Set the color effect on a color light.

```bash
iaqualink set-effect aux_3 "Alpine White"
iaqualink set-effect aux_3 "Voodoo Lounge"
```

Use `status` to see the current effect. Available effects depend on the light model.

---

### `set-speed`

Set the speed of a fan/pump as a percentage (0–100%).

```bash
iaqualink set-speed pump 65
```

Returns an error if the device does not support speed control.

---

### `set-preset`

Set a named preset mode on a fan/pump.

```bash
iaqualink set-preset pump SCHEDULE
iaqualink set-preset pump CUSTOM
iaqualink set-preset pump STOP
```

Available presets depend on the device. Use `status` to see the current preset.

---

### `set-value`

Set a numeric value on a Number device.

```bash
iaqualink set-value target_chlorine 3.0
```

The command validates the value against the device's configured minimum, maximum, and step.

---

### `logout`

Remove the saved session and force fresh authentication on the next command.

```bash
iaqualink logout
```

## Device Type Reference

The table below shows which commands apply to each device type.

| Device type | `get` | `turn-on/off` | `set-temperature` | `set-brightness` | `set-effect` | `set-speed` | `set-preset` | `set-value` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Sensor | ✓ | — | — | — | — | — | — | — |
| Binary Sensor | ✓ | — | — | — | — | — | — | — |
| Switch | ✓ | ✓ | — | — | — | — | — | — |
| Light | ✓ | ✓ | — | ✓ (if supported) | ✓ (if supported) | — | — | — |
| Climate | ✓ | ✓ | ✓ | — | — | — | — | — |
| Number | ✓ | — | — | — | — | — | — | ✓ |
| Fan / Pump | ✓ | ✓ (if supported) | — | — | — | ✓ (if supported) | ✓ (if supported) | — |

## Multiple Systems

If your account has more than one system you must specify which one to use with `--system`. The value can be the serial number or the system name:

```bash
iaqualink status --system ABC123456
iaqualink turn-on pool_light --system "My Pool"
```

Without `--system`, commands that operate on a single device will error if multiple systems are found.
