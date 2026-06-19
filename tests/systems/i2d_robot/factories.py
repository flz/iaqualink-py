"""i2d_robot device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkBinarySensor, AqualinkSensor
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.i2d_robot.device import (
    I2dBinarySensor,
    I2dDevice,
    I2dRobot,
    I2dSensor,
)
from iaqualink.systems.i2d_robot.system import I2dRobotSystem

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

I2D_ROBOT_SYSTEM_DATA: dict[str, Any] = {
    "id": "PQR789",
    "serial_number": "ROBOT001",
    "name": "Polaris Robot",
    "device_type": "i2d_robot",
}
I2D_ROBOT_SENSOR_DATA: dict[str, Any] = {
    "name": "state",
    "state": "actively_cleaning",
}
I2D_ROBOT_BINARY_ON_DATA: dict[str, Any] = {"name": "running", "state": 1}
I2D_ROBOT_ROBOT_DATA: dict[str, Any] = {"name": "robot", "state": 0x04}


def make_system() -> I2dRobotSystem:
    client = AqualinkClient("foo", "bar")
    return cast(
        I2dRobotSystem,
        I2dRobotSystem.from_data(client, I2D_ROBOT_SYSTEM_DATA),
    )


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _i2d_robot_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=I2dDevice.from_data(system, {**I2D_ROBOT_SENSOR_DATA}),
        expected_class=I2dSensor,
    )


def _i2d_robot_binary_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=I2dDevice.from_data(system, {**I2D_ROBOT_BINARY_ON_DATA}),
        expected_class=I2dBinarySensor,
    )


def _i2d_robot_robot_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=I2dDevice.from_data(system, {**I2D_ROBOT_ROBOT_DATA}),
        expected_class=I2dRobot,
    )


i2d_robot_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d_robot-sensor-device", _i2d_robot_sensor_device),
    ("i2d_robot-binary-sensor-device", _i2d_robot_binary_sensor_device),
    ("i2d_robot-robot-device", _i2d_robot_robot_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _i2d_robot_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            I2dDevice.from_data(system, {**I2D_ROBOT_SENSOR_DATA}),
        ),
        expected_class=I2dSensor,
    )


i2d_robot_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d_robot-state-sensor", _i2d_robot_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _i2d_robot_running() -> BinarySensorFixture:
    system = make_system()
    data_off: dict[str, Any] = {**I2D_ROBOT_BINARY_ON_DATA, "state": 0}
    return BinarySensorFixture(
        device_on=cast(
            AqualinkBinarySensor,
            I2dDevice.from_data(system, {**I2D_ROBOT_BINARY_ON_DATA}),
        ),
        device_off=cast(
            AqualinkBinarySensor,
            I2dDevice.from_data(system, data_off),
        ),
        expected_class=I2dBinarySensor,
    )


i2d_robot_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d_robot-running", _i2d_robot_running),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _i2d_robot_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    system = AqualinkSystem.from_data(client, data=I2D_ROBOT_SYSTEM_DATA)
    return SystemFixture(
        system=system,
        expected_class=I2dRobotSystem,
        expected_online_status=SystemStatus.ONLINE,
        refresh_response=load_fixture("i2d_robot", "control_status"),
    )


i2d_robot_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("i2d_robot-system", _i2d_robot_system),
]

# i2d_robot does not implement these device types.
i2d_robot_switch_factories: list[tuple[str, Callable[[], Any]]] = []
i2d_robot_light_factories: list[tuple[str, Callable[[], Any]]] = []
i2d_robot_climate_factories: list[tuple[str, Callable[[], Any]]] = []
i2d_robot_number_factories: list[tuple[str, Callable[[], Any]]] = []
i2d_robot_fan_factories: list[tuple[str, Callable[[], Any]]] = []
i2d_robot_select_factories: list[tuple[str, Callable[[], Any]]] = []
