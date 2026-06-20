from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.systems.zs500.device import (
    ZS500_TEMP_CELSIUS_HIGH,
    ZS500_TEMP_CELSIUS_LOW,
    Zs500Climate,
    Zs500CompressorSpeedSensor,
    Zs500CoolingSwitch,
    Zs500Device,
    Zs500ErrorBinarySensor,
    Zs500HeatingPrioritySwitch,
    Zs500ModeSelect,
    Zs500StandbyReasonSensor,
    Zs500TemperatureSensor,
)
from iaqualink.systems.zs500.system import Zs500System


def make_system() -> Zs500System:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "SN123456",
        "device_type": "zs500",
        "name": "Pool Heat Pump",
    }
    return Zs500System(client, data=data)


def from_data(system: Zs500System, data: dict[str, Any]) -> Zs500Device:
    return Zs500Device.from_data(system, data)


def make_climate(
    system: Zs500System, *, state: int, tsp: int = 250
) -> Zs500Climate:
    data: dict[str, Any] = {"name": "climate", "state": state, "tsp": tsp}
    return cast(Zs500Climate, from_data(system, data))


def make_mode(system: Zs500System, *, st: int) -> Zs500ModeSelect:
    data: dict[str, Any] = {"name": "mode", "st": st}
    return cast(Zs500ModeSelect, from_data(system, data))


def make_cooling(system: Zs500System, *, cl: int) -> Zs500CoolingSwitch:
    data: dict[str, Any] = {"name": "cooling", "cl": cl}
    return cast(Zs500CoolingSwitch, from_data(system, data))


def make_heating_priority(
    system: Zs500System, *, hp: int
) -> Zs500HeatingPrioritySwitch:
    data: dict[str, Any] = {"name": "heating_priority", "hp": hp}
    return cast(Zs500HeatingPrioritySwitch, from_data(system, data))


def make_temperature_sensor(
    system: Zs500System, *, name: str, value: int | None
) -> Zs500TemperatureSensor:
    data: dict[str, Any] = {"name": name}
    if value is not None:
        data["value"] = value
    return cast(Zs500TemperatureSensor, from_data(system, data))


def make_compressor_speed(
    system: Zs500System, *, cmpr_spd: int
) -> Zs500CompressorSpeedSensor:
    data: dict[str, Any] = {"name": "compressor_speed", "cmprSpd": cmpr_spd}
    return cast(Zs500CompressorSpeedSensor, from_data(system, data))


def make_standby_reason(
    system: Zs500System, *, reason: int | None
) -> Zs500StandbyReasonSensor:
    data: dict[str, Any] = {"name": "standby_reason"}
    if reason is not None:
        data["reason"] = reason
    return cast(Zs500StandbyReasonSensor, from_data(system, data))


def make_error(
    system: Zs500System, *, error_code: str | None
) -> Zs500ErrorBinarySensor:
    data: dict[str, Any] = {"name": "error"}
    if error_code is not None:
        data["errorCode"] = error_code
    return cast(Zs500ErrorBinarySensor, from_data(system, data))


class TestZs500DeviceFromData:
    @pytest.mark.parametrize(
        ("name", "expected_class"),
        [
            ("climate", Zs500Climate),
            ("mode", Zs500ModeSelect),
            ("cooling", Zs500CoolingSwitch),
            ("heating_priority", Zs500HeatingPrioritySwitch),
            ("water_temp", Zs500TemperatureSensor),
            ("air_temp", Zs500TemperatureSensor),
            ("compressor_speed", Zs500CompressorSpeedSensor),
            ("standby_reason", Zs500StandbyReasonSensor),
            ("error", Zs500ErrorBinarySensor),
        ],
    )
    def test_dispatch(self, name: str, expected_class: type) -> None:
        system = make_system()
        dev = from_data(system, {"name": name})
        assert isinstance(dev, expected_class)

    def test_unknown_name_raises(self) -> None:
        system = make_system()
        with pytest.raises(ValueError, match="Unknown zs500 device name"):
            from_data(system, {"name": "bogus"})

    def test_manufacturer_and_model(self) -> None:
        system = make_system()
        dev = make_cooling(system, cl=0)
        assert dev.manufacturer == "Zodiac"
        assert dev.model == "CoolingSwitch"

    def test_label(self) -> None:
        system = make_system()
        dev = make_heating_priority(system, hp=0)
        assert dev.label == "Heating Priority"


class TestZs500Climate:
    def test_is_on_true(self) -> None:
        system = make_system()
        assert make_climate(system, state=2).is_on is True

    def test_is_on_false(self) -> None:
        system = make_system()
        assert make_climate(system, state=0).is_on is False

    def test_temperature_unit(self) -> None:
        system = make_system()
        assert make_climate(system, state=2).temperature_unit == "C"

    def test_current_temperature_none_without_sibling(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        assert climate.current_temperature is None

    def test_current_temperature_from_sibling(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        system.devices["water_temp"] = make_temperature_sensor(
            system, name="water_temp", value=230
        )
        assert climate.current_temperature == "23.0"

    def test_target_temperature(self) -> None:
        system = make_system()
        assert (
            make_climate(system, state=2, tsp=250).target_temperature == "25.0"
        )

    def test_min_max_temp(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        assert climate.min_temp == ZS500_TEMP_CELSIUS_LOW
        assert climate.max_temp == ZS500_TEMP_CELSIUS_HIGH

    async def test_turn_on_payload(self) -> None:
        system = make_system()
        climate = make_climate(system, state=0)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await climate.turn_on()
        mock_set.assert_awaited_once_with({"state": 1})

    async def test_turn_on_noop(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await climate.turn_on()
        mock_set.assert_not_awaited()

    async def test_turn_off_payload(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await climate.turn_off()
        mock_set.assert_awaited_once_with({"state": 0})

    async def test_set_temperature_payload(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await climate.set_temperature(30)
        mock_set.assert_awaited_once_with({"tsp": 300})

    async def test_set_temperature_too_low(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        with pytest.raises(AqualinkInvalidParameterException):
            await climate.set_temperature(ZS500_TEMP_CELSIUS_LOW - 1)

    async def test_set_temperature_too_high(self) -> None:
        system = make_system()
        climate = make_climate(system, state=2)
        with pytest.raises(AqualinkInvalidParameterException):
            await climate.set_temperature(ZS500_TEMP_CELSIUS_HIGH + 1)


class TestZs500ModeSelect:
    def test_current_option(self) -> None:
        system = make_system()
        assert make_mode(system, st=2).current_option == "Smart"

    def test_options(self) -> None:
        system = make_system()
        assert make_mode(system, st=0).options == ["Boost", "Silent", "Smart"]

    async def test_select_option_payload(self) -> None:
        system = make_system()
        mode = make_mode(system, st=0)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await mode.select_option("Silent")
        mock_set.assert_awaited_once_with({"st": 1})

    async def test_select_invalid_option_raises(self) -> None:
        system = make_system()
        mode = make_mode(system, st=0)
        with pytest.raises(AqualinkInvalidParameterException):
            await mode.select_option("Eco")


class TestZs500CoolingSwitch:
    def test_is_on_false(self) -> None:
        system = make_system()
        assert make_cooling(system, cl=0).is_on is False

    def test_is_on_true(self) -> None:
        system = make_system()
        assert make_cooling(system, cl=1).is_on is True

    async def test_turn_on_payload(self) -> None:
        system = make_system()
        sw = make_cooling(system, cl=0)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await sw.turn_on()
        mock_set.assert_awaited_once_with({"cl": 1})

    async def test_turn_off_payload(self) -> None:
        system = make_system()
        sw = make_cooling(system, cl=1)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await sw.turn_off()
        mock_set.assert_awaited_once_with({"cl": 0})


class TestZs500HeatingPrioritySwitch:
    def test_is_on_false(self) -> None:
        system = make_system()
        assert make_heating_priority(system, hp=0).is_on is False

    def test_is_on_true(self) -> None:
        system = make_system()
        assert make_heating_priority(system, hp=1).is_on is True

    async def test_turn_on_payload(self) -> None:
        system = make_system()
        sw = make_heating_priority(system, hp=0)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await sw.turn_on()
        mock_set.assert_awaited_once_with({"hp": 1})

    async def test_turn_off_payload(self) -> None:
        system = make_system()
        sw = make_heating_priority(system, hp=1)
        with patch.object(system, "set_desired", new=AsyncMock()) as mock_set:
            await sw.turn_off()
        mock_set.assert_awaited_once_with({"hp": 0})


class TestZs500Sensors:
    def test_temperature_sensor_value(self) -> None:
        system = make_system()
        dev = make_temperature_sensor(system, name="water_temp", value=230)
        assert dev.value == "23.0"
        assert dev.unit_of_measurement == "C"

    def test_temperature_sensor_missing_value(self) -> None:
        system = make_system()
        dev = make_temperature_sensor(system, name="air_temp", value=None)
        assert dev.value == ""

    def test_compressor_speed_sensor(self) -> None:
        system = make_system()
        dev = make_compressor_speed(system, cmpr_spd=62)
        assert dev.value == "62"
        assert dev.unit_of_measurement == "%"

    def test_standby_reason_sensor_translation(self) -> None:
        system = make_system()
        dev = make_standby_reason(system, reason=3)
        assert dev.value == "3"
        assert dev.value_translated == "TEMPERATURE_BUFFER"

    def test_standby_reason_sensor_default(self) -> None:
        system = make_system()
        dev = make_standby_reason(system, reason=None)
        assert dev.value == "0"
        assert dev.value_translated == "NONE"


class TestZs500ErrorBinarySensor:
    def test_is_on_false_when_no_error(self) -> None:
        system = make_system()
        assert make_error(system, error_code="0").is_on is False

    def test_is_on_true_when_error_present(self) -> None:
        system = make_system()
        assert make_error(system, error_code="12").is_on is True

    def test_is_on_false_when_field_missing(self) -> None:
        system = make_system()
        assert make_error(system, error_code=None).is_on is False
