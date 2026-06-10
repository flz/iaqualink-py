"""TCX device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkSensor, AqualinkSwitch
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.device import (
    TcxAirSensor,
    TcxAuxSwitch,
    TcxChlorinatorBoost,
    TcxClimate,
    TcxDevice,
    TcxFeatureCircuit,
    TcxFilterPump,
    TcxSolarSensor,
    TcxWaterSensor,
    TcxZigbeeSwitch,
)
from iaqualink.systems.tcx.system import TcxSystem

from ...conformance.fixtures import (
    ClimateFixture,
    DeviceFixture,
    SensorFixture,
    SwitchFixture,
    SystemFixture,
)

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


def _tcx_filter_pump() -> SwitchFixture:
    system = make_system()
    data_off: dict[str, Any] = {**TCX_FILTER_PUMP_ON_DATA, "st": 0}
    return SwitchFixture(
        device_on=cast(
            AqualinkSwitch,
            TcxDevice.from_data(system, {**TCX_FILTER_PUMP_ON_DATA}),
        ),
        device_off=cast(AqualinkSwitch, TcxDevice.from_data(system, data_off)),
        expected_class=TcxFilterPump,
    )


def _tcx_aux_switch() -> SwitchFixture:
    system = make_system()
    data_off: dict[str, Any] = {**TCX_AUX_SWITCH_ON_DATA, "st": 0}
    return SwitchFixture(
        device_on=cast(
            AqualinkSwitch,
            TcxDevice.from_data(system, {**TCX_AUX_SWITCH_ON_DATA}),
        ),
        device_off=cast(AqualinkSwitch, TcxDevice.from_data(system, data_off)),
        expected_class=TcxAuxSwitch,
    )


def _tcx_chlorinator_boost() -> SwitchFixture:
    system = make_system()
    data_off: dict[str, Any] = {**TCX_CHLORINATOR_BOOST_ON_DATA, "boost": 0}
    return SwitchFixture(
        device_on=cast(
            AqualinkSwitch,
            TcxDevice.from_data(system, {**TCX_CHLORINATOR_BOOST_ON_DATA}),
        ),
        device_off=cast(AqualinkSwitch, TcxDevice.from_data(system, data_off)),
        expected_class=TcxChlorinatorBoost,
    )


def _tcx_feature_circuit() -> SwitchFixture:
    system = make_system()
    data_off: dict[str, Any] = {**TCX_FEATURE_CIRCUIT_ON_DATA, "st": 0}
    return SwitchFixture(
        device_on=cast(
            AqualinkSwitch,
            TcxDevice.from_data(system, {**TCX_FEATURE_CIRCUIT_ON_DATA}),
        ),
        device_off=cast(AqualinkSwitch, TcxDevice.from_data(system, data_off)),
        expected_class=TcxFeatureCircuit,
    )


def _tcx_zigbee_switch() -> SwitchFixture:
    system = make_system()
    data_off: dict[str, Any] = {**TCX_ZIGBEE_SWITCH_ON_DATA, "st": 0}
    return SwitchFixture(
        device_on=cast(
            AqualinkSwitch,
            TcxDevice.from_data(system, {**TCX_ZIGBEE_SWITCH_ON_DATA}),
        ),
        device_off=cast(AqualinkSwitch, TcxDevice.from_data(system, data_off)),
        expected_class=TcxZigbeeSwitch,
    )


tcx_switch_factories: list[tuple[str, Callable[[], Any]]] = [
    ("tcx-filter-pump", _tcx_filter_pump),
    ("tcx-aux-switch", _tcx_aux_switch),
    ("tcx-chlorinator-boost", _tcx_chlorinator_boost),
    ("tcx-feature-circuit", _tcx_feature_circuit),
    ("tcx-zigbee-switch", _tcx_zigbee_switch),
]

# ---------------------------------------------------------------------------
# Climate fixtures
# ---------------------------------------------------------------------------


def _tcx_climate() -> ClimateFixture:
    system = make_system()

    water_dev = TcxDevice.from_data(system, {**TCX_WATER_DATA})
    device_on = cast(
        TcxClimate,
        TcxDevice.from_data(system, {**TCX_CLIMATE_ON_DATA}),
    )
    climate_off_data: dict[str, Any] = {
        **TCX_CLIMATE_ON_DATA,
        "heatEnabled": False,
    }
    device_off = cast(
        TcxClimate,
        TcxDevice.from_data(system, climate_off_data),
    )

    system.devices = {
        "water": water_dev,
        "TspBdy0": device_on,
    }

    return ClimateFixture(
        device_on=device_on,
        device_off=device_off,
        expected_class=TcxClimate,
    )


tcx_climate_factories: list[tuple[str, Callable[[], Any]]] = [
    ("tcx-climate", _tcx_climate),
]

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
# TcxVariableSpeedPump doesn't implement on/off (supports_turn_on/off are
# False), which conflicts with the generic AqualinkFan conformance contract
# for `is_on`. Covered by direct unit tests in test_device.py instead.
tcx_fan_factories: list[tuple[str, Callable[[], Any]]] = []
