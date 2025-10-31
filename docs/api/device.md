# Device API

Device classes represent individual pool equipment and sensors.

## Base Classes

### AqualinkDevice

::: iaqualink.device.AqualinkDevice

### AqualinkSensor

::: iaqualink.device.AqualinkSensor

### AqualinkBinarySensor

::: iaqualink.device.AqualinkBinarySensor

### AqualinkSwitch

::: iaqualink.device.AqualinkSwitch

### AqualinkLight

::: iaqualink.device.AqualinkLight

### AqualinkThermostat

::: iaqualink.device.AqualinkThermostat

## Device Hierarchy

```
AqualinkDevice
├── AqualinkSensor (read-only state)
│   └── AqualinkBinarySensor (on/off state)
│       └── AqualinkSwitch (controllable on/off)
│           ├── AqualinkLight (toggle support)
│           └── AqualinkThermostat (temperature control)
```

## Common Properties

All devices inherit these properties:

### name

Internal device identifier.

**Type:** `str`

### label

User-friendly device label.

**Type:** `str`

### state

Current device state (type varies by device).

**Type:** `Any`

### system

Reference to parent system.

**Type:** `AqualinkSystem`

### data

Raw device data from API.

**Type:** `dict[str, Any]`

## Sensor Properties

### unit

Measurement unit for sensor readings.

**Type:** `str`

## Binary Sensor Properties

### is_on

Boolean indicating if device is on.

**Type:** `bool`

## Switch Methods

### turn_on()

Turn the switch on.

**Returns:** `None`

**Raises:**
- `AqualinkServiceException` - Command failed

### turn_off()

Turn the switch off.

**Returns:** `None`

**Raises:**
- `AqualinkServiceException` - Command failed

## Light Methods

### toggle()

Toggle the light state.

**Returns:** `None`

**Raises:**
- `AqualinkServiceException` - Command failed

## Thermostat Properties

### min_temperature

Minimum allowed temperature.

**Type:** `int`

### max_temperature

Maximum allowed temperature.

**Type:** `int`

## Thermostat Methods

### set_temperature()

Set target temperature.

**Parameters:**
- `temperature` (`int`) - Target temperature in device's unit

**Returns:** `None`

**Raises:**
- `AqualinkServiceException` - Command failed

## Usage Examples

### Sensors

```python
# Temperature sensor
pool_temp = devices.get('pool_temp')
print(f"Pool: {pool_temp.state}°{pool_temp.unit}")

# Chemistry sensor
ph_sensor = devices.get('ph')
if ph_sensor:
    print(f"pH: {ph_sensor.state}")
```

### Binary Sensors

```python
# Check status
freeze = devices.get('freeze_protection')
if freeze.is_on:
    print("Freeze protection active")
```

### Switches

```python
# Control pump
pool_pump = devices.get('pool_pump')
await pool_pump.turn_on()
await pool_pump.turn_off()

# Check state
if pool_pump.is_on:
    print("Pump is running")
```

### Lights

```python
# Control light
pool_light = devices.get('pool_light')
await pool_light.turn_on()
await pool_light.toggle()  # Turn off
await pool_light.toggle()  # Turn on
```

### Thermostats

```python
# Set temperature
spa_thermostat = devices.get('spa_set_point')
print(f"Range: {spa_thermostat.min_temperature}-{spa_thermostat.max_temperature}")
await spa_thermostat.set_temperature(102)
```

## Device Discovery

Devices are accessed through the system:

```python
# Get all devices
devices = await system.get_devices()

# Access by name
device = devices.get('pool_pump')

# Iterate
for name, device in devices.items():
    print(f"{name}: {device.label}")
```

## State Updates

Device state is updated when the parent system updates:

```python
# Update system
await system.update()

# Device state is now current
print(pool_pump.is_on)
```

## See Also

- [System API](system.md) - System reference
- [iAqua Devices](iaqua.md) - iAqua-specific devices
- [eXO Devices](exo.md) - eXO-specific devices
- [Devices Guide](../guide/devices.md) - Device usage guide
