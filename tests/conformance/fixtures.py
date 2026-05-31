"""Fixture dataclasses for conformance tests.

Each dataclass bundles the device instances and behavioral flags needed to
exercise a device type's contract without inheritance or state mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from iaqualink.device import (
        AqualinkBinarySensor,
        AqualinkClimate,
        AqualinkDevice,
        AqualinkFan,
        AqualinkLight,
        AqualinkNumber,
        AqualinkSensor,
        AqualinkSwitch,
    )
    from iaqualink.system import AqualinkSystem, SystemStatus


@dataclass
class DeviceFixture:
    """Minimal fixture for any AqualinkDevice — tests name/label/manufacturer/model."""

    device: AqualinkDevice
    expected_class: type | None = None


@dataclass
class SensorFixture:
    """Fixture for AqualinkSensor conformance tests."""

    device: AqualinkSensor
    expected_class: type | None = None


@dataclass
class BinarySensorFixture:
    """Fixture for AqualinkBinarySensor conformance tests."""

    device_on: AqualinkBinarySensor
    device_off: AqualinkBinarySensor
    expected_class: type | None = None


@dataclass
class SwitchFixture:
    """Fixture for AqualinkSwitch conformance tests."""

    device_on: AqualinkSwitch
    device_off: AqualinkSwitch
    has_noop_guard: bool = True
    expected_class: type | None = None


@dataclass
class LightFixture:
    """Fixture for AqualinkLight conformance tests."""

    device_on: AqualinkLight
    device_off: AqualinkLight
    has_noop_guard: bool = True
    expected_class: type | None = None


@dataclass
class ClimateFixture:
    """Fixture for AqualinkClimate conformance tests."""

    device_on: AqualinkClimate
    device_off: AqualinkClimate
    has_noop_guard: bool = True
    supports_fahrenheit: bool = True
    """True if the system supports Fahrenheit (tests min/max_temp in °F are skipped when False)."""
    expected_class: type | None = None


@dataclass
class NumberFixture:
    """Fixture for AqualinkNumber conformance tests."""

    device: AqualinkNumber
    expected_class: type | None = None


@dataclass
class FanFixture:
    """Fixture for AqualinkFan conformance tests."""

    device_on: AqualinkFan
    device_off: AqualinkFan
    expected_class: type | None = None


@dataclass
class SystemFixture:
    """Fixture for AqualinkSystem conformance tests."""

    system: AqualinkSystem
    expected_class: type | None = None
    expected_online_status: SystemStatus | None = None
    refresh_response: dict = field(default_factory=dict)
    refresh_internal_method: str | None = None
    """Name of the internal method called during refresh (for throttle/401 tests)."""
    request_method: str | None = None
    """Name of a request method to test retry-once-on-401 behavior."""
    request_method_args: tuple[object, ...] = ()
    """Positional args for the request method."""
