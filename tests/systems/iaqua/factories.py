"""iAqua device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem
from iaqualink.systems.iaqua.device import (
    IaquaAuxSwitch,
    IaquaBinarySensor,
    IaquaClimate,
    IaquaColorLightCL,
    IaquaColorLightHU,
    IaquaColorLightIB,
    IaquaColorLightJC,
    IaquaColorLightJL,
    IaquaColorLightSL,
    IaquaDevice,
    IaquaDimmableLight,
    IaquaHeater,
    IaquaIclLight,
    IaquaLightSwitch,
    IaquaOneTouchSwitch,
    IaquaSensor,
    IaquaSetPoint,
    IaquaSwcBoostSwitch,
    IaquaSwcSetPoint,
    IaquaSwitch,
)
from iaqualink.systems.iaqua.enums import IaquaTemperatureUnit
from iaqualink.systems.iaqua.system import IaquaSystem

from ...conformance.fixtures import (
    BinarySensorFixture,
    ClimateFixture,
    DeviceFixture,
    LightFixture,
    NumberFixture,
    SensorFixture,
    SwitchFixture,
    SystemFixture,
)

# ---------------------------------------------------------------------------
# Shared test data constants
# ---------------------------------------------------------------------------

IAQUA_SYSTEM_DATA: dict = {"serial_number": "SN123456", "device_type": "iaqua"}
IAQUA_DEVICE_DATA: dict = {"name": "device", "state": "42"}
IAQUA_SENSOR_DATA: dict = {"name": "orp", "state": "42"}
IAQUA_BINARY_SENSOR_OFF_DATA: dict = {"name": "freeze_protection", "state": "0"}
IAQUA_SWITCH_OFF_DATA: dict = {"name": "pool_pump", "state": "0"}
IAQUA_HEATER_OFF_DATA: dict = {"name": "pool_heater", "state": "0"}
IAQUA_ONETOUCH_OFF_DATA: dict = {
    "name": "onetouch_1",
    "state": "0",
    "label": "Morning Scene",
    "status": "1",
}
IAQUA_AUX_SWITCH_OFF_DATA: dict = {
    "name": "aux_1",
    "state": "0",
    "aux": "1",
    "type": "0",
    "label": "CLEANER",
}
IAQUA_LIGHT_SWITCH_OFF_DATA: dict = {
    "name": "aux_1",
    "state": "0",
    "aux": "1",
    "label": "POOL LIGHT",
    "type": "0",
}
IAQUA_DIMMABLE_LIGHT_ON_DATA: dict = {
    "name": "aux_1",
    "state": "1",
    "aux": "1",
    "subtype": "25",
    "type": "1",
    "label": "SPA LIGHT",
}
IAQUA_COLOR_LIGHT_OFF_DATA: dict = {
    "name": "aux_1",
    "aux": "1",
    "state": "0",
    "type": "2",
    "subtype": "5",
    "label": "POOL LIGHT",
}
IAQUA_POOL_SET_POINT_DATA: dict = {"name": "pool_set_point", "state": "86"}
IAQUA_POOL_TEMP_DATA: dict = {"name": "pool_temp", "state": "65"}
IAQUA_CLIMATE_DATA: dict = {"name": "pool_thermostat"}
IAQUA_SWC_BOOST_OFF_DATA: dict = {"name": "swc_boost", "state": "0"}
IAQUA_SWC_POOL_SET_POINT_DATA: dict = {
    "name": "swc_pool_set_point",
    "state": "50",
}


def make_system() -> IaquaSystem:
    client = AqualinkClient("foo", "bar")
    return IaquaSystem(client, data={**IAQUA_SYSTEM_DATA})


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _iaqua_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=IaquaDevice(system, {**IAQUA_DEVICE_DATA}),
        expected_class=IaquaDevice,
    )


def _iaqua_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=IaquaSensor(system, {**IAQUA_SENSOR_DATA}),
        expected_class=IaquaSensor,
    )


def _iaqua_binary_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=IaquaBinarySensor(system, {**IAQUA_BINARY_SENSOR_OFF_DATA}),
        expected_class=IaquaBinarySensor,
    )


iaqua_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-device", _iaqua_device),
    ("iaqua-sensor-device", _iaqua_sensor_device),
    ("iaqua-binary-sensor-device", _iaqua_binary_sensor_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _iaqua_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=IaquaSensor(system, {**IAQUA_SENSOR_DATA}),
        expected_class=IaquaSensor,
    )


iaqua_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-sensor", _iaqua_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _iaqua_binary_sensor() -> BinarySensorFixture:
    system = make_system()
    data_on = {**IAQUA_BINARY_SENSOR_OFF_DATA, "state": "1"}
    return BinarySensorFixture(
        device_on=IaquaBinarySensor(system, data_on),
        device_off=IaquaBinarySensor(system, {**IAQUA_BINARY_SENSOR_OFF_DATA}),
        expected_class=IaquaBinarySensor,
    )


iaqua_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-binary-sensor", _iaqua_binary_sensor),
]

# ---------------------------------------------------------------------------
# Switch fixtures
# ---------------------------------------------------------------------------


def _iaqua_switch() -> SwitchFixture:
    system = make_system()
    system._parse_home_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore
    data_on = {**IAQUA_SWITCH_OFF_DATA, "state": "1"}
    return SwitchFixture(
        device_on=IaquaSwitch(system, data_on),
        device_off=IaquaSwitch(system, {**IAQUA_SWITCH_OFF_DATA}),
        expected_class=IaquaSwitch,
    )


def _iaqua_heater() -> SwitchFixture:
    system = make_system()
    system._parse_home_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore
    data_on = {**IAQUA_HEATER_OFF_DATA, "state": "1"}
    return SwitchFixture(
        device_on=IaquaHeater(system, data_on),
        device_off=IaquaHeater(system, {**IAQUA_HEATER_OFF_DATA}),
        expected_class=IaquaHeater,
    )


def _iaqua_aux_switch() -> SwitchFixture:
    system = make_system()
    system._parse_devices_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore
    data_on = {**IAQUA_AUX_SWITCH_OFF_DATA, "state": "1"}
    data_off = {**IAQUA_AUX_SWITCH_OFF_DATA}
    return SwitchFixture(
        device_on=IaquaAuxSwitch(system, data_on),
        device_off=IaquaAuxSwitch(system, data_off),
        expected_class=IaquaAuxSwitch,
    )


def _iaqua_onetouch_switch() -> SwitchFixture:
    system = make_system()
    system._parse_onetouch_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore
    data_on = {**IAQUA_ONETOUCH_OFF_DATA, "state": "1"}
    data_off = {**IAQUA_ONETOUCH_OFF_DATA}
    return SwitchFixture(
        device_on=IaquaOneTouchSwitch(system, data_on),
        device_off=IaquaOneTouchSwitch(system, data_off),
        expected_class=IaquaOneTouchSwitch,
    )


def _iaqua_swc_boost_switch() -> SwitchFixture:
    system = make_system()
    data_on = {**IAQUA_SWC_BOOST_OFF_DATA, "state": "1"}
    return SwitchFixture(
        device_on=IaquaSwcBoostSwitch(system, data_on),
        device_off=IaquaSwcBoostSwitch(system, {**IAQUA_SWC_BOOST_OFF_DATA}),
        expected_class=IaquaSwcBoostSwitch,
    )


iaqua_switch_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-switch", _iaqua_switch),
    ("iaqua-heater", _iaqua_heater),
    ("iaqua-aux-switch", _iaqua_aux_switch),
    ("iaqua-onetouch-switch", _iaqua_onetouch_switch),
    ("iaqua-swc-boost-switch", _iaqua_swc_boost_switch),
]

# ---------------------------------------------------------------------------
# Light fixtures
# ---------------------------------------------------------------------------


def _iaqua_light_switch() -> LightFixture:
    system = make_system()
    system._parse_devices_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore
    data_on = {**IAQUA_LIGHT_SWITCH_OFF_DATA, "state": "1"}
    data_off = {**IAQUA_LIGHT_SWITCH_OFF_DATA}
    return LightFixture(
        device_on=IaquaLightSwitch(system, data_on),
        device_off=IaquaLightSwitch(system, data_off),
        expected_class=IaquaLightSwitch,
    )


def _iaqua_dimmable_light() -> LightFixture:
    system = make_system()
    system._parse_devices_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore
    data_on = {**IAQUA_DIMMABLE_LIGHT_ON_DATA}
    data_off = {**IAQUA_DIMMABLE_LIGHT_ON_DATA, "state": "0", "subtype": "0"}
    return LightFixture(
        device_on=IaquaDimmableLight(system, data_on),
        device_off=IaquaDimmableLight(system, data_off),
        expected_class=IaquaDimmableLight,
    )


def _iaqua_color_light_factory(
    subtype: str,
    cls: type,
) -> LightFixture:
    system = make_system()
    system._parse_devices_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore
    base = {**IAQUA_COLOR_LIGHT_OFF_DATA, "subtype": subtype}
    return LightFixture(
        device_on=cls(system, {**base, "state": "1"}),
        device_off=cls(system, {**base}),
        expected_class=cls,
    )


def _iaqua_color_light_jc() -> LightFixture:
    return _iaqua_color_light_factory("1", IaquaColorLightJC)


def _iaqua_color_light_sl() -> LightFixture:
    return _iaqua_color_light_factory("2", IaquaColorLightSL)


def _iaqua_color_light_cl() -> LightFixture:
    return _iaqua_color_light_factory("3", IaquaColorLightCL)


def _iaqua_color_light_jl() -> LightFixture:
    return _iaqua_color_light_factory("4", IaquaColorLightJL)


def _iaqua_color_light_ib() -> LightFixture:
    return _iaqua_color_light_factory("5", IaquaColorLightIB)


def _iaqua_color_light_hu() -> LightFixture:
    return _iaqua_color_light_factory("6", IaquaColorLightHU)


def _iaqua_icl_light() -> LightFixture:
    system = make_system()
    data_on: dict = {
        "zoneId": "1",
        "zoneName": "Pool Light",
        "zoneStatus": "on",
        "zoneColor": "6",
        "zoneColorVal": "Emerald Green",
        "dim_level": "100",
        "red_val": "255",
        "green_val": "128",
        "blue_val": "64",
        "white_val": "0",
    }
    data_off = {**data_on, "zoneStatus": "off"}
    return LightFixture(
        device_on=IaquaIclLight(system, data_on),
        device_off=IaquaIclLight(system, data_off),
        expected_class=IaquaIclLight,
    )


iaqua_light_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-light-switch", _iaqua_light_switch),
    ("iaqua-dimmable-light", _iaqua_dimmable_light),
    ("iaqua-color-light-jc", _iaqua_color_light_jc),
    ("iaqua-color-light-sl", _iaqua_color_light_sl),
    ("iaqua-color-light-cl", _iaqua_color_light_cl),
    ("iaqua-color-light-jl", _iaqua_color_light_jl),
    ("iaqua-color-light-ib", _iaqua_color_light_ib),
    ("iaqua-color-light-hu", _iaqua_color_light_hu),
    ("iaqua-icl-light", _iaqua_icl_light),
]

# ---------------------------------------------------------------------------
# Number fixtures
# ---------------------------------------------------------------------------


def _iaqua_set_point() -> NumberFixture:
    system = make_system()
    system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
    system._parse_home_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore

    pool_set_point = {**IAQUA_POOL_SET_POINT_DATA}
    device = IaquaSetPoint(system, pool_set_point)
    system.devices = {"pool_set_point": device}

    return NumberFixture(device=device, expected_class=IaquaSetPoint)


def _iaqua_swc_set_point() -> NumberFixture:
    system = make_system()
    device = IaquaSwcSetPoint(system, {**IAQUA_SWC_POOL_SET_POINT_DATA})
    system.devices = {"swc_pool_set_point": device}

    return NumberFixture(device=device, expected_class=IaquaSwcSetPoint)


iaqua_number_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-set-point", _iaqua_set_point),
    ("iaqua-swc-set-point", _iaqua_swc_set_point),
]

# ---------------------------------------------------------------------------
# Climate fixtures
# ---------------------------------------------------------------------------


def _iaqua_climate() -> ClimateFixture:
    system = make_system()
    system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
    system._parse_home_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore

    pool_set_point_dev = IaquaSetPoint(system, {**IAQUA_POOL_SET_POINT_DATA})
    pool_temp_dev = IaquaSensor(system, {**IAQUA_POOL_TEMP_DATA})

    pool_heater_on = {**IAQUA_HEATER_OFF_DATA, "state": "1"}
    pool_heater_on_dev = IaquaHeater(system, pool_heater_on)

    system.devices = {
        "pool_set_point": pool_set_point_dev,
        "pool_heater": pool_heater_on_dev,
        "pool_temp": pool_temp_dev,
    }

    device_on = IaquaClimate(system, {**IAQUA_CLIMATE_DATA})
    system.devices["pool_thermostat"] = device_on

    # For device_off, separate system with heater off
    system_off = make_system()
    system_off.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
    system_off._parse_home_response = lambda *a, **kw: None  # type: ignore[method-assign]  # ty: ignore

    pool_set_point_off_dev = IaquaSetPoint(
        system_off, {**IAQUA_POOL_SET_POINT_DATA}
    )
    pool_temp_off_dev = IaquaSensor(system_off, {**IAQUA_POOL_TEMP_DATA})
    pool_heater_off_dev = IaquaHeater(system_off, {**IAQUA_HEATER_OFF_DATA})

    system_off.devices = {
        "pool_set_point": pool_set_point_off_dev,
        "pool_heater": pool_heater_off_dev,
        "pool_temp": pool_temp_off_dev,
    }

    device_off = IaquaClimate(system_off, {**IAQUA_CLIMATE_DATA})
    system_off.devices["pool_thermostat"] = device_off

    return ClimateFixture(
        device_on=device_on,
        device_off=device_off,
        supports_fahrenheit=True,
        expected_class=IaquaClimate,
    )


iaqua_climate_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-climate", _iaqua_climate),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _iaqua_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 123456,
        "serial_number": "SN123456",
        "created_at": "2017-09-23T01:00:08.000Z",
        "updated_at": "2017-09-23T01:00:08.000Z",
        "name": "Pool",
        "device_type": "iaqua",
        "owner_id": None,
        "updating": False,
        "firmware_version": None,
        "target_firmware_version": None,
        "update_firmware_start_at": None,
        "last_activity_at": None,
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=IaquaSystem,
        expected_online_status=None,
        refresh_response={
            "home_screen": [
                {"status": "Online", "system_type": "5", "temp_scale": "F"}
            ],
            "onetouch": "false",
            "devices_screen": [{"status": "Online"}, {}, {}],
        },
    )


iaqua_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("iaqua-system", _iaqua_system),
]

# iaqua does not implement this device type.
iaqua_fan_factories: list[tuple[str, Callable[[], Any]]] = []
