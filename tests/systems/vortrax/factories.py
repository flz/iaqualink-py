"""Vortrax device factories for conformance tests.

Vortrax is a thin subclass of VrSystem; it reuses vr's device classes and
parser with the "vortrax" namespace. Factories therefore build real
VortraxSystem instances but instantiate the shared VrDevice classes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkBinarySensor, AqualinkSensor
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.vortrax.system import VortraxSystem
from iaqualink.systems.vr.device import (
    VrBinarySensor,
    VrDevice,
    VrErrorSensor,
    VrRobot,
    VrSensor,
)

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

VORTRAX_SYSTEM_DATA: dict[str, Any] = {
    "serial_number": "SN42",
    "device_type": "vortrax",
}
VORTRAX_SENSOR_DATA: dict[str, Any] = {"name": "stepper", "state": 30}
VORTRAX_ERROR_DATA: dict[str, Any] = {"name": "error_state", "state": 0}
VORTRAX_RUNNING_ON_DATA: dict[str, Any] = {"name": "running", "state": 1}
VORTRAX_ROBOT_DATA: dict[str, Any] = {"name": "robot", "state": 1}


def make_system() -> VortraxSystem:
    client = AqualinkClient("foo", "bar")
    return VortraxSystem(client, data=VORTRAX_SYSTEM_DATA)


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _vortrax_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VORTRAX_SENSOR_DATA}),
        expected_class=VrSensor,
    )


def _vortrax_error_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VORTRAX_ERROR_DATA}),
        expected_class=VrErrorSensor,
    )


def _vortrax_binary_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VORTRAX_RUNNING_ON_DATA}),
        expected_class=VrBinarySensor,
    )


def _vortrax_robot_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VORTRAX_ROBOT_DATA}),
        expected_class=VrRobot,
    )


vortrax_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vortrax-sensor-device", _vortrax_sensor_device),
    ("vortrax-error-sensor-device", _vortrax_error_sensor_device),
    ("vortrax-binary-sensor-device", _vortrax_binary_sensor_device),
    ("vortrax-robot-device", _vortrax_robot_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _vortrax_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            VrDevice.from_data(system, {**VORTRAX_SENSOR_DATA}),
        ),
        expected_class=VrSensor,
    )


def _vortrax_error_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            VrDevice.from_data(system, {**VORTRAX_ERROR_DATA}),
        ),
        expected_class=VrErrorSensor,
    )


vortrax_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vortrax-stepper-sensor", _vortrax_sensor),
    ("vortrax-error-sensor", _vortrax_error_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _vortrax_running() -> BinarySensorFixture:
    system = make_system()
    data_off: dict[str, Any] = {**VORTRAX_RUNNING_ON_DATA, "state": 0}
    return BinarySensorFixture(
        device_on=cast(
            AqualinkBinarySensor,
            VrDevice.from_data(system, {**VORTRAX_RUNNING_ON_DATA}),
        ),
        device_off=cast(
            AqualinkBinarySensor,
            VrDevice.from_data(system, data_off),
        ),
        expected_class=VrBinarySensor,
    )


vortrax_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vortrax-running", _vortrax_running),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _vortrax_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "SN42",
        "device_type": "vortrax",
        "name": "Pool Robot",
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=VortraxSystem,
        expected_online_status=SystemStatus.ONLINE,
        refresh_response=load_fixture("vortrax", "shadow_get"),
    )


vortrax_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vortrax-system", _vortrax_system),
]

# Vortrax does not implement these device types.
vortrax_switch_factories: list[tuple[str, Callable[[], Any]]] = []
vortrax_light_factories: list[tuple[str, Callable[[], Any]]] = []
vortrax_climate_factories: list[tuple[str, Callable[[], Any]]] = []
vortrax_number_factories: list[tuple[str, Callable[[], Any]]] = []
vortrax_fan_factories: list[tuple[str, Callable[[], Any]]] = []
vortrax_select_factories: list[tuple[str, Callable[[], Any]]] = []
