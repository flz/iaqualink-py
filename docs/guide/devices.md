# Devices

iaqualink-py provides a comprehensive device hierarchy for controlling and monitoring pool equipment.

## Device Hierarchy

The library uses inheritance to organize device types:

```
AqualinkDevice (base)
├── AqualinkSensor
│   ├── AqualinkBinarySensor
│   │   └── AqualinkSwitch
│   │       ├── AqualinkLight
│   │       └── AqualinkThermostat
```

## Device Types

### Sensors

Read-only devices that report state:

```python
# Temperature sensors
pool_temp = devices.get('pool_temp')
print(f"Pool: {pool_temp.state}°{pool_temp.unit}")

spa_temp = devices.get('spa_temp')
print(f"Spa: {spa_temp.state}°{spa_temp.unit}")

air_temp = devices.get('air_temp')
print(f"Air: {air_temp.state}°{air_temp.unit}")

# Chemistry sensors
ph_sensor = devices.get('ph')
if ph_sensor:
    print(f"pH: {ph_sensor.state}")

orp_sensor = devices.get('orp')
if orp_sensor:
    print(f"ORP: {orp_sensor.state} mV")

salt_sensor = devices.get('salt')
if salt_sensor:
    print(f"Salt: {salt_sensor.state} ppm")
```

### Binary Sensors

Sensors with on/off states:

```python
# Freeze protection
freeze = devices.get('freeze_protection')
if freeze:
    print(f"Freeze protection: {'Active' if freeze.is_on else 'Inactive'}")
```

### Switches

Devices that can be turned on/off:

```python
# Pumps
pool_pump = devices.get('pool_pump')
await pool_pump.turn_on()
await pool_pump.turn_off()
print(f"Pump is {'on' if pool_pump.is_on else 'off'}")

# Heaters
spa_heater = devices.get('spa_heater')
await spa_heater.turn_on()
await spa_heater.turn_off()

# Auxiliary devices
aux_1 = devices.get('aux_1')
await aux_1.turn_on()
await aux_1.turn_off()
```

### Lights

Special switches with toggle support:

```python
# Pool lights
pool_light = devices.get('pool_light')
await pool_light.turn_on()
await pool_light.turn_off()
await pool_light.toggle()  # Toggles current state

# Spa lights
spa_light = devices.get('spa_light')
await spa_light.toggle()
```

### Thermostats

Temperature controllers with set points:

```python
# Pool thermostat
pool_setpoint = devices.get('pool_set_point')
print(f"Current setting: {pool_setpoint.state}°{pool_setpoint.unit}")
await pool_setpoint.set_temperature(82)

# Spa thermostat
spa_setpoint = devices.get('spa_set_point')
await spa_setpoint.set_temperature(102)

# Check temperature ranges
print(f"Min: {spa_setpoint.min_temperature}")
print(f"Max: {spa_setpoint.max_temperature}")
```

## Common Device Properties

All devices share these properties:

```python
device.name          # Internal device name
device.label         # User-friendly label
device.state         # Current state (varies by type)
device.system        # Parent system reference
device.data          # Raw device data
```

## Device States

Different device types have different state representations:

```python
# Sensors: numeric or string value
temp_sensor.state    # 78.5

# Binary sensors: boolean
freeze.state         # True or False
freeze.is_on         # Convenience property

# Switches: boolean
pump.state           # "1" or "0" (string)
pump.is_on           # True or False (boolean)

# Thermostats: current setpoint
thermostat.state     # 82
```

## Finding Devices

### By Name

Device names are standardized:

```python
# Common device names
devices.get('pool_temp')        # Pool temperature sensor
devices.get('spa_temp')         # Spa temperature sensor
devices.get('air_temp')         # Air temperature sensor
devices.get('pool_pump')        # Pool pump
devices.get('spa_pump')         # Spa pump
devices.get('pool_heater')      # Pool heater
devices.get('spa_heater')       # Spa heater
devices.get('pool_set_point')   # Pool thermostat
devices.get('spa_set_point')    # Spa thermostat
devices.get('pool_light')       # Pool light
devices.get('spa_light')        # Spa light
devices.get('aux_1')            # Auxiliary 1
devices.get('aux_2')            # Auxiliary 2
# ... etc
```

### By Type

```python
# Find all temperature sensors
temps = {
    name: device
    for name, device in devices.items()
    if 'temp' in name
}

# Find all switches
switches = {
    name: device
    for name, device in devices.items()
    if hasattr(device, 'turn_on')
}

# Find all thermostats
thermostats = {
    name: device
    for name, device in devices.items()
    if hasattr(device, 'set_temperature')
}
```

## Device Commands

### Synchronous State Updates

Device state is updated when the parent system updates:

```python
# Update system (refreshes all devices)
await system.update()

# Check device state
print(pool_pump.is_on)
```

### Asynchronous Commands

Commands are sent immediately but state may take time to reflect:

```python
# Send command
await pool_pump.turn_on()

# Wait for state to update
await asyncio.sleep(1)
await system.update()

# Verify state changed
assert pool_pump.is_on
```

## Error Handling

Handle device command errors:

```python
from iaqualink import AqualinkServiceException

try:
    await pool_pump.turn_on()
except AqualinkServiceException as e:
    print(f"Command failed: {e}")
```

## System-Specific Devices

### iAqua Devices

iAqua systems have these specific characteristics:
- Devices use numeric IDs
- Commands sent via session requests
- Two-step state refresh

### eXO Devices

eXO systems have these specific characteristics:
- Devices use string endpoints
- Commands update desired state
- Single shadow state update

## Next Steps

- [Examples](examples.md) - See complete examples
- [API Reference](../api/device.md) - Detailed device API
- [Systems Guide](systems.md) - Learn about system types
