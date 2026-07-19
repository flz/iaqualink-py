# Quick Start

This guide will help you get started with iaqualink-py quickly.

## Basic Usage

### Connecting to Your System

```python
from iaqualink import AqualinkClient

async with AqualinkClient('user@example.com', 'password') as client:
    # Discover your pool systems
    systems = await client.get_systems()

    # Get the first system
    system = list(systems.values())[0]
    print(f"Found system: {system.name}")
```

### Getting Devices

```python
from iaqualink.device import AqualinkSensor, AqualinkSwitch

# Get all devices for a system
devices = await system.get_devices()

# Access specific devices
pool_temp = devices.get('pool_temp')
if isinstance(pool_temp, AqualinkSensor):
    print(f"Pool temperature: {pool_temp.value}°F")

spa_heater = devices.get('spa_heater')
if isinstance(spa_heater, AqualinkSwitch):
    print(f"Spa heater: {'ON' if spa_heater.is_on else 'OFF'}")
```

### Controlling Devices

#### Switches and Pumps

```python
# Turn on pool pump
pool_pump = devices.get('pool_pump')
if pool_pump:
    await pool_pump.turn_on()

# Turn off spa heater
spa_heater = devices.get('spa_heater')
if spa_heater:
    await spa_heater.turn_off()
```

#### Lights

```python
from iaqualink.device import AqualinkLight

pool_light = devices.get('aux_3')
if isinstance(pool_light, AqualinkLight):
    await pool_light.turn_on()
```

#### Thermostats

```python
from iaqualink.device import AqualinkClimate

# Set spa temperature
spa_heater = devices.get('spa_set_point')
if isinstance(spa_heater, AqualinkClimate):
    await spa_heater.set_temperature(102)

# Set pool temperature
pool_heater = devices.get('pool_set_point')
if isinstance(pool_heater, AqualinkClimate):
    await pool_heater.set_temperature(82)
```

### Monitoring System Status

```python
# Check if system is online
from iaqualink import AqualinkSensor, SystemStatus

# Refresh system state
await system.refresh()

# Check if system is online
if system.status is SystemStatus.ONLINE:
    print(f"System {system.name} is online")

    # Get all temperature readings
    for device_name, device in devices.items():
        if isinstance(device, AqualinkSensor) and device.value:
            print(f"{device.label}: {device.value}")
```

## Working with Multiple Systems

If you have multiple pool systems:

```python
async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()

    for serial, system in systems.items():
        print(f"System: {system.name} ({serial})")
        print(f"Type: {system.data.get('device_type')}")

        devices = await system.get_devices()
        print(f"Devices: {len(devices)}")
```

## Error Handling

```python
from iaqualink import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

try:
    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()
except AqualinkServiceUnauthorizedException:
    print("Invalid credentials")
except AqualinkServiceException as e:
    print(f"Service error: {e}")
```

## Cyclobat — Battery-Powered Robot Cleaners

Cyclobat systems (`device_type: "cyclobat"`) represent Zodiac battery-powered robot cleaners. They expose read-only sensors from an HTTP shadow poll and accept start/stop/return-to-base commands over WebSocket.

### API Overview

- **Reads** — `system.refresh()` fetches the robot shadow (`GET /devices/v1/{serial}/shadow`) and updates all devices atomically.
- **Writes** — Three high-level commands send a WebSocket frame to `wss://prod-socket.zodiac-io.com/devices`.

### System Status

| `SystemStatus` | Meaning |
|---|---|
| `ONLINE` | Shadow fetched and `equipment.robot` present |
| `OFFLINE` | Shadow reachable but `equipment.robot` absent or malformed |
| `DISCONNECTED` | Network or HTTP error (non-401, non-429) |
| `UNKNOWN` | HTTP 429 throttle response |

### Device Inventory

All keys are read-only `CyclobatSensor` unless noted.

| Device key | Description |
|---|---|
| `main_state` | Current robot state (integer: 0=stopped, 1=cleaning, 3=returning) |
| `main_ctrl` | Write target — same encoding as `main_state` |
| `main_mode` | Cleaning mode code |
| `main_error` | Error code (0 = none) |
| `main_cycleStartTime` | Unix timestamp when current cycle started |
| `battery_state` | Battery state code |
| `battery_percentage` | Charge percentage (0–100) |
| `battery_charge_state` | Charge state code |
| `battery_cycles` | Total charge cycle count |
| `battery_warning_code` | Battery warning code (0 = none) |
| `battery_version` | Battery firmware version |
| `total_runtime` | Lifetime total run time (minutes) |
| `diagnostic_code` | Diagnostic code |
| `temperature` | Robot temperature reading |
| `last_error_code` | Last recorded error code |
| `last_error_cycle` | Cycle number of last error |
| `last_cycle_number` | Most recent completed cycle count |
| `last_cycle_duration` | Duration of most recent cycle (minutes) |
| `last_cycle_mode` | Mode used in most recent cycle |
| `cycle` | End-cycle type index of most recent cycle (0–3) |
| `last_cycle_error` | Error code at end of most recent cycle |
| `floor_duration` | Floor-only cycle duration (minutes) |
| `floor_walls_duration` | Floor + walls cycle duration (minutes) |
| `smart_duration` | Smart cycle duration (minutes) |
| `waterline_duration` | Waterline cycle duration (minutes) |
| `first_smart_done` | Whether first smart cycle has completed |
| `lift_pattern_time` | Lift pattern timing value |
| `vr` | Robot firmware version |
| `sn` | Serial number |
| `model_number` | Model number string |
| `running` | **BinarySensor** — `True` when `main_state == 1` (cleaning) |
| `returning` | **BinarySensor** — `True` when `main_state == 3` (returning) |
| `time_remaining_sec` | Estimated seconds remaining in current cycle (derived) |

### Write Commands

```python
# Start a cleaning cycle
await system.start_cleaning()   # sends ctrl=1

# Stop cleaning
await system.stop_cleaning()    # sends ctrl=0

# Return the robot to its base/dock
await system.return_to_base()   # sends ctrl=3
```

### Full Example

```python
from iaqualink import AqualinkClient
from iaqualink.system import SystemStatus

async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()

    for system in systems.values():
        if system.data.get('device_type') == 'cyclobat':
            await system.refresh()

            if system.status is SystemStatus.ONLINE:
                devices = await system.get_devices()

                running = devices.get('running')
                pct = devices.get('battery_percentage')
                print(f"Running: {running.is_on}, Battery: {pct.value}%")

                # Start cleaning
                await system.start_cleaning()
```

## Working with Polaris iqPump Robot Cleaners (i2d_robot)

Polaris iqPump robot cleaners use a hex-encoded HTTP protocol. After connecting
you can read sensor values and send control commands:

```python
from iaqualink import AqualinkClient
from iaqualink.systems.i2d_robot.system import I2dRobotSystem

async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()

    # Find an i2d_robot system
    robot = next(
        (s for s in systems.values() if isinstance(s, I2dRobotSystem)),
        None,
    )
    if robot is None:
        print("No Polaris robot found")
    else:
        devices = await robot.get_devices()

        # Read state
        print(f"State: {devices['state'].value}")
        print(f"Error: {devices['error'].value}")
        print(f"Mode: {devices['mode'].value}")
        print(f"Time remaining: {devices['time_remaining_min'].value} min")
        print(f"Running: {devices['running'].is_on}")
        print(f"Canister full: {devices['canister_full'].is_on}")

        # Send control commands
        await robot.start_cleaning()
        await robot.stop_cleaning()
        await robot.return_to_base()
```

## Next Steps

- [CLI Reference](cli.md) — command-line client for scripting and quick control
- [API Reference](../api/client.md) — `AqualinkClient` class reference
- [Architecture](../contributing/architecture.md) — system/device hierarchy and data flow
- [Protocol Reference](../reference/client.md) — wire-level auth and endpoint details
