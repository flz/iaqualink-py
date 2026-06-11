"""Cyclonext device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkBinarySensor, AqualinkSensor
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclonext.device import (
    CyclonextBinarySensor,
    CyclonextDevice,
    CyclonextErrorSensor,
    CyclonextRobot,
    CyclonextSensor,
)
from iaqualink.systems.cyclonext.system import CyclonextSystem

from ...conformance.fixtures import (
    BinarySensorFixture,
    DeviceFixture,
    SensorFixture,
    SystemFixture,
)
from ...conftest import load_fixture

# ---------------------------------------------------------------------------
# Shared test data constants
# ---------------------------------------------------------------------------

CYCLONEXT_SYSTEM_DATA: dict[str, Any] = {
    "serial_number": "SN42",
    "device_type": "cyclonext",
}
CYCLONEXT_SENSOR_DATA: dict[str, Any] = {"name": "mode", "state": 1}
CYCLONEXT_ERROR_DATA: dict[str, Any] = {"name": "error_code", "state": 0}
CYCLONEXT_RUNNING_ON_DATA: dict[str, Any] = {"name": "running", "state": 1}
CYCLONEXT_ROBOT_DATA: dict[str, Any] = {"name": "robot", "state": 1}


def make_system() -> CyclonextSystem:
    client = AqualinkClient("foo", "bar")
    return CyclonextSystem(client, data=CYCLONEXT_SYSTEM_DATA)


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _cyclonext_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=CyclonextDevice.from_data(system, {**CYCLONEXT_SENSOR_DATA}),
        expected_class=CyclonextSensor,
    )


def _cyclonext_error_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=CyclonextDevice.from_data(system, {**CYCLONEXT_ERROR_DATA}),
        expected_class=CyclonextErrorSensor,
    )


def _cyclonext_binary_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=CyclonextDevice.from_data(system, {**CYCLONEXT_RUNNING_ON_DATA}),
        expected_class=CyclonextBinarySensor,
    )


def _cyclonext_robot_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=CyclonextDevice.from_data(system, {**CYCLONEXT_ROBOT_DATA}),
        expected_class=CyclonextRobot,
    )


cyclonext_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclonext-sensor-device", _cyclonext_sensor_device),
    ("cyclonext-error-sensor-device", _cyclonext_error_sensor_device),
    ("cyclonext-binary-sensor-device", _cyclonext_binary_sensor_device),
    ("cyclonext-robot-device", _cyclonext_robot_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _cyclonext_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            CyclonextDevice.from_data(system, {**CYCLONEXT_SENSOR_DATA}),
        ),
        expected_class=CyclonextSensor,
    )


def _cyclonext_error_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            CyclonextDevice.from_data(system, {**CYCLONEXT_ERROR_DATA}),
        ),
        expected_class=CyclonextErrorSensor,
    )


cyclonext_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclonext-mode-sensor", _cyclonext_sensor),
    ("cyclonext-error-sensor", _cyclonext_error_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _cyclonext_running() -> BinarySensorFixture:
    system = make_system()
    data_off: dict[str, Any] = {**CYCLONEXT_RUNNING_ON_DATA, "state": 0}
    return BinarySensorFixture(
        device_on=cast(
            AqualinkBinarySensor,
            CyclonextDevice.from_data(system, {**CYCLONEXT_RUNNING_ON_DATA}),
        ),
        device_off=cast(
            AqualinkBinarySensor,
            CyclonextDevice.from_data(system, data_off),
        ),
        expected_class=CyclonextBinarySensor,
    )


cyclonext_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclonext-running", _cyclonext_running),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _cyclonext_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "SN42",
        "device_type": "cyclonext",
        "name": "Pool Robot",
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=CyclonextSystem,
        expected_online_status=SystemStatus.ONLINE,
        refresh_response=load_fixture("cyclonext", "shadow_get"),
    )


cyclonext_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclonext-system", _cyclonext_system),
]

# Cyclonext does not implement these device types.
cyclonext_switch_factories: list[tuple[str, Callable[[], Any]]] = []
cyclonext_light_factories: list[tuple[str, Callable[[], Any]]] = []
cyclonext_climate_factories: list[tuple[str, Callable[[], Any]]] = []
cyclonext_number_factories: list[tuple[str, Callable[[], Any]]] = []
cyclonext_fan_factories: list[tuple[str, Callable[[], Any]]] = []
