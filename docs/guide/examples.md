# Examples

Complete examples demonstrating common use cases.

## Basic Monitoring

Monitor pool and spa temperatures:

```python
import asyncio
from iaqualink import AqualinkClient

async def monitor_temperatures():
    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()
        system = list(systems.values())[0]

        while True:
            devices = await system.get_devices()

            pool_temp = devices.get('pool_temp')
            spa_temp = devices.get('spa_temp')
            air_temp = devices.get('air_temp')

            print(f"\nTemperatures:")
            if pool_temp:
                print(f"  Pool: {pool_temp.state}°{pool_temp.unit}")
            if spa_temp:
                print(f"  Spa: {spa_temp.state}°{spa_temp.unit}")
            if air_temp:
                print(f"  Air: {air_temp.state}°{air_temp.unit}")

            # Wait 5 seconds before next update
            await asyncio.sleep(5)

asyncio.run(monitor_temperatures())
```

## Spa Automation

Automatically heat spa to desired temperature:

```python
import asyncio
from iaqualink import AqualinkClient

async def heat_spa_to_temperature(target_temp: int = 102):
    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()
        system = list(systems.values())[0]
        devices = await system.get_devices()

        spa_temp = devices.get('spa_temp')
        spa_heater = devices.get('spa_heater')
        spa_setpoint = devices.get('spa_set_point')

        if not all([spa_temp, spa_heater, spa_setpoint]):
            print("Required spa devices not found")
            return

        # Set target temperature
        print(f"Setting spa temperature to {target_temp}°F")
        await spa_setpoint.set_temperature(target_temp)

        # Turn on heater
        if not spa_heater.is_on:
            print("Turning on spa heater")
            await spa_heater.turn_on()

        # Monitor until target reached
        while True:
            await system.update()
            current = spa_temp.state

            print(f"Current: {current}°F, Target: {target_temp}°F")

            if current >= target_temp:
                print("Target temperature reached!")
                break

            await asyncio.sleep(30)  # Check every 30 seconds

asyncio.run(heat_spa_to_temperature(102))
```

## System Status Report

Generate a comprehensive status report:

```python
import asyncio
from iaqualink import AqualinkClient

async def system_status_report():
    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()

        for serial, system in systems.items():
            print(f"\n{'='*60}")
            print(f"System: {system.name}")
            print(f"Serial: {serial}")
            print(f"Type: {system.data.get('device_type')}")
            print(f"Online: {system.online}")
            print(f"{'='*60}")

            if not system.online:
                print("System is offline")
                continue

            devices = await system.get_devices()

            # Temperature sensors
            print("\nTemperatures:")
            for name, device in devices.items():
                if 'temp' in name and hasattr(device, 'state'):
                    if device.state:
                        print(f"  {device.label}: {device.state}°{device.unit}")

            # Switches (pumps, heaters, etc)
            print("\nSwitches:")
            for name, device in devices.items():
                if hasattr(device, 'is_on') and not hasattr(device, 'set_temperature'):
                    status = "ON" if device.is_on else "OFF"
                    print(f"  {device.label}: {status}")

            # Thermostats
            print("\nThermostats:")
            for name, device in devices.items():
                if hasattr(device, 'set_temperature'):
                    print(f"  {device.label}: {device.state}°{device.unit}")

            # Chemistry
            print("\nChemistry:")
            chemistry_sensors = ['ph', 'orp', 'salt']
            for name in chemistry_sensors:
                device = devices.get(name)
                if device and device.state:
                    unit = " mV" if name == "orp" else " ppm" if name == "salt" else ""
                    print(f"  {device.label}: {device.state}{unit}")

asyncio.run(system_status_report())
```

## Scheduled Pool Pump

Turn pool pump on/off at scheduled times:

```python
import asyncio
from datetime import datetime
from iaqualink import AqualinkClient

async def scheduled_pump_control():
    # Configure schedule
    START_HOUR = 8   # 8 AM
    STOP_HOUR = 18   # 6 PM

    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()
        system = list(systems.values())[0]
        devices = await system.get_devices()

        pool_pump = devices.get('pool_pump')
        if not pool_pump:
            print("Pool pump not found")
            return

        print(f"Pump schedule: ON at {START_HOUR}:00, OFF at {STOP_HOUR}:00")

        while True:
            await system.update()
            now = datetime.now()
            current_hour = now.hour

            should_be_on = START_HOUR <= current_hour < STOP_HOUR

            if should_be_on and not pool_pump.is_on:
                print(f"[{now}] Turning pump ON")
                await pool_pump.turn_on()
            elif not should_be_on and pool_pump.is_on:
                print(f"[{now}] Turning pump OFF")
                await pool_pump.turn_off()

            # Check every 5 minutes
            await asyncio.sleep(300)

asyncio.run(scheduled_pump_control())
```

## Multi-System Management

Manage multiple pool systems:

```python
import asyncio
from iaqualink import AqualinkClient

async def manage_multiple_systems():
    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()

        # Update all systems in parallel
        await asyncio.gather(*[
            system.update() for system in systems.values()
        ])

        # Process each system
        for serial, system in systems.items():
            print(f"\nSystem: {system.name}")

            if not system.online:
                print("  Status: OFFLINE")
                continue

            devices = await system.get_devices()

            # Get pool temperature
            pool_temp = devices.get('pool_temp')
            if pool_temp:
                print(f"  Pool Temp: {pool_temp.state}°F")

            # Get pump status
            pool_pump = devices.get('pool_pump')
            if pool_pump:
                status = "ON" if pool_pump.is_on else "OFF"
                print(f"  Pool Pump: {status}")

asyncio.run(manage_multiple_systems())
```

## Error Handling

Robust error handling example:

```python
import asyncio
from iaqualink import (
    AqualinkClient,
    AqualinkServiceUnauthorizedException,
    AqualinkServiceException,
    AqualinkSystemOfflineException,
)

async def robust_control():
    try:
        async with AqualinkClient('user@example.com', 'password') as client:
            try:
                systems = await client.get_systems()
                system = list(systems.values())[0]

                try:
                    devices = await system.get_devices()
                    pool_pump = devices.get('pool_pump')

                    if pool_pump:
                        await pool_pump.turn_on()
                        print("Pool pump turned on successfully")

                except AqualinkSystemOfflineException:
                    print("System is offline")

            except AqualinkServiceException as e:
                print(f"Service error: {e}")

    except AqualinkServiceUnauthorizedException:
        print("Login failed - check credentials")
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(robust_control())
```

## Configuration from Environment

Load credentials from environment variables:

```python
import asyncio
import os
from iaqualink import AqualinkClient

async def main():
    # Load from environment
    username = os.getenv('IAQUALINK_USERNAME')
    password = os.getenv('IAQUALINK_PASSWORD')

    if not username or not password:
        print("Set IAQUALINK_USERNAME and IAQUALINK_PASSWORD")
        return

    async with AqualinkClient(username, password) as client:
        systems = await client.get_systems()
        print(f"Found {len(systems)} system(s)")

        for system in systems.values():
            print(f"  - {system.name}")

asyncio.run(main())
```

Run with:
```bash
export IAQUALINK_USERNAME="user@example.com"
export IAQUALINK_PASSWORD="your-password"
python script.py
```

## Next Steps

- [API Reference](../api/client.md) - Detailed API documentation
- [Systems Guide](systems.md) - Learn about system types
- [Devices Guide](devices.md) - Learn about device types
