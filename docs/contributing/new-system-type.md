# Adding a New System Type

This guide walks through adding support for a new pool system type.

## Steps

### 1. Create directory structure

```bash
mkdir -p src/iaqualink/systems/newsystem
touch src/iaqualink/systems/newsystem/__init__.py
touch src/iaqualink/systems/newsystem/system.py
touch src/iaqualink/systems/newsystem/device.py
```

### 2. Implement the system class

```python
# src/iaqualink/systems/newsystem/system.py
from iaqualink.system import AqualinkSystem, SystemStatus

class NewSystem(AqualinkSystem):
    NAME = "newsystem"  # Must match device_type from API

    async def _refresh(self) -> None:
        r = await self._send_state_request()
        self._parse_state_response(r)   # must set self.status before returning

    def _parse_state_response(self, response) -> None:
        # ... parse logic ...
        self.status = SystemStatus.ONLINE   # required before returning
```

See [Architecture: System Status Lifecycle](architecture.md#system-status-lifecycle) for the full `_refresh()` contract.

Key rules:
- Set `self.status` to a non-`IN_PROGRESS` value before returning from `_refresh()`
- Do **not** catch `AqualinkServiceException` or subclasses inside `_refresh()` — `refresh()` handles those automatically

### 3. Implement device classes

```python
# src/iaqualink/systems/newsystem/device.py
from iaqualink.device import AqualinkDevice, AqualinkSwitch, AqualinkThermostat

class NewDevice(AqualinkDevice):
    """Base device for new system."""
    pass

class NewSwitch(NewDevice, AqualinkSwitch):
    """Switch for new system."""
    pass
```

### 4. Export from `__init__.py`

```python
# src/iaqualink/systems/newsystem/__init__.py
from .system import NewSystem
from .device import NewDevice, NewSwitch

__all__ = ["NewSystem", "NewDevice", "NewSwitch"]
```

### 5. Register in client.py

Add an import in `src/iaqualink/client.py` so `AqualinkSystem.from_data()` discovers the subclass at runtime:

```python
from iaqualink.systems import newsystem  # noqa: F401
```

### 6. Add tests

Follow the existing structure in `tests/systems/`. Required:
- Subclass `base_test_system.py` and `base_test_device.py` abstract test cases
- Add JSON fixtures alongside your test files in `tests/systems/newsystem/`
- Cover `_refresh()`, device parsing, and all device types

### 7. Update documentation

All of the following must be updated in the same PR:

| File | What to add |
|---|---|
| `README.md` | System to Multi-System Support feature list |
| `docs/index.md` | System to Features list |
| `docs/api/systems/.nav.yml` | Add entry for the new system |
| `docs/reference/systems/.nav.yml` | Add entry for the new system |
| `docs/implementation/systems/.nav.yml` | Add entry for the new system |
| `docs/getting-started/newsystem.md` | API overview, status table, device inventory |
| `docs/implementation/systems/newsystem.md` | Status lifecycle, design decisions, deltas vs reference |
| `docs/api/systems/newsystem.md` | `:::` autodoc directives for system + device classes |
| `docs/reference/systems/newsystem.md` | Wire-level protocol documentation |

## Checklist

- [ ] `systems/newsystem/` directory with `__init__.py`, `system.py`, `device.py`
- [ ] `NewSystem.NAME` matches the `device_type` string from the API device list
- [ ] `_refresh()` sets `self.status` before returning on every code path
- [ ] `_refresh()` does not catch `AqualinkServiceException` subclasses
- [ ] Device parsing in `_parse_*_response()` methods
- [ ] Device classes extend the correct base types
- [ ] Module imported in `client.py`
- [ ] Tests cover system refresh, device parsing, and all device control paths
- [ ] All documentation files listed above updated in the same PR
