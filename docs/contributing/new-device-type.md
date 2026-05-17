# Adding a New Base Device Type

This guide covers adding a new direct subclass of `AqualinkDevice` to `device.py`.

## Steps

### 1. Define the device class in `device.py`

```python
# src/iaqualink/device.py
class AqualinkNewDevice(AqualinkDevice):
    """Brief description of new device type."""

    @property
    def current_value(self) -> float:
        return float(self.state)

    async def set_value(self, value: float) -> None:
        ...
```

Only add a new direct subclass when the new type has meaningfully different behaviour from all existing types. Intermediate classes (e.g. `AqualinkBinarySensor`) don't need their own entry.

### 2. Register in `_DEVICE_GROUPS` in `cli/app.py`

```python
# src/iaqualink/cli/app.py
_DEVICE_GROUPS: list[tuple[type[AqualinkDevice], str]] = [
    (AqualinkThermostat, "Thermostats"),
    (AqualinkLight, "Lights"),
    (AqualinkSwitch, "Switches"),
    (AqualinkPump, "Pumps"),
    (AqualinkNumber, "Numbers"),
    (AqualinkNewDevice, "New Devices"),   # add before AqualinkSensor
    (AqualinkSensor, "Sensors"),
]
```

Devices without a matching entry silently fall through to the "Other" bucket in CLI output.

### 3. Ordering rule

Subclasses must appear **before** their superclass in `_DEVICE_GROUPS`. For example, `AqualinkLight` (which extends `AqualinkSwitch`) must come before `AqualinkSwitch`.

Current order and hierarchy:

| Class | CLI Group | Extends |
|---|---|---|
| `AqualinkThermostat` | Thermostats | `AqualinkSwitch` |
| `AqualinkLight` | Lights | `AqualinkSwitch` |
| `AqualinkSwitch` | Switches | `AqualinkBinarySensor` |
| `AqualinkPump` | Pumps | `AqualinkDevice` |
| `AqualinkNumber` | Numbers | `AqualinkDevice` |
| `AqualinkSensor` | Sensors | `AqualinkDevice` — also covers `AqualinkBinarySensor` |

### 4. Export from `__init__.py`

Add the new class to `src/iaqualink/__init__.py` if it should be part of the public API.

### 5. Update docs

- Add a row to the device type table in `docs/contributing/new-device-type.md` (this file)
- Update the device hierarchy diagram in `docs/contributing/architecture.md`
- Add API docs in `docs/api/device.md` (the `:::` autodoc directive picks it up automatically if docstrings are present)
