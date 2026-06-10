from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from iaqualink.exception import AqualinkOperationNotSupportedException
from iaqualink.systems.tcx.device import (
    TcxAuxSwitch,
    TcxClimate,
    TcxDevice,
    TcxFeatureCircuit,
    TcxFilterPump,
    TcxSolarSensor,
    TcxVariableSpeedPump,
    TcxWaterSensor,
    TcxZigbeeSwitch,
)

from .factories import make_system

VSP_DATA: dict[str, Any] = {
    "name": "ecm0",
    "cmdSpd": 2700,
    "minSpd": 1000,
    "maxSpd": 3450,
    "st": 1,
    "spdList": [
        {"name": "Low", "speed": 1000},
        {"name": "Med", "speed": 2000},
        {"name": "High", "speed": 3450},
    ],
}


class TestTcxVariableSpeedPumpOnOff:
    def test_is_on_true(self) -> None:
        data: dict[str, Any] = {**VSP_DATA, "st": 1}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        data: dict[str, Any] = {**VSP_DATA, "st": 0}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.is_on is False

    async def test_turn_on_not_supported(self) -> None:
        sut = TcxVariableSpeedPump(make_system(), {**VSP_DATA})
        with pytest.raises(AqualinkOperationNotSupportedException):
            await sut.turn_on()

    async def test_turn_off_not_supported(self) -> None:
        sut = TcxVariableSpeedPump(make_system(), {**VSP_DATA})
        with pytest.raises(AqualinkOperationNotSupportedException):
            await sut.turn_off()


class TestTcxVariableSpeedPumpPresets:
    def test_supports_presets_true(self) -> None:
        sut = TcxVariableSpeedPump(make_system(), {**VSP_DATA})
        assert sut.supports_presets is True

    def test_supports_presets_false_when_empty(self) -> None:
        data: dict[str, Any] = {**VSP_DATA, "spdList": []}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.supports_presets is False

    def test_preset_modes(self) -> None:
        sut = TcxVariableSpeedPump(make_system(), {**VSP_DATA})
        assert sut.preset_modes == ["Low", "Med", "High"]

    def test_preset_mode_matches_cmd_spd(self) -> None:
        data: dict[str, Any] = {**VSP_DATA, "cmdSpd": 2000}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.preset_mode == "Med"

    def test_preset_mode_none_when_no_match(self) -> None:
        data: dict[str, Any] = {**VSP_DATA, "cmdSpd": 2700}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.preset_mode is None

    def test_preset_mode_none_when_cmd_spd_missing(self) -> None:
        data = {k: v for k, v in VSP_DATA.items() if k != "cmdSpd"}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.preset_mode is None

    async def test_set_preset_mode_sends_speed(self) -> None:
        sut = TcxVariableSpeedPump(make_system(), {**VSP_DATA})
        with patch.object(
            sut.system, "set_vsp_speed", new_callable=AsyncMock
        ) as mock_set:
            await sut.set_preset_mode("High")
        mock_set.assert_awaited_once_with(3450)


class TestTcxVariableSpeedPumpPercentage:
    @pytest.mark.parametrize(
        "cmd_spd,min_spd,max_spd,expected",
        [
            (2700, 1000, 3450, 69),
            (1000, 1000, 3450, 0),
            (3450, 1000, 3450, 100),
        ],
        ids=["mid-range", "at-min", "at-max"],
    )
    def test_percentage(
        self, cmd_spd: int, min_spd: int, max_spd: int, expected: int
    ) -> None:
        data: dict[str, Any] = {
            **VSP_DATA,
            "cmdSpd": cmd_spd,
            "minSpd": min_spd,
            "maxSpd": max_spd,
        }
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.percentage == expected

    def test_percentage_none_when_cmd_spd_missing(self) -> None:
        data = {k: v for k, v in VSP_DATA.items() if k != "cmdSpd"}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.percentage is None

    def test_percentage_none_when_min_equals_max(self) -> None:
        data: dict[str, Any] = {**VSP_DATA, "minSpd": 1000, "maxSpd": 1000}
        sut = TcxVariableSpeedPump(make_system(), data)
        assert sut.percentage is None

    async def test_set_percentage_sends_mapped_speed(self) -> None:
        sut = TcxVariableSpeedPump(make_system(), {**VSP_DATA})
        with patch.object(
            sut.system, "set_vsp_speed", new_callable=AsyncMock
        ) as mock_set:
            await sut.set_percentage(50)
        mock_set.assert_awaited_once_with(2225)


class TestTcxFilterPumpLabel:
    def test_label_uses_fr(self) -> None:
        sut = TcxFilterPump(make_system(), {"name": "filt0", "fr": "Pump A"})
        assert sut.label == "Pump A"

    def test_label_falls_back(self) -> None:
        sut = TcxFilterPump(make_system(), {"name": "filt0"})
        assert sut.label == "Filter Pump"


class TestTcxAuxSwitchLabel:
    def test_label_uses_fr(self) -> None:
        sut = TcxAuxSwitch(make_system(), {"name": "aux0", "fr": "Waterfall"})
        assert sut.label == "Waterfall"

    def test_label_falls_back_to_name(self) -> None:
        sut = TcxAuxSwitch(make_system(), {"name": "aux0"})
        assert sut.label == "AUX0"


class TestTcxWaterSensorStatus:
    def test_value_when_valid(self) -> None:
        data: dict[str, Any] = {"name": "water", "value": 82, "us": 1}
        sut = TcxWaterSensor(make_system(), data)
        assert sut.value == "82"

    def test_value_empty_when_not_valid(self) -> None:
        data: dict[str, Any] = {"name": "water", "value": 82, "us": 2}
        sut = TcxWaterSensor(make_system(), data)
        assert sut.value == ""


class TestTcxSolarSensorStatus:
    def test_value_when_present(self) -> None:
        data: dict[str, Any] = {"name": "solar", "value": 105, "us": 1}
        sut = TcxSolarSensor(make_system(), data)
        assert sut.value == "105"

    def test_value_empty_when_not_present(self) -> None:
        data: dict[str, Any] = {"name": "solar", "value": 105, "us": 4}
        sut = TcxSolarSensor(make_system(), data)
        assert sut.value == ""


class TestTcxClimateLabel:
    def test_label_uses_body_name(self) -> None:
        sut = TcxClimate(make_system(), {"name": "TspBdy0", "bodyName": "Pool"})
        assert sut.label == "Pool"

    def test_label_falls_back_when_no_body_name(self) -> None:
        sut = TcxClimate(make_system(), {"name": "TspBdy0"})
        assert sut.label == "Heater"

    def test_current_temperature_none_without_water_sensor(self) -> None:
        sut = TcxClimate(make_system(), {"name": "TspBdy0"})
        assert sut.current_temperature is None


class TestTcxFromDataDispatchTspBdy0:
    def test_wire_name_does_not_break_dispatch(self) -> None:
        """`TspBdy0.name` ("Pool") must not collide with the `TspBdy0` dispatch key."""
        system = make_system()
        data: dict[str, Any] = {
            "name": "TspBdy0",
            "bodyName": "Pool",
            "heatEnabled": True,
        }
        sut = TcxDevice.from_data(system, data)
        assert isinstance(sut, TcxClimate)
        assert sut.name == "TspBdy0"
        assert sut.label == "Pool"


class TestTcxFeatureCircuitLabel:
    def test_label_uses_fr(self) -> None:
        sut = TcxFeatureCircuit(
            make_system(), {"name": "feaCircuit0", "fr": "Spa Jets"}
        )
        assert sut.label == "Spa Jets"

    def test_label_falls_back_to_index(self) -> None:
        sut = TcxFeatureCircuit(make_system(), {"name": "feaCircuit2"})
        assert sut.label == "Feature Circuit 2"


class TestTcxZigbeeSwitchLabel:
    def test_label_uses_fr(self) -> None:
        sut = TcxZigbeeSwitch(
            make_system(), {"name": "zig_aabbccdd", "fr": "Pool Light"}
        )
        assert sut.label == "Pool Light"

    def test_label_falls_back_to_name(self) -> None:
        sut = TcxZigbeeSwitch(make_system(), {"name": "zig_aabbccdd"})
        assert sut.label == "ZigBee aabbccdd"
