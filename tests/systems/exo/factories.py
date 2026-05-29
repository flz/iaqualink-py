"""EXO device factories for conformance tests."""

from __future__ import annotations

from typing import cast

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.exo.device import (
    ExoAttributeSensor,
    ExoAttributeSwitch,
    ExoAuxSwitch,
    ExoClimate,
    ExoDevice,
    ExoFilterPump,
    ExoSensor,
)
from iaqualink.systems.exo.system import ExoSystem

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

EXO_SYSTEM_DATA: dict = {"serial_number": "SN123456", "device_type": "exo"}
EXO_DEVICE_DATA: dict = {"name": "Test Device", "state": "42"}
EXO_SENSOR_DATA: dict = {
    "name": "sns_1",
    "sensor_type": "Foo",
    "value": 42,
    "state": 1,
}
EXO_ATTRIBUTE_SENSOR_DATA: dict = {"name": "foo_bar", "state": 42}
EXO_FILTER_PUMP_ON_DATA: dict = {"name": "filter_pump", "type": 1, "state": 1}
EXO_HEATING_ON_DATA: dict = {
    "name": "heating",
    "enabled": 1,
    "sp": 20,
    "sp_min": 1,
    "sp_max": 40,
}
EXO_WATER_TEMP_DATA: dict = {
    "name": "sns_3",
    "sensor_type": "Water Temp",
    "state": 1,
    "value": 16,
}


def make_system() -> ExoSystem:
    client = AqualinkClient("foo", "bar")
    return ExoSystem(client, data=EXO_SYSTEM_DATA)


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _exo_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=ExoDevice(system, {**EXO_DEVICE_DATA}), expected_class=ExoDevice
    )


def _exo_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=ExoDevice.from_data(system, {**EXO_SENSOR_DATA}),
        expected_class=ExoSensor,
    )


def _exo_attribute_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=ExoDevice.from_data(system, {**EXO_ATTRIBUTE_SENSOR_DATA}),
        expected_class=ExoAttributeSensor,
    )


exo_device_factories: list[tuple[str, callable]] = [
    ("exo-device", _exo_device),
    ("exo-sensor-device", _exo_sensor_device),
    ("exo-attribute-sensor-device", _exo_attribute_sensor_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _exo_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=ExoDevice.from_data(system, {**EXO_SENSOR_DATA}),
        expected_class=ExoSensor,
    )


def _exo_attribute_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=ExoDevice.from_data(system, {**EXO_ATTRIBUTE_SENSOR_DATA}),
        expected_class=ExoAttributeSensor,
    )


exo_sensor_factories: list[tuple[str, callable]] = [
    ("exo-sensor", _exo_sensor),
    ("exo-attribute-sensor", _exo_attribute_sensor),
]

# ---------------------------------------------------------------------------
# Switch fixtures
# ---------------------------------------------------------------------------


def _exo_aux_switch() -> SwitchFixture:
    system = make_system()
    data_on = {
        "name": "aux_1",
        "type": "Foo",
        "mode": "mode",
        "light": 0,
        "state": 1,
    }
    data_off = {**data_on, "state": 0}
    return SwitchFixture(
        device_on=ExoDevice.from_data(system, data_on),
        device_off=ExoDevice.from_data(system, data_off),
        expected_class=ExoAuxSwitch,
    )


def _exo_attribute_switch() -> SwitchFixture:
    system = make_system()
    data_on = {"name": "boost", "state": 1}
    data_off = {"name": "boost", "state": 0}
    return SwitchFixture(
        device_on=ExoDevice.from_data(system, data_on),
        device_off=ExoDevice.from_data(system, data_off),
        expected_class=ExoAttributeSwitch,
    )


def _exo_filter_pump() -> SwitchFixture:
    system = make_system()
    data_off = {**EXO_FILTER_PUMP_ON_DATA, "state": 0}
    return SwitchFixture(
        device_on=ExoDevice.from_data(system, {**EXO_FILTER_PUMP_ON_DATA}),
        device_off=ExoDevice.from_data(system, data_off),
        expected_class=ExoFilterPump,
    )


exo_switch_factories: list[tuple[str, callable]] = [
    ("exo-aux-switch", _exo_aux_switch),
    ("exo-attribute-switch", _exo_attribute_switch),
    ("exo-filter-pump", _exo_filter_pump),
]

# ---------------------------------------------------------------------------
# Climate fixtures
# ---------------------------------------------------------------------------


def _exo_climate() -> ClimateFixture:
    system = make_system()

    pool_set_point_off = {**EXO_HEATING_ON_DATA, "enabled": 0}

    water_temp_dev = ExoDevice.from_data(system, {**EXO_WATER_TEMP_DATA})

    device_on = cast(
        ExoClimate, ExoDevice.from_data(system, {**EXO_HEATING_ON_DATA})
    )
    device_off = cast(
        ExoClimate, ExoDevice.from_data(system, pool_set_point_off)
    )

    system.devices = {
        "heating": device_on,
        "sns_3": water_temp_dev,
    }

    return ClimateFixture(
        device_on=device_on,
        device_off=device_off,
        supports_fahrenheit=False,
        expected_class=ExoClimate,
    )


exo_climate_factories: list[tuple[str, callable]] = [
    ("exo-climate", _exo_climate),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _exo_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data = {
        "id": 1,
        "serial_number": "ABCDEFG",
        "device_type": "exo",
        "name": "Pool",
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=ExoSystem,
        expected_online_status=SystemStatus.CONNECTED,
        refresh_response={
            "state": {"reported": {"aws": {"status": "connected"}}}
        },
    )


exo_system_factories: list[tuple[str, callable]] = [
    ("exo-system", _exo_system),
]

# EXO does not implement these device types.
exo_binary_sensor_factories: list[tuple[str, callable]] = []
exo_light_factories: list[tuple[str, callable]] = []
exo_number_factories: list[tuple[str, callable]] = []
exo_fan_factories: list[tuple[str, callable]] = []
