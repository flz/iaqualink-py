"""TCX device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkSensor
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.device import (
    TcxAirSensor,
    TcxDevice,
    TcxFilterPump,
    TcxSolarSensor,
    TcxWaterSensor,
)
from iaqualink.systems.tcx.system import TcxSystem

from ...conformance.fixtures import DeviceFixture, SensorFixture, SystemFixture

# ---------------------------------------------------------------------------
# Shared test data constants
# ---------------------------------------------------------------------------

TCX_SYSTEM_DATA: dict[str, Any] = {
    "serial_number": "ABCDEFG",
    "device_type": "tcx",
}
TCX_WATER_DATA: dict[str, Any] = {
    "name": "water",
    "value": 82,
    "us": 1,
    "fr": "Pool Water",
    "en": 1,
    "zn": [0],
}
TCX_AIR_DATA: dict[str, Any] = {"name": "air", "value": 72, "snsr": "ok"}
TCX_SOLAR_DATA: dict[str, Any] = {
    "name": "solar",
    "value": 105,
    "us": 1,
    "en": 0,
    "fr": "Solar Panel",
    "zn": [0],
}
TCX_FILTER_PUMP_ON_DATA: dict[str, Any] = {
    "name": "filt0",
    "st": 1,
    "en": 1,
    "fr": "Filter Pump",
}
TCX_AUX_SWITCH_ON_DATA: dict[str, Any] = {
    "name": "aux0",
    "st": 1,
    "en": 1,
    "app": "WF",
    "fr": "Waterfall",
}
TCX_CHLORINATOR_BOOST_ON_DATA: dict[str, Any] = {
    "name": "swc0",
    "boost": 1,
    "fr": "Salt Chlorinator",
}
TCX_FEATURE_CIRCUIT_ON_DATA: dict[str, Any] = {
    "name": "feaCircuit0",
    "st": 1,
    "en": 1,
    "fr": "Spa Jets",
}
TCX_ZIGBEE_SWITCH_ON_DATA: dict[str, Any] = {
    "name": "zig_aabbccdd",
    "addr": "aabbccdd",
    "st": 1,
    "fr": "Pool Light",
}
TCX_CLIMATE_ON_DATA: dict[str, Any] = {
    "name": "TspBdy0",
    "bodyName": "Pool",
    "waterTempSet": 88,
    "heatEnabled": True,
}


def make_system() -> TcxSystem:
    client = AqualinkClient("foo", "bar")
    return TcxSystem(client, data=TCX_SYSTEM_DATA)


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _tcx_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=TcxDevice.from_data(system, {**TCX_FILTER_PUMP_ON_DATA}),
        expected_class=TcxFilterPump,
    )


tcx_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("tcx-device", _tcx_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _tcx_water_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            TcxDevice.from_data(system, {**TCX_WATER_DATA}),
        ),
        expected_class=TcxWaterSensor,
    )


def _tcx_air_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            TcxDevice.from_data(system, {**TCX_AIR_DATA}),
        ),
        expected_class=TcxAirSensor,
    )


def _tcx_solar_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            TcxDevice.from_data(system, {**TCX_SOLAR_DATA}),
        ),
        expected_class=TcxSolarSensor,
    )


tcx_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("tcx-water-sensor", _tcx_water_sensor),
    ("tcx-air-sensor", _tcx_air_sensor),
    ("tcx-solar-sensor", _tcx_solar_sensor),
]

# ---------------------------------------------------------------------------
# Switch fixtures
# ---------------------------------------------------------------------------


# Generic switch conformance (test_switch.py) asserts turn_on/turn_off make
# an HTTP request via respx. TCX writes now go over WS (StateController
# frames), which respx can't intercept, so these fixtures would fail for the
# wrong reason. Covered by direct unit tests in test_device.py instead (same
# precedent as tcx_fan_factories below); the *_ON_DATA constants above are
# reused there.
tcx_switch_factories: list[tuple[str, Callable[[], Any]]] = []

# ---------------------------------------------------------------------------
# Climate fixtures
# ---------------------------------------------------------------------------


# Generic climate conformance (test_climate.py) asserts turn_on/turn_off/
# set_temperature make an HTTP request via respx, same problem as switches
# above (TCX writes now go over WS). Covered by direct unit tests in
# test_device.py instead; TCX_CLIMATE_ON_DATA is reused there.
tcx_climate_factories: list[tuple[str, Callable[[], Any]]] = []

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _tcx_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "ABCDEFG",
        "device_type": "tcx",
        "name": "Pool",
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=TcxSystem,
        expected_online_status=SystemStatus.CONNECTED,
        refresh_response={
            "state": {"reported": {"aws": {"status": "connected"}}}
        },
    )


tcx_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("tcx-system", _tcx_system),
]

# TCX does not implement these device types.
tcx_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = []
tcx_light_factories: list[tuple[str, Callable[[], Any]]] = []
tcx_number_factories: list[tuple[str, Callable[[], Any]]] = []
tcx_select_factories: list[tuple[str, Callable[[], Any]]] = []
# TcxVariableSpeedPump doesn't implement on/off (supports_turn_on/off are
# False), which conflicts with the generic AqualinkFan conformance contract
# for `is_on`. Covered by direct unit tests in test_device.py instead.
tcx_fan_factories: list[tuple[str, Callable[[], Any]]] = []
