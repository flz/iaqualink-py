"""Cyclobat device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkBinarySensor, AqualinkSensor
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclobat.device import (
    CyclobatBinarySensor,
    CyclobatDevice,
    CyclobatRobot,
    CyclobatSensor,
)
from iaqualink.systems.cyclobat.system import CyclobatSystem

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

CYCLOBAT_SYSTEM_DATA: dict[str, Any] = {
    "serial_number": "SN42",
    "device_type": "cyclobat",
}
CYCLOBAT_SENSOR_DATA: dict[str, Any] = {
    "name": "battery_percentage",
    "state": 87,
}
CYCLOBAT_RUNNING_ON_DATA: dict[str, Any] = {"name": "running", "state": 1}
CYCLOBAT_ROBOT_DATA: dict[str, Any] = {"name": "robot", "state": 1}


def make_system() -> CyclobatSystem:
    client = AqualinkClient("foo", "bar")
    return CyclobatSystem(client, data=CYCLOBAT_SYSTEM_DATA)


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _cyclobat_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=CyclobatDevice.from_data(system, {**CYCLOBAT_SENSOR_DATA}),
        expected_class=CyclobatSensor,
    )


def _cyclobat_binary_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=CyclobatDevice.from_data(system, {**CYCLOBAT_RUNNING_ON_DATA}),
        expected_class=CyclobatBinarySensor,
    )


def _cyclobat_robot_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=CyclobatDevice.from_data(system, {**CYCLOBAT_ROBOT_DATA}),
        expected_class=CyclobatRobot,
    )


cyclobat_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclobat-sensor-device", _cyclobat_sensor_device),
    ("cyclobat-binary-sensor-device", _cyclobat_binary_sensor_device),
    ("cyclobat-robot-device", _cyclobat_robot_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _cyclobat_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            CyclobatDevice.from_data(system, {**CYCLOBAT_SENSOR_DATA}),
        ),
        expected_class=CyclobatSensor,
    )


cyclobat_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclobat-battery-sensor", _cyclobat_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _cyclobat_running() -> BinarySensorFixture:
    system = make_system()
    data_off: dict[str, Any] = {**CYCLOBAT_RUNNING_ON_DATA, "state": 0}
    return BinarySensorFixture(
        device_on=cast(
            AqualinkBinarySensor,
            CyclobatDevice.from_data(system, {**CYCLOBAT_RUNNING_ON_DATA}),
        ),
        device_off=cast(
            AqualinkBinarySensor,
            CyclobatDevice.from_data(system, data_off),
        ),
        expected_class=CyclobatBinarySensor,
    )


cyclobat_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclobat-running", _cyclobat_running),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _cyclobat_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": "CV3000",
        "serial_number": "SN42",
        "device_type": "cyclobat",
        "name": "Pool Robot",
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=CyclobatSystem,
        expected_online_status=SystemStatus.ONLINE,
        refresh_response=load_fixture("cyclobat", "shadow_get"),
    )


cyclobat_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("cyclobat-system", _cyclobat_system),
]

# Cyclobat does not implement these device types.
cyclobat_switch_factories: list[tuple[str, Callable[[], Any]]] = []
cyclobat_light_factories: list[tuple[str, Callable[[], Any]]] = []
cyclobat_climate_factories: list[tuple[str, Callable[[], Any]]] = []
cyclobat_number_factories: list[tuple[str, Callable[[], Any]]] = []
cyclobat_fan_factories: list[tuple[str, Callable[[], Any]]] = []
