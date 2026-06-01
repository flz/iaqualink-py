# Writing Tests

This guide explains the test structure and how to add tests for new systems and device classes.

## Test Architecture

Tests are split into two layers:

| Layer | Location | Purpose |
|---|---|---|
| **Conformance** | `tests/conformance/` | Verifies the interface contract across all systems using parametrized pytest fixtures |
| **System-specific** | `tests/systems/<name>/` | Verifies wire-protocol details (JSON payloads, URL params, state parsing) |

Both layers run together — every PR must pass `uv run pytest` with all tests green.

## Conformance Tests

Conformance tests verify that every device and system implementation satisfies the abstract contract defined in `device.py` and `system.py`. They use **fixture dataclasses** and **factory functions** — no class inheritance.

### Structure

```
tests/conformance/
├── __init__.py
├── conftest.py              # Aggregates factories, exposes parametrized fixtures
├── fixtures.py              # Dataclass definitions (DeviceFixture, SwitchFixture, etc.)
├── test_device.py           # Tests AqualinkDevice contract
├── test_sensor.py           # Tests AqualinkSensor contract
├── test_binary_sensor.py    # Tests AqualinkBinarySensor contract
├── test_switch.py           # Tests AqualinkSwitch contract
├── test_light.py            # Tests AqualinkLight contract
├── test_climate.py          # Tests AqualinkClimate contract
├── test_number.py           # Tests AqualinkNumber contract
├── test_fan.py              # Tests AqualinkFan contract
└── test_system.py           # Tests AqualinkSystem contract

tests/systems/<name>/
├── __init__.py
├── factories.py             # Factory functions for conformance fixtures
├── fixtures/                # JSON fixture files for HTTP mock responses
├── test_device.py
├── test_system.py
└── test_parsing.py          # (optional)
```

### Fixture Dataclasses

Each device type has a fixture dataclass in `fixtures.py` that bundles the device instances and behavioral flags:

```python
@dataclass
class SwitchFixture:
    device_on: AqualinkSwitch    # Device instance in "on" state
    device_off: AqualinkSwitch   # Device instance in "off" state
    has_noop_guard: bool = True  # Whether turn_on/off skips when already in state
    expected_class: type | None = None
```

For devices with on/off states, provide two instances. For stateless devices (sensors, numbers), provide one.

### Factory Functions

Each system provides factory functions in `tests/systems/<name>/factories.py`. A factory constructs a fixture dataclass with realistic data:

```python
def _exo_aux_switch() -> SwitchFixture:
    system = _make_system()
    data_on = {"name": "aux_1", "type": "Foo", "state": 1, "light": 0, "mode": ""}
    data_off = {"name": "aux_1", "type": "Foo", "state": 0, "light": 0, "mode": ""}
    return SwitchFixture(
        device_on=ExoDevice.from_data(system, data_on),
        device_off=ExoDevice.from_data(system, data_off),
        expected_class=ExoAuxSwitch,
    )
```

Factories are collected into exported lists of `(id, callable)` tuples:

```python
exo_switch_factories: list[tuple[str, callable]] = [
    ("exo-aux-switch", _exo_aux_switch),
    ("exo-attribute-switch", _exo_attribute_switch),
    ("exo-filter-pump", _exo_filter_pump),
]
```

The `conftest.py` aggregates these lists and exposes parametrized fixtures that pytest uses to run each conformance test against every registered device.

### Adding a New System to Conformance Tests

1. Create `tests/systems/newsystem/factories.py`
2. Write factory functions for each device type your system implements
3. Export factory lists using the naming convention `<system>_<type>_factories`
   (e.g., `newsystem_device_factories`, `newsystem_switch_factories`)

The conftest auto-discovers these lists by scanning `tests/systems/*/factories.py`
for attributes matching `<system>_<type>_factories` — no changes to `conftest.py` needed.

### SystemFixture and refresh_response

The `SystemFixture` includes a `refresh_response` dict — the JSON body returned by the mock HTTP layer during `refresh()` tests:

```python
def _newsystem_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    system = AqualinkSystem.from_data(client, data={...})
    return SystemFixture(
        system=system,
        expected_class=NewSystem,
        expected_online_status=SystemStatus.CONNECTED,
        refresh_response={"status": "connected", "devices": []},
    )
```

Set `expected_online_status=None` if your system's multi-request refresh flow cannot be exercised with a single mocked response.

## System-Specific Tests

These tests live in `tests/systems/<name>/` and verify implementation details: correct HTTP payloads, URL construction, state parsing, and routing logic.

### Structure

```
tests/systems/newsystem/
├── __init__.py
├── test_device.py    # Device control and parsing tests
├── test_system.py    # System refresh and lifecycle tests
└── test_parsing.py   # Response parsing edge cases (optional)
```

### Testing Patterns

System-specific tests use plain pytest classes with per-test factory helpers:

```python
from ...conftest import dotstar, resp_200

def _make_switch():
    system = NewSystem(AqualinkClient("foo", "bar"), {"serial_number": "SN123", ...})
    sut = NewSwitch(system, {"name": "switch_1", "state": "0"})
    return system, sut

class TestNewSwitch:
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        _, sut = _make_switch()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_response"):
            await sut.turn_on()
        url = str(respx_mock.calls[0].request.url)
        assert "switch_1=on" in url
```

Conformance tests handle the abstract contract; system-specific tests focus on wire-protocol correctness.

### HTTP Mocking

All tests use `respx` for HTTP mocking via the `respx_mock` pytest fixture (injected automatically):

```python
async def test_turn_on(
    switch_fixture: SwitchFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await switch_fixture.device_off.turn_on()
    assert len(respx_mock.calls) > 0
```

### Async Test Execution

The project uses `pytest-asyncio` with `asyncio_mode = "auto"` — async test functions are collected automatically without needing `@pytest.mark.asyncio`.

## Adding Tests for a New System

### Checklist

- [ ] Create `tests/systems/newsystem/factories.py` with factories for every device type (auto-discovered by conftest)
- [ ] Create `tests/systems/newsystem/` directory with `__init__.py`
- [ ] Add `test_system.py` with standalone tests for refresh, parsing, and status transitions
- [ ] Add `test_device.py` with standalone tests for each device class
- [ ] Use `@respx.mock` and `patch.object` to verify wire-protocol correctness
- [ ] Add a `test_parsing.py` if response parsing has non-trivial edge cases
- [ ] Run `uv run pytest` — all tests must pass
- [ ] Run `uv run prek run --all-files` — lint and type checks must pass

### Adding Tests for a New Device Type

When adding a new base device type to `device.py`:

1. Add a fixture dataclass in `tests/conformance/fixtures.py`
2. Add a conformance test module `tests/conformance/test_newdevice.py`
3. Add a parametrized fixture in `tests/conformance/conftest.py`
4. Register factories in each system's `factories.py` that implements the type
