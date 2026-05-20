# Adding a New Base Device Type

This guide covers adding a new direct subclass of `AqualinkDevice` to `device.py`.

## Steps

### 1. Define the device class in `device.py`

All base device classes are direct subclasses of `AqualinkDevice` (flat hierarchy). Use
`@abstractmethod` for properties and methods that every concrete subclass must implement.
Use `raise NotImplementedError` stubs for optional features (implement only when
`supports_X = True`). Use template methods for operations that need shared validation
before calling a private `_foo` method.

```python
# src/iaqualink/device.py
class AqualinkNewDevice(AqualinkDevice):
    """Brief description. Maps to HA SomeEntity."""

    # ── Required overrides ──────────────────────────────────────────────────

    @property
    @abstractmethod
    def some_required_property(self) -> str:
        """Doc string."""

    @abstractmethod
    async def _send_command(self, value: str) -> None:
        """Send the validated command to the device."""

    # ── Template (do not override) ───────────────────────────────────────────

    async def do_something(self, value: str) -> None:
        """Validate then dispatch."""
        if not value:
            raise AqualinkInvalidParameterException("value required")
        await self._send_command(value)
```

Only add a new direct subclass when the new type has meaningfully different behaviour
from all existing types.

### 2. Register in `_DEVICE_GROUPS` in `cli/app.py`

```python
# src/iaqualink/cli/app.py
_DEVICE_GROUPS: list[tuple[type[AqualinkDevice], str, str]] = [
    (AqualinkClimate,      "🌡️", "Climate"),
    (AqualinkLight,        "💡", "Lights"),
    (AqualinkSwitch,       "⚡", "Switches"),
    (AqualinkFan,          "⚙️", "Fans"),
    (AqualinkNumber,       "🔢", "Numbers"),
    (AqualinkBinarySensor, "📊", "Sensors"),
    (AqualinkSensor,       "📊", "Sensors"),
    (AqualinkNewDevice,    "🔧", "New Devices"),  # add here
]
```

Devices without a matching entry silently fall through to the "Other" bucket in CLI output.
Entries with the same label string are automatically merged into one group.

Also update `_format_device_line` if the new type needs a custom display string (value,
status, etc.).

### 3. Current device types

All classes are direct subclasses of `AqualinkDevice`:

| Class | CLI Group | HA Entity |
|---|---|---|
| `AqualinkClimate` | Climate | `ClimateEntity` |
| `AqualinkLight` | Lights | `LightEntity` |
| `AqualinkSwitch` | Switches | `SwitchEntity` |
| `AqualinkFan` | Fans | `FanEntity` (no PumpEntity in HA) |
| `AqualinkNumber` | Numbers | `NumberEntity` |
| `AqualinkBinarySensor` | Sensors | `BinarySensorEntity` |
| `AqualinkSensor` | Sensors | `SensorEntity` |

### 4. Export from `__init__.py`

Add the new class to `src/iaqualink/__init__.py` if it should be part of the public API.

### 5. Update docs

- Add a row to the device type table in `docs/contributing/new-device-type.md` (this file)
- Update the device hierarchy in `docs/contributing/architecture.md`
- Update the `_DEVICE_GROUPS` table in `CLAUDE.md`
- Add API docs in `docs/api/device.md` (the `:::` autodoc directive picks it up automatically)
