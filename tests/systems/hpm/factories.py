"""HPM device factories for conformance tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkSelect,
    AqualinkSensor,
    AqualinkSwitch,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.hpm.device import (
    HpmAttributeSensor,
    HpmCoolingPriority,
    HpmDevice,
    HpmHeatPump,
    HpmMode,
    HpmOperatingStatusSensor,
    HpmStandbyReasonSensor,
    HpmWaterFlow,
    HpmWaterTemperature,
)
from iaqualink.systems.hpm.system import HpmSystem

from ...conformance.fixtures import (
    BinarySensorFixture,
    ClimateFixture,
    DeviceFixture,
    SelectFixture,
    SensorFixture,
    SwitchFixture,
    SystemFixture,
)

# ---------------------------------------------------------------------------
# Shared test data constants
# ---------------------------------------------------------------------------

HPM_SYSTEM_DATA: dict[str, Any] = {
    "serial_number": "JX00000000",
    "device_type": "hpm",
}
HPM_DEVICE_DATA: dict[str, Any] = {"name": "test_device", "state": 1}
HPM_REASON_DATA: dict[str, Any] = {"name": "reason", "reason": 0}
HPM_HEATPUMP_ON_DATA: dict[str, Any] = {
    "name": "heatpump",
    "state": 1,
    "tsp": 28,
}
HPM_WATER_TEMP_DATA: dict[str, Any] = {
    "name": "water_temp",
    "type": "water",
    "state": "connected",
    "value": 30.4,
}


def make_system() -> HpmSystem:
    client = AqualinkClient("foo", "bar")
    return HpmSystem(client, data=HPM_SYSTEM_DATA)


def _data(**kwargs: Any) -> dict[str, Any]:
    # Keeps ty from inferring a narrow structural type for an inline
    # mixed-value literal, which then doesn't satisfy DeviceData.
    return dict(kwargs)


# ---------------------------------------------------------------------------
# Device fixtures
# ---------------------------------------------------------------------------


def _hpm_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=HpmDevice(system, {**HPM_DEVICE_DATA}), expected_class=HpmDevice
    )


def _hpm_reason_sensor_device() -> DeviceFixture:
    system = make_system()
    return DeviceFixture(
        device=HpmDevice.from_data(system, {**HPM_REASON_DATA}),
        expected_class=HpmStandbyReasonSensor,
    )


hpm_device_factories: list[tuple[str, Callable[[], Any]]] = [
    ("hpm-device", _hpm_device),
    ("hpm-reason-sensor-device", _hpm_reason_sensor_device),
]

# ---------------------------------------------------------------------------
# Sensor fixtures
# ---------------------------------------------------------------------------


def _hpm_operating_status_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            HpmDevice.from_data(system, _data(name="status", status=2)),
        ),
        expected_class=HpmOperatingStatusSensor,
    )


def _hpm_water_temperature_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            HpmDevice.from_data(system, {**HPM_WATER_TEMP_DATA}),
        ),
        expected_class=HpmWaterTemperature,
    )


def _hpm_unrecognized_attribute_sensor() -> SensorFixture:
    system = make_system()
    return SensorFixture(
        device=cast(
            AqualinkSensor,
            HpmDevice.from_data(
                system, _data(name="some_future_field", state=42)
            ),
        ),
        expected_class=HpmAttributeSensor,
    )


hpm_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("hpm-operating-status-sensor", _hpm_operating_status_sensor),
    ("hpm-water-temperature-sensor", _hpm_water_temperature_sensor),
    ("hpm-unrecognized-attribute-sensor", _hpm_unrecognized_attribute_sensor),
]

# ---------------------------------------------------------------------------
# Binary sensor fixtures
# ---------------------------------------------------------------------------


def _hpm_water_flow() -> BinarySensorFixture:
    system = make_system()
    return BinarySensorFixture(
        device_on=cast(
            AqualinkBinarySensor,
            HpmDevice.from_data(system, _data(name="water_flow", wf=1)),
        ),
        device_off=cast(
            AqualinkBinarySensor,
            HpmDevice.from_data(system, _data(name="water_flow", wf=0)),
        ),
        expected_class=HpmWaterFlow,
    )


hpm_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = [
    ("hpm-water-flow", _hpm_water_flow),
]

# ---------------------------------------------------------------------------
# Switch fixtures
# ---------------------------------------------------------------------------


def _hpm_cooling_priority() -> SwitchFixture:
    system = make_system()
    data_on = _data(name="cooling_priority", cl=1)
    data_off = _data(name="cooling_priority", cl=0)
    return SwitchFixture(
        device_on=cast(AqualinkSwitch, HpmDevice.from_data(system, data_on)),
        device_off=cast(AqualinkSwitch, HpmDevice.from_data(system, data_off)),
        expected_class=HpmCoolingPriority,
    )


hpm_switch_factories: list[tuple[str, Callable[[], Any]]] = [
    ("hpm-cooling-priority", _hpm_cooling_priority),
]

# ---------------------------------------------------------------------------
# Select fixtures
# ---------------------------------------------------------------------------


def _hpm_mode() -> SelectFixture:
    system = make_system()
    return SelectFixture(
        device=cast(
            AqualinkSelect,
            HpmDevice.from_data(system, _data(name="mode", st=2)),
        ),
        expected_class=HpmMode,
    )


hpm_select_factories: list[tuple[str, Callable[[], Any]]] = [
    ("hpm-mode", _hpm_mode),
]

# ---------------------------------------------------------------------------
# Climate fixtures
# ---------------------------------------------------------------------------


def _hpm_climate() -> ClimateFixture:
    system = make_system()

    water_temp_dev = HpmDevice.from_data(system, {**HPM_WATER_TEMP_DATA})

    heatpump_off_data = _data(**{**HPM_HEATPUMP_ON_DATA, "state": 0})

    device_on = cast(
        HpmHeatPump, HpmDevice.from_data(system, {**HPM_HEATPUMP_ON_DATA})
    )
    device_off = cast(
        HpmHeatPump, HpmDevice.from_data(system, heatpump_off_data)
    )

    system.devices = {
        "heatpump": device_on,
        "water_temp": water_temp_dev,
    }

    return ClimateFixture(
        device_on=device_on,
        device_off=device_off,
        supports_fahrenheit=False,
        expected_class=HpmHeatPump,
    )


hpm_climate_factories: list[tuple[str, Callable[[], Any]]] = [
    ("hpm-climate", _hpm_climate),
]

# ---------------------------------------------------------------------------
# System fixtures
# ---------------------------------------------------------------------------


def _hpm_system() -> SystemFixture:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "JX00000000",
        "device_type": "hpm",
        "name": "Heat_Pump-1",
    }
    system = AqualinkSystem.from_data(client, data=data)
    return SystemFixture(
        system=system,
        expected_class=HpmSystem,
        expected_online_status=SystemStatus.CONNECTED,
        refresh_response={
            "state": {"reported": {"aws": {"status": "connected"}}}
        },
    )


hpm_system_factories: list[tuple[str, Callable[[], Any]]] = [
    ("hpm-system", _hpm_system),
]

# HPM does not implement these device types.
hpm_light_factories: list[tuple[str, Callable[[], Any]]] = []
hpm_number_factories: list[tuple[str, Callable[[], Any]]] = []
hpm_fan_factories: list[tuple[str, Callable[[], Any]]] = []
