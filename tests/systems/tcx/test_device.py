from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from iaqualink.exception import AqualinkOperationNotSupportedException
from iaqualink.systems.tcx.device import (
    TcxAuxSwitch,
    TcxChlorinatorBoost,
    TcxClimate,
    TcxDevice,
    TcxFeatureCircuit,
    TcxFilterPump,
    TcxJvaSwitch,
    TcxSolarSensor,
    TcxSpeedSensor,
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
        # Wire value is tenths of a degree (live-confirmed) -> 82.0.
        data: dict[str, Any] = {"name": "water", "value": 820, "us": 1}
        sut = TcxWaterSensor(make_system(), data)
        assert sut.value == "82.0"

    def test_value_empty_when_not_valid(self) -> None:
        data: dict[str, Any] = {"name": "water", "value": 820, "us": 2}
        sut = TcxWaterSensor(make_system(), data)
        assert sut.value == ""


class TestTcxSolarSensorStatus:
    def test_value_when_present(self) -> None:
        # Wire value is tenths of a degree (live-confirmed) -> 105.0.
        data: dict[str, Any] = {"name": "solar", "value": 1050, "us": 1}
        sut = TcxSolarSensor(make_system(), data)
        assert sut.value == "105.0"

    def test_value_empty_when_not_present(self) -> None:
        data: dict[str, Any] = {"name": "solar", "value": 1050, "us": 4}
        sut = TcxSolarSensor(make_system(), data)
        assert sut.value == ""


class TestTcxSpeedSensor:
    # RPM speed fields on filt0/ecm0 not otherwise surfaced (only used
    # internally for TcxVariableSpeedPump's percentage/preset math) —
    # exposed as read-only sensors, no /10 scaling (unlike temperature).

    def test_value_and_label(self) -> None:
        data: dict[str, Any] = {
            "name": "ecm0_frzSpd",
            "label": "Fan Freeze-Protect Speed",
            "value": 2500,
        }
        sut = TcxSpeedSensor(make_system(), data)
        assert sut.value == "2500"
        assert sut.label == "Fan Freeze-Protect Speed"

    def test_label_falls_back_to_name_without_label_field(self) -> None:
        sut = TcxSpeedSensor(make_system(), {"name": "ecm0_qcSpd"})
        assert sut.label == "ecm0_qcSpd"

    def test_value_empty_when_absent(self) -> None:
        sut = TcxSpeedSensor(make_system(), {"name": "ecm0_prmSpd"})
        assert sut.value == ""

    @pytest.mark.parametrize(
        "name",
        [
            "filt0_manSpd",
            "ecm0_manSpd",
            "ecm0_frzSpd",
            "ecm0_prmSpd",
            "ecm0_qcSpd",
        ],
    )
    def test_from_data_dispatches_to_speed_sensor(self, name: str) -> None:
        data: dict[str, Any] = {"name": name, "value": 1000}
        sut = TcxDevice.from_data(make_system(), data)
        assert isinstance(sut, TcxSpeedSensor)


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


class TestTcxClimateTemperatureScaling:
    # Wire temperature fields are tenths of a degree (live-confirmed against
    # real hardware — see _wire_temp_to_display in device.py).

    def test_target_temperature_scales_wire_value(self) -> None:
        data: dict[str, Any] = {"name": "TspBdy0", "waterTempSet": 283}
        sut = TcxClimate(make_system(), data)
        assert sut.target_temperature == "28.3"

    def test_current_temperature_scales_via_water_sensor(self) -> None:
        system = make_system()
        water_data: dict[str, Any] = {"name": "water", "value": 283, "us": 1}
        system.devices["water"] = TcxWaterSensor(system, water_data)
        sut = TcxClimate(system, {"name": "TspBdy0"})
        assert sut.current_temperature == "28.3"


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
            make_system(), {"name": "auxz0", "fr": "Pool Light"}
        )
        assert sut.label == "Pool Light"

    def test_label_falls_back_to_name(self) -> None:
        sut = TcxZigbeeSwitch(make_system(), {"name": "auxz0"})
        assert sut.label == "ZigBee 0"


# ---------------------------------------------------------------------------
# Switch/climate on-off dispatch to WS command methods.
#
# These devices are excluded from the generic switch/climate conformance
# suites (tests/conformance/test_switch.py, test_climate.py) because those
# assert turn_on/turn_off make an HTTP request via respx — TCX writes now go
# over WS, which respx can't intercept. Covered directly here instead,
# mirroring the pattern already used for TcxVariableSpeedPump above.
# ---------------------------------------------------------------------------


FILTER_PUMP_ON: dict[str, Any] = {"name": "filt0", "st": 1}
FILTER_PUMP_OFF: dict[str, Any] = {"name": "filt0", "st": 0}
AUX_SWITCH_ON: dict[str, Any] = {"name": "aux0", "st": 1}
AUX_SWITCH_OFF: dict[str, Any] = {"name": "aux0", "st": 0}
JVA_SWITCH_ON: dict[str, Any] = {"name": "jva1", "st": 1}
JVA_SWITCH_OFF: dict[str, Any] = {"name": "jva1", "st": 0}
CHLORINATOR_BOOST_ON: dict[str, Any] = {"name": "swc0", "boost": 1}
CHLORINATOR_BOOST_OFF: dict[str, Any] = {"name": "swc0", "boost": 0}
FEATURE_CIRCUIT_ON: dict[str, Any] = {"name": "feaCircuit0", "st": 1}
FEATURE_CIRCUIT_OFF: dict[str, Any] = {"name": "feaCircuit0", "st": 0}
ZIGBEE_SWITCH_ON: dict[str, Any] = {"name": "auxz0", "st": 1}
ZIGBEE_SWITCH_OFF: dict[str, Any] = {"name": "auxz0", "st": 0}
CLIMATE_ON: dict[str, Any] = {"name": "TspBdy0", "heatEnabled": True}
CLIMATE_OFF: dict[str, Any] = {"name": "TspBdy0", "heatEnabled": False}


class TestTcxFilterPumpOnOff:
    def test_is_on_true(self) -> None:
        sut = TcxFilterPump(make_system(), FILTER_PUMP_ON)
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = TcxFilterPump(make_system(), FILTER_PUMP_OFF)
        assert sut.is_on is False

    async def test_turn_on_sends_command(self) -> None:
        sut = TcxFilterPump(make_system(), FILTER_PUMP_OFF)
        with patch.object(
            sut.system, "set_filter_pump", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with(1)

    async def test_turn_on_noop_when_already_on(self) -> None:
        sut = TcxFilterPump(make_system(), FILTER_PUMP_ON)
        with patch.object(
            sut.system, "set_filter_pump", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_not_called()

    async def test_turn_off_sends_command(self) -> None:
        sut = TcxFilterPump(make_system(), FILTER_PUMP_ON)
        with patch.object(
            sut.system, "set_filter_pump", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_awaited_once_with(0)

    async def test_turn_off_noop_when_already_off(self) -> None:
        sut = TcxFilterPump(make_system(), FILTER_PUMP_OFF)
        with patch.object(
            sut.system, "set_filter_pump", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_not_called()


class TestTcxAuxSwitchOnOff:
    def test_is_on_true(self) -> None:
        sut = TcxAuxSwitch(make_system(), AUX_SWITCH_ON)
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = TcxAuxSwitch(make_system(), AUX_SWITCH_OFF)
        assert sut.is_on is False

    async def test_turn_on_sends_command_with_name(self) -> None:
        sut = TcxAuxSwitch(make_system(), AUX_SWITCH_OFF)
        with patch.object(
            sut.system, "set_aux", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with("aux0", 1)

    async def test_turn_off_sends_command_with_name(self) -> None:
        sut = TcxAuxSwitch(make_system(), AUX_SWITCH_ON)
        with patch.object(
            sut.system, "set_aux", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_awaited_once_with("aux0", 0)


class TestTcxJvaSwitchOnOff:
    def test_is_on_true(self) -> None:
        sut = TcxJvaSwitch(make_system(), JVA_SWITCH_ON)
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = TcxJvaSwitch(make_system(), JVA_SWITCH_OFF)
        assert sut.is_on is False

    async def test_turn_on_sends_command_with_name(self) -> None:
        sut = TcxJvaSwitch(make_system(), JVA_SWITCH_OFF)
        with patch.object(
            sut.system, "set_jva_state", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with("jva1", 1)

    async def test_turn_off_sends_command_with_name(self) -> None:
        sut = TcxJvaSwitch(make_system(), JVA_SWITCH_ON)
        with patch.object(
            sut.system, "set_jva_state", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_awaited_once_with("jva1", 0)

    def test_from_data_dispatches_jva1_and_jva2(self) -> None:
        for name in ("jva1", "jva2"):
            data: dict[str, Any] = {"name": name, "st": 0}
            sut = TcxDevice.from_data(make_system(), data)
            assert isinstance(sut, TcxJvaSwitch)


class TestTcxChlorinatorBoostOnOff:
    def test_is_on_true(self) -> None:
        sut = TcxChlorinatorBoost(make_system(), CHLORINATOR_BOOST_ON)
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = TcxChlorinatorBoost(make_system(), CHLORINATOR_BOOST_OFF)
        assert sut.is_on is False

    async def test_turn_on_sends_command(self) -> None:
        sut = TcxChlorinatorBoost(make_system(), CHLORINATOR_BOOST_OFF)
        with patch.object(
            sut.system, "set_swc_boost", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with(True)

    async def test_turn_off_sends_command(self) -> None:
        sut = TcxChlorinatorBoost(make_system(), CHLORINATOR_BOOST_ON)
        with patch.object(
            sut.system, "set_swc_boost", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_awaited_once_with(False)


class TestTcxFeatureCircuitOnOff:
    def test_is_on_true(self) -> None:
        sut = TcxFeatureCircuit(make_system(), FEATURE_CIRCUIT_ON)
        assert sut.is_on is True

    async def test_turn_on_sends_command_with_name(self) -> None:
        sut = TcxFeatureCircuit(make_system(), FEATURE_CIRCUIT_OFF)
        with patch.object(
            sut.system, "set_feature_circuit_state", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with("feaCircuit0", 1)

    async def test_turn_off_sends_command_with_name(self) -> None:
        sut = TcxFeatureCircuit(make_system(), FEATURE_CIRCUIT_ON)
        with patch.object(
            sut.system, "set_feature_circuit_state", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_awaited_once_with("feaCircuit0", 0)


class TestTcxZigbeeSwitchOnOff:
    def test_is_on_true(self) -> None:
        sut = TcxZigbeeSwitch(make_system(), ZIGBEE_SWITCH_ON)
        assert sut.is_on is True

    async def test_turn_on_sends_command_with_name(self) -> None:
        sut = TcxZigbeeSwitch(make_system(), ZIGBEE_SWITCH_OFF)
        with patch.object(
            sut.system, "set_zigbee_state", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with("auxz0", 1)

    async def test_turn_off_sends_command_with_name(self) -> None:
        sut = TcxZigbeeSwitch(make_system(), ZIGBEE_SWITCH_ON)
        with patch.object(
            sut.system, "set_zigbee_state", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_awaited_once_with("auxz0", 0)


class TestTcxClimateOnOff:
    def test_is_on_true(self) -> None:
        sut = TcxClimate(make_system(), CLIMATE_ON)
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = TcxClimate(make_system(), CLIMATE_OFF)
        assert sut.is_on is False

    async def test_turn_on_sends_command(self) -> None:
        sut = TcxClimate(make_system(), CLIMATE_OFF)
        with patch.object(
            sut.system, "set_heat_enabled", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with(True)

    async def test_turn_off_sends_command(self) -> None:
        sut = TcxClimate(make_system(), CLIMATE_ON)
        with patch.object(
            sut.system, "set_heat_enabled", new_callable=AsyncMock
        ) as mock_set:
            await sut.turn_off()
        mock_set.assert_awaited_once_with(False)

    async def test_set_temperature_sends_command(self) -> None:
        data: dict[str, Any] = {
            "name": "TspBdy0",
            "heatEnabled": True,
            "waterTempSet": 800,
        }
        sut = TcxClimate(make_system(), data)
        with patch.object(
            sut.system, "set_water_temp_setpoint", new_callable=AsyncMock
        ) as mock_set:
            # set_temperature() takes a whole-degree int (AqualinkClimate
            # contract); the wire field is tenths of a degree.
            await sut.set_temperature(88)
        mock_set.assert_awaited_once_with(880)
