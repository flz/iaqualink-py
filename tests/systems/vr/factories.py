"""VR device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkBinarySensor, AqualinkSensor
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.vr.device import (
    VrBinarySensor,
    VrDevice,
    VrErrorSensor,
    VrRobot,
    VrSensor,
)
from iaqualink.systems.vr.system import VrSystem

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

VR_SYSTEM_DATA: dict[str, Any] = {
    "serial_number": "SN42",
    "device_type": "vr",
}
VR_SENSOR_DATA: dict[str, Any] = {"name": "stepper", "state": 30}
VR_ERROR_DATA: dict[str, Any] = {"name": "error_state", "state": 0}
VR_RUNNING_ON_DATA: dict[str, Any] = {"name": "running", "state": 1}
VR_ROBOT_DATA: dict[str, Any] = {"name": "robot", "state": 1}


def make_system() -> VrSystem:
    client = AqualinkClient("foo", "bar")
    return VrSystem(client, data=VR_SYSTEM_DATA)


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _vr_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VR_SENSOR_DATA}),
        expected_class=VrSensor,
    )


def _vr_error_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VR_ERROR_DATA}),
        expected_class=VrErrorSensor,
    )


def _vr_binary_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VR_RUNNING_ON_DATA}),
        expected_class=VrBinarySensor,
    )


def _vr_robot_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=VrDevice.from_data(system, {**VR_ROBOT_DATA}),
        expected_class=VrRobot,
    )


vr_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vr-sensor-device", _vr_sensor_device),
    ("vr-error-sensor-device", _vr_error_sensor_device),
    ("vr-binary-sensor-device", _vr_binary_sensor_device),
    ("vr-robot-device", _vr_robot_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _vr_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            VrDevice.from_data(system, {**VR_SENSOR_DATA}),
        ),
        expected_class=VrSensor,
    )


def _vr_error_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            VrDevice.from_data(system, {**VR_ERROR_DATA}),
        ),
        expected_class=VrErrorSensor,
    )


vr_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vr-stepper-sensor", _vr_sensor),
    ("vr-error-sensor", _vr_error_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _vr_running() -> BinarySensorFixture:
    system = make_system()
    data_off: dict[str, Any] = {**VR_RUNNING_ON_DATA, "state": 0}
    return BinarySensorFixture(
        device_on=cast(
            AqualinkBinarySensor,
            VrDevice.from_data(system, {**VR_RUNNING_ON_DATA}),
        ),
        device_off=cast(
            AqualinkBinarySensor,
            VrDevice.from_data(system, data_off),
        ),
        expected_class=VrBinarySensor,
    )


vr_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vr-running", _vr_running),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _vr_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "SN42",
        "device_type": "vr",
        "name": "Pool Robot",
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=VrSystem,
        expected_online_status=SystemStatus.ONLINE,
        refresh_response=load_fixture("vr", "shadow_get"),
    )


vr_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("vr-system", _vr_system),
]

# VR does not implement these device types.
vr_switch_factories: list[tuple[str, Callable[[], Any]]] = []
vr_light_factories: list[tuple[str, Callable[[], Any]]] = []
vr_climate_factories: list[tuple[str, Callable[[], Any]]] = []
vr_number_factories: list[tuple[str, Callable[[], Any]]] = []
vr_fan_factories: list[tuple[str, Callable[[], Any]]] = []
vr_select_factories: list[tuple[str, Callable[[], Any]]] = []
