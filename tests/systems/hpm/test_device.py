from __future__ import annotations

from typing import Any, cast

from iaqualink.client import AqualinkClient
from iaqualink.systems.hpm.device import (
    HpmAirTemperature,
    HpmAttributeSensor,
    HpmCoolingPriority,
    HpmDevice,
    HpmHeatPump,
    HpmMode,
    HpmOperatingState,
    HpmOperatingStatusSensor,
    HpmPerformanceMode,
    HpmStandbyReason,
    HpmStandbyReasonSensor,
    HpmWaterFlow,
    HpmWaterTemperature,
)
from iaqualink.systems.hpm.system import HpmSystem


def _make_system() -> HpmSystem:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {"serial_number": "JX00000000", "device_type": "hpm"}
    return HpmSystem(client, data=data)


def _data(**kwargs: Any) -> dict[str, Any]:
    # Keeps ty from inferring a narrow structural type for an inline
    # mixed-value literal, which then doesn't satisfy DeviceData.
    return dict(kwargs)


class TestHpmDeviceDispatch:
    def test_heatpump(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(
            system, _data(name="heatpump", state=1, tsp=28)
        )
        assert isinstance(dev, HpmHeatPump)

    def test_mode(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(system, _data(name="mode", st=0))
        assert isinstance(dev, HpmMode)

    def test_cooling_priority(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(system, _data(name="cooling_priority", cl=0))
        assert isinstance(dev, HpmCoolingPriority)

    def test_status(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(system, _data(name="status", status=1))
        assert isinstance(dev, HpmOperatingStatusSensor)

    def test_reason(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(system, _data(name="reason", reason=0))
        assert isinstance(dev, HpmStandbyReasonSensor)

    def test_water_temp(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(
            system,
            _data(
                name="water_temp", type="water", state="connected", value=30.4
            ),
        )
        assert isinstance(dev, HpmWaterTemperature)

    def test_air_temp(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(
            system,
            _data(name="air_temp", type="air", state="connected", value=28.6),
        )
        assert isinstance(dev, HpmAirTemperature)

    def test_water_flow(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(system, _data(name="water_flow", wf=1))
        assert isinstance(dev, HpmWaterFlow)

    def test_unrecognized_falls_back_to_attribute_sensor(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(
            system, _data(name="some_future_field", state=42)
        )
        assert isinstance(dev, HpmAttributeSensor)

    def test_manufacturer_and_model(self) -> None:
        system = _make_system()
        dev = HpmDevice.from_data(system, _data(name="status", status=1))
        assert dev.manufacturer == "Fluidra"
        assert dev.model == "Heat Pump Module"


class TestHpmProbeSensor:
    def test_value_when_connected(self) -> None:
        system = _make_system()
        dev = cast(
            HpmWaterTemperature,
            HpmDevice.from_data(
                system,
                _data(
                    name="water_temp",
                    type="water",
                    state="connected",
                    value=30.4,
                ),
            ),
        )
        assert dev.value == 30.4

    def test_value_none_when_disconnected(self) -> None:
        system = _make_system()
        dev = cast(
            HpmWaterTemperature,
            HpmDevice.from_data(
                system,
                _data(
                    name="water_temp",
                    type="water",
                    state="disconnected",
                    value=30.4,
                ),
            ),
        )
        assert dev.value is None


class TestHpmOperatingStatusSensor:
    def test_value_enum_translation(self) -> None:
        system = _make_system()
        dev = cast(
            HpmOperatingStatusSensor,
            HpmDevice.from_data(system, _data(name="status", status=2)),
        )
        assert dev.value == 2
        assert dev.value_translated == HpmOperatingState.HEATING.name

    def test_value_none_when_absent(self) -> None:
        system = _make_system()
        dev = cast(
            HpmOperatingStatusSensor,
            HpmDevice.from_data(system, _data(name="status")),
        )
        assert dev.value is None


class TestHpmStandbyReasonSensor:
    def test_value_enum_translation(self) -> None:
        system = _make_system()
        dev = cast(
            HpmStandbyReasonSensor,
            HpmDevice.from_data(system, _data(name="reason", reason=1)),
        )
        assert dev.value == 1
        assert dev.value_translated == HpmStandbyReason.NO_FLOW.name


class TestHpmMode:
    def test_current_option(self) -> None:
        system = _make_system()
        dev = cast(
            HpmMode, HpmDevice.from_data(system, _data(name="mode", st=2))
        )
        assert dev.current_option == HpmPerformanceMode.SMART.name.lower()

    def test_options(self) -> None:
        system = _make_system()
        dev = cast(
            HpmMode, HpmDevice.from_data(system, _data(name="mode", st=0))
        )
        assert dev.options == ["boost", "silent", "smart"]

    async def test_select_option_sends_correct_value(self) -> None:
        system = _make_system()
        dev = cast(
            HpmMode, HpmDevice.from_data(system, _data(name="mode", st=0))
        )
        sent: list[int] = []

        async def fake_set_mode(mode: int) -> None:
            sent.append(mode)

        system.set_mode = fake_set_mode  # type: ignore[method-assign]  # ty: ignore
        await dev.select_option("silent")
        assert sent == [HpmPerformanceMode.SILENT.value]


class TestHpmHeatPump:
    def test_current_temperature_reads_water_sensor(self) -> None:
        system = _make_system()
        water = HpmDevice.from_data(
            system,
            _data(
                name="water_temp", type="water", state="connected", value=30.4
            ),
        )
        heatpump = cast(
            HpmHeatPump,
            HpmDevice.from_data(
                system, _data(name="heatpump", state=1, tsp=28)
            ),
        )
        system.devices = {"water_temp": water}
        assert heatpump.current_temperature == "30.4"

    def test_current_temperature_none_without_sensor(self) -> None:
        system = _make_system()
        heatpump = cast(
            HpmHeatPump,
            HpmDevice.from_data(
                system, _data(name="heatpump", state=1, tsp=28)
            ),
        )
        system.devices = {}
        assert heatpump.current_temperature is None
