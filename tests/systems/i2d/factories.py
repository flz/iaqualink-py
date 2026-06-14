"""I2D device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.system import SystemStatus
from iaqualink.systems.i2d.device import (
    I2dBinarySensor,
    I2dFan,
    I2dNumber,
    I2dSensor,
    I2dSwitch,
)
from iaqualink.systems.i2d.system import I2dSystem

from ...conformance.fixtures import (
    BinarySensorFixture,
    DeviceFixture,
    FanFixture,
    NumberFixture,
    SensorFixture,
    SwitchFixture,
    SystemFixture,
)

CONTRACT_SYSTEM_DATA: dict = {
    "id": 1,
    "serial_number": "ABC123",
    "name": "Pool Pump",
    "device_type": "i2d",
}


def make_system() -> I2dSystem:
    client = AqualinkClient("foo", "bar")
    return cast(I2dSystem, I2dSystem.from_data(client, CONTRACT_SYSTEM_DATA))


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _i2d_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=I2dSensor(
            system,
            {"speed": "1500"},
            key="speed",
            label="Motor Speed",
            unit="RPM",
        ),
        expected_class=I2dSensor,
    )


def _i2d_switch_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=I2dSwitch(
            system,
            {"freezeprotectenable": "1"},
            key="freezeprotectenable",
            label="Freeze Protection",
        ),
        expected_class=I2dSwitch,
    )


def _i2d_binary_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=I2dBinarySensor(
            system,
            {"freezeprotectstatus": "0"},
            key="freezeprotectstatus",
            label="Freeze Protect Status",
        ),
        expected_class=I2dBinarySensor,
    )


i2d_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d-sensor-device", _i2d_sensor_device),
    ("i2d-switch-device", _i2d_switch_device),
    ("i2d-binary-sensor-device", _i2d_binary_sensor_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _i2d_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=I2dSensor(
            system,
            {"speed": "1500"},
            key="speed",
            label="Motor Speed",
            unit="RPM",
        ),
        expected_class=I2dSensor,
    )


i2d_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d-sensor", _i2d_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _i2d_binary_sensor() -> BinarySensorFixture:
    system = make_system()
    data_on: dict = {"freezeprotectstatus": "1"}
    data_off: dict = {"freezeprotectstatus": "0"}
    return BinarySensorFixture(
        device_on=I2dBinarySensor(
            system,
            data_on,
            key="freezeprotectstatus",
            label="Freeze Protect Status",
        ),
        device_off=I2dBinarySensor(
            system,
            data_off,
            key="freezeprotectstatus",
            label="Freeze Protect Status",
        ),
        expected_class=I2dBinarySensor,
    )


i2d_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d-binary-sensor", _i2d_binary_sensor),
]

# ---------------------------------------------------------------------------
# Switch fixtures
# ---------------------------------------------------------------------------


def _i2d_switch() -> SwitchFixture:
    system = make_system()
    data_on: dict = {"freezeprotectenable": "1"}
    data_off: dict = {"freezeprotectenable": "0"}
    return SwitchFixture(
        device_on=I2dSwitch(
            system,
            data_on,
            key="freezeprotectenable",
            label="Freeze Protection",
        ),
        device_off=I2dSwitch(
            system,
            data_off,
            key="freezeprotectenable",
            label="Freeze Protection",
        ),
        has_noop_guard=False,  # i2d write endpoint has no idempotency guard
        expected_class=I2dSwitch,
    )


i2d_switch_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d-switch", _i2d_switch),
]

# ---------------------------------------------------------------------------
# Number fixtures
# ---------------------------------------------------------------------------


def _i2d_number() -> NumberFixture:
    system = make_system()
    data = {
        "quickcleanrpm": "3000",
        "globalrpmmin": "600",
        "globalrpmmax": "3450",
    }
    return NumberFixture(
        device=I2dNumber(
            system,
            data,
            key="quickcleanrpm",
            label="Quick Clean RPM",
            min_value=600.0,
            max_value=3450.0,
            step=25.0,
            unit="RPM",
        ),
        expected_class=I2dNumber,
    )


i2d_number_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d-number", _i2d_number),
]

# ---------------------------------------------------------------------------
# Fan fixtures
# ---------------------------------------------------------------------------


def _i2d_fan() -> FanFixture:
    system = make_system()
    base: dict = {
        "name": "ABC123",
        "opmode": "2",
        "globalrpmmin": "600",
        "globalrpmmax": "3450",
    }
    return FanFixture(
        device_on=I2dFan(system, {**base, "runstate": "on"}),
        device_off=I2dFan(system, {**base, "runstate": "off"}),
        expected_class=I2dFan,
    )


i2d_fan_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d-fan", _i2d_fan),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _i2d_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    system = I2dSystem.from_data(client, CONTRACT_SYSTEM_DATA)
    return SystemFixture(
        system=system,
        expected_class=I2dSystem,
        expected_online_status=SystemStatus.CONNECTED,
        refresh_response={"alldata": {"opmode": "1", "name": "PUMP1"}},
    )


i2d_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d-system", _i2d_system),
]

# i2d does not implement these device types.
i2d_light_factories: list[tuple[str, Callable[[], Any]]] = []
i2d_climate_factories: list[tuple[str, Callable[[], Any]]] = []
