# Device API

Device classes represent individual pool equipment and sensors.

## Base Class

### AqualinkDevice

::: iaqualink.device.AqualinkDevice

## Device Classes

### AqualinkSensor

::: iaqualink.device.AqualinkSensor

### AqualinkBinarySensor

::: iaqualink.device.AqualinkBinarySensor

### AqualinkSwitch

::: iaqualink.device.AqualinkSwitch

### AqualinkLight

::: iaqualink.device.AqualinkLight

### AqualinkClimate

::: iaqualink.device.AqualinkClimate

### AqualinkNumber

::: iaqualink.device.AqualinkNumber

### AqualinkSelect

::: iaqualink.device.AqualinkSelect

### AqualinkFan

::: iaqualink.device.AqualinkFan

## Device Hierarchy

All device classes are flat direct subclasses of `AqualinkDevice`:

```
AqualinkDevice (ABC)
├── AqualinkSensor        — read-only sensor (HA SensorEntity)
├── AqualinkBinarySensor  — read-only on/off sensor (HA BinarySensorEntity)
├── AqualinkSwitch        — controllable on/off (HA SwitchEntity)
├── AqualinkLight         — controllable light with optional brightness/effects (HA LightEntity)
├── AqualinkClimate       — temperature control (HA ClimateEntity)
├── AqualinkNumber        — writable numeric setting (HA NumberEntity)
├── AqualinkSelect        — single-choice picker (HA SelectEntity)
└── AqualinkFan           — fan/pump control (HA FanEntity)
```

## Common Properties

All devices inherit these properties from `AqualinkDevice`:

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Unique device identifier within the system |
| `label` | `str` | Human-readable display name |
| `manufacturer` | `str` | Device manufacturer name |
| `model` | `str` | Device model name |
| `system` | `AqualinkSystem` | Parent system reference |
| `data` | `DeviceData` | Raw device data from API |

## Sensor Properties

| Property | Type | Description |
|---|---|---|
| `value` | `str` | Current sensor reading |
| `unit_of_measurement` | `str \| None` | Measurement unit (e.g. `"°F"`, `"RPM"`) |
| `value_enum` | `type[Enum] \| None` | Optional enum for translating wire values |
| `value_translated` | `str \| None` | Human-readable enum translation of `value` |

## Binary Sensor Properties

| Property | Type | Description |
|---|---|---|
| `is_on` | `bool` | `True` if the sensor is active/triggered |

## Switch Properties and Methods

| Member | Type | Description |
|---|---|---|
| `is_on` | `bool` | `True` if the switch is on |
| `turn_on()` | async | Turn the switch on |
| `turn_off()` | async | Turn the switch off |

## Light Properties and Methods

| Member | Type | Description |
|---|---|---|
| `is_on` | `bool` | `True` if the light is on |
| `turn_on()` | async | Turn the light on |
| `turn_off()` | async | Turn the light off |
| `brightness_percentage` | `int \| None` | Current brightness 0–100%; `None` if not supported |
| `supports_brightness` | `bool` | `True` if brightness control is available |
| `set_brightness_percentage(brightness)` | async | Set brightness (0–100%) |
| `effect` | `str \| None` | Current active effect; `None` if off or unsupported |
| `effect_list` | `list[str] \| None` | Available effect names; `None` if unsupported |
| `supports_effect` | `bool` | `True` if effects are available |
| `set_effect(effect)` | async | Activate a named effect |

## Climate Properties and Methods

| Member | Type | Description |
|---|---|---|
| `is_on` | `bool` | `True` if heating/cooling is active |
| `turn_on()` | async | Enable climate control |
| `turn_off()` | async | Disable climate control |
| `temperature_unit` | `str` | `"C"` or `"F"` |
| `current_temperature` | `str` | Current measured temperature |
| `target_temperature` | `str` | Current set-point |
| `min_temp` | `int` | Minimum allowed set-point |
| `max_temp` | `int` | Maximum allowed set-point |
| `set_temperature(temperature)` | async | Set target temperature (validates range) |

## Number Properties and Methods

| Member | Type | Description |
|---|---|---|
| `current_value` | `float \| None` | Current numeric value |
| `min_value` | `float` | Minimum allowed value |
| `max_value` | `float` | Maximum allowed value |
| `step` | `float` | Required step increment (default `1.0`) |
| `unit_of_measurement` | `str \| None` | Value unit (e.g. `"RPM"`) |
| `set_value(value)` | async | Set value (validates range and step) |

## Select Properties and Methods

| Member | Type | Description |
|---|---|---|
| `current_option` | `str \| None` | Currently selected option; `None` if unavailable |
| `options` | `list[str]` | Valid options |
| `select_option(option)` | async | Select one of `options` (validates membership) |

## Fan Properties and Methods

| Member | Type | Description |
|---|---|---|
| `is_on` | `bool` | `True` if the fan/pump is running |
| `supports_turn_on` | `bool` | `True` if power-on is supported |
| `supports_turn_off` | `bool` | `True` if power-off is supported |
| `turn_on()` | async | Turn on (if supported) |
| `turn_off()` | async | Turn off (if supported) |
| `preset_mode` | `str \| None` | Currently active preset name |
| `preset_modes` | `list[str]` | Available preset names |
| `supports_presets` | `bool` | `True` if preset modes are available |
| `set_preset_mode(preset_mode)` | async | Activate a preset (validates name) |
| `percentage` | `int \| None` | Current speed as a percentage (0–100); `None` if unavailable |
| `supports_percentage` | `bool` | `True` if speed percentage control is available |
| `set_percentage(percentage)` | async | Set speed 0–100% (validates range) |

## Usage Examples

### Sensors

```python
# Temperature sensor
pool_temp = devices.get('pool_temp')
print(f"Pool: {pool_temp.value}°{pool_temp.unit_of_measurement}")

# Chemistry sensor
ph_sensor = devices.get('ph')
if ph_sensor:
    print(f"pH: {ph_sensor.value}")
```

### Binary Sensors

```python
freeze = devices.get('freeze_protection')
if freeze.is_on:
    print("Freeze protection active")
```

### Switches

```python
pool_pump = devices.get('pool_pump')
await pool_pump.turn_on()
await pool_pump.turn_off()

if pool_pump.is_on:
    print("Pump is running")
```

### Lights

```python
pool_light = devices.get('pool_light')
await pool_light.turn_on()
await pool_light.turn_off()

# Dimmable light
if pool_light.supports_brightness:
    await pool_light.set_brightness_percentage(75)

# Color light
if pool_light.supports_effect:
    print(pool_light.effect_list)
    await pool_light.set_effect("Alpine White")
```

### Climate

```python
spa = devices.get('spa_set_point')
print(f"Range: {spa.min_temp}-{spa.max_temp}{spa.temperature_unit}")
print(f"Current: {spa.current_temperature}, Target: {spa.target_temperature}")
await spa.set_temperature(102)
```

### Numbers

```python
rpm = devices.get('customspeedrpm')
print(f"RPM: {rpm.current_value} {rpm.unit_of_measurement}")
await rpm.set_value(2000)
```

### Selects

```python
mode = devices.get('heatpump_mode')
print(mode.options)
await mode.select_option("chill")
```

### Fans (variable-speed pumps)

```python
pump = devices.get('ABC123')
if pump.supports_turn_on:
    await pump.turn_on()

if pump.supports_percentage:
    await pump.set_percentage(75)

if pump.supports_presets:
    print(pump.preset_modes)
    await pump.set_preset_mode("CUSTOM")
```

## Device Discovery

```python
devices = await system.get_devices()

# Access by name
device = devices.get('pool_pump')

# Iterate
for name, device in devices.items():
    print(f"{name}: {device.label}")

# Filter by type
from iaqualink import AqualinkSensor
sensors = {k: v for k, v in devices.items() if isinstance(v, AqualinkSensor)}
```

## See Also

- [System API](system.md) — System reference
- [iAqua Devices](systems/iaqua.md) — iAqua-specific devices
- [eXO Devices](systems/exo.md) — eXO-specific devices
- [i2d Devices](systems/i2d.md) — iQPump-specific devices
- [Architecture](../contributing/architecture.md) — Device hierarchy and design
