# Cyclobat Systems API

Cyclobat systems are Zodiac battery-powered robot cleaners using the zodiac-io.com API with AWS IoT-style shadow state and a WebSocket write path.

## CyclobatSystem

::: iaqualink.systems.cyclobat.system.CyclobatSystem

## CyclobatDevice

::: iaqualink.systems.cyclobat.device.CyclobatDevice

## CyclobatSensor

::: iaqualink.systems.cyclobat.device.CyclobatSensor

## CyclobatBinarySensor

::: iaqualink.systems.cyclobat.device.CyclobatBinarySensor

## API Overview

- **Reads** — `system.refresh()` fetches the robot shadow (`GET /devices/v1/{serial}/shadow`) and updates all devices atomically.
- **Writes** — Three high-level commands send a WebSocket frame to `wss://prod-socket.zodiac-io.com/devices`.

## System Status

| `SystemStatus` | Meaning |
|---|---|
| `ONLINE` | Shadow fetched and `equipment.robot` present |
| `OFFLINE` | Shadow reachable but `equipment.robot` absent or malformed |
| `DISCONNECTED` | Network or HTTP error (non-401, non-429) |
| `UNKNOWN` | HTTP 429 throttle response |

## Device Inventory

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

## Write Commands

```python
# Start a cleaning cycle
await system.start_cleaning()   # sends ctrl=1

# Stop cleaning
await system.stop_cleaning()    # sends ctrl=0

# Return the robot to its base/dock
await system.return_to_base()   # sends ctrl=3
```

## Usage Example

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

## See Also

- [Implementation Notes](../../implementation/systems/cyclobat.md)
- [Protocol Reference](../../reference/systems/cyclobat.md)
