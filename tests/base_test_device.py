from __future__ import annotations

import copy
from unittest.mock import PropertyMock, patch

import pytest
import respx
import respx.router

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkLight,
    AqualinkNumber,
    AqualinkPump,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
)

from .base import TestBase, dotstar, resp_200


class TestBaseDevice(TestBase):
    def test_property_name(self) -> None:
        assert isinstance(self.sut.name, str)

    def test_property_label(self) -> None:
        assert isinstance(self.sut.label, str)

    def test_property_state(self) -> None:
        assert isinstance(self.sut.state, str)

    def test_property_manufacturer(self) -> None:
        assert isinstance(self.sut.manufacturer, str)

    def test_property_model(self) -> None:
        assert isinstance(self.sut.model, str)

    def test_from_data(self) -> None:
        if sut_class := getattr(self, "sut_class", None):
            assert isinstance(self.sut, sut_class)


class TestBaseSensor(TestBaseDevice):
    def test_inheritance(self) -> None:
        assert isinstance(self.sut, AqualinkSensor)


class TestBaseBinarySensor(TestBaseSensor):
    def test_inheritance(self) -> None:
        assert isinstance(self.sut, AqualinkBinarySensor)

    def test_property_is_on_true(self) -> None:
        assert self.sut.is_on is True

    def test_property_is_on_false(self) -> None:
        assert self.sut.is_on is False


class TestBaseSwitch(TestBaseBinarySensor):
    def test_inheritance(self) -> None:
        assert isinstance(self.sut, AqualinkSwitch)

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_on()
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_turn_on_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_on()
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_off()
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_turn_off_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_off()
        assert len(respx_mock.calls) == 0


class TestBaseLight(TestBaseSwitch):
    def test_inheritance(self) -> None:
        assert isinstance(self.sut, AqualinkLight)

    def test_property_supports_brightness(self) -> None:
        assert isinstance(self.sut.supports_brightness, bool)

    def test_property_supports_effect(self) -> None:
        assert isinstance(self.sut.supports_effect, bool)

    def test_property_brightness(self) -> None:
        if not self.sut.supports_brightness:
            pytest.skip("Device doesn't support brightness")
        assert isinstance(self.sut.brightness, int)
        assert 0 <= self.sut.brightness <= 100

    def test_property_effect(self) -> None:
        if not self.sut.supports_effect:
            pytest.skip("Device doesn't support effects")
        assert isinstance(self.sut.effect, str)

    def test_property_supported_effects(self) -> None:
        if not self.sut.supports_effect:
            pytest.skip("Device doesn't support effects")
        assert isinstance(self.sut.supported_effects, dict)

    @respx.mock
    async def test_set_brightness_75(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_brightness:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_brightness(75)
            return

        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_brightness(75)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_brightness_invalid_89(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_brightness:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_brightness(89)
            return

        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_brightness(89)
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_set_effect_by_id_4(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_effect:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_effect_by_id(4)
            return

        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_effect_by_id(4)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_effect_by_id_invalid_27(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_effect:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_effect_by_id(27)
            return

        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_effect_by_id(27)
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_set_effect_by_name_off(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_effect:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_effect_by_name("Off")
            return

        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_effect_by_name("Off")
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_effect_by_name_invalid_amaranth(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_effect:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_effect_by_name("Amaranth")
            return

        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_effect_by_name("Amaranth")
        assert len(respx_mock.calls) == 0


class TestBaseThermostat(TestBaseSwitch):
    def test_inheritance(self) -> None:
        assert isinstance(self.sut, AqualinkThermostat)

    def test_property_unit(self) -> None:
        assert self.sut.unit in ["C", "F"]

    def test_property_min_temperature_f(self) -> None:
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "F"
            assert isinstance(self.sut.min_temperature, int)

    def test_property_min_temperature_c(self) -> None:
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "C"
            assert isinstance(self.sut.min_temperature, int)

    def test_property_max_temperature_f(self) -> None:
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "F"
            assert isinstance(self.sut.max_temperature, int)

    def test_property_max_temperature_c(self) -> None:
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "C"
            assert isinstance(self.sut.max_temperature, int)

    def test_property_current_temperature(self) -> None:
        assert isinstance(self.sut.current_temperature, str)

    def test_property_target_temperature(self) -> None:
        assert isinstance(self.sut.target_temperature, str)

    @respx.mock
    async def test_set_temperature_86f(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "F"
            await self.sut.set_temperature(86)
            assert len(respx_mock.calls) > 0
            self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_temperature_30c(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "C"
            await self.sut.set_temperature(30)
            assert len(respx_mock.calls) > 0
            self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_temperature_invalid_400f(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "F"
            with pytest.raises(AqualinkInvalidParameterException):
                await self.sut.set_temperature(400)
            assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_set_temperature_invalid_204c(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(
            type(self.sut), "unit", new_callable=PropertyMock
        ) as mock_unit:
            mock_unit.return_value = "C"
            with pytest.raises(AqualinkInvalidParameterException):
                await self.sut.set_temperature(204)
            assert len(respx_mock.calls) == 0


class TestBaseNumber(TestBaseDevice):
    def test_inheritance(self) -> None:
        assert isinstance(self.sut, AqualinkNumber)

    def test_property_current_value(self) -> None:
        assert self.sut.current_value is None or isinstance(
            self.sut.current_value, float
        )

    def test_property_min_value(self) -> None:
        assert isinstance(self.sut.min_value, float)

    def test_property_max_value(self) -> None:
        assert isinstance(self.sut.max_value, float)

    def test_property_min_le_max(self) -> None:
        assert self.sut.min_value <= self.sut.max_value

    def test_property_step(self) -> None:
        assert isinstance(self.sut.step, float)
        assert self.sut.step > 0

    def test_property_unit(self) -> None:
        assert self.sut.unit is None or isinstance(self.sut.unit, str)

    @respx.mock
    async def test_set_value_at_min(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_value(self.sut.min_value)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_value_at_max(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_value(self.sut.max_value)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_value_below_min(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_value(self.sut.min_value - 1.0)
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_set_value_above_max(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_value(self.sut.max_value + 1.0)
        assert len(respx_mock.calls) == 0


class TestBasePump(TestBaseBinarySensor):
    def test_inheritance(self) -> None:
        assert isinstance(self.sut, AqualinkPump)

    def test_property_supports_turn_on(self) -> None:
        assert isinstance(self.sut.supports_turn_on, bool)

    def test_property_supports_turn_off(self) -> None:
        assert isinstance(self.sut.supports_turn_off, bool)

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        if not self.sut.supports_turn_on:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.turn_on()
            return
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_on()
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_turn_on_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_turn_on:
            pytest.skip("Device doesn't support turn_on")
        with patch.object(
            type(self.sut),
            "is_on",
            new_callable=PropertyMock(return_value=True),
        ):
            respx_mock.route(dotstar).mock(resp_200)
            await self.sut.turn_on()
            assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        if not self.sut.supports_turn_off:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.turn_off()
            return
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_off()
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_turn_off_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_turn_off:
            pytest.skip("Device doesn't support turn_off")
        with patch.object(
            type(self.sut),
            "is_on",
            new_callable=PropertyMock(return_value=False),
        ):
            respx_mock.route(dotstar).mock(resp_200)
            await self.sut.turn_off()
            assert len(respx_mock.calls) == 0

    def test_property_supports_presets(self) -> None:
        assert isinstance(self.sut.supports_presets, bool)

    def test_property_supported_presets(self) -> None:
        if self.sut.supports_presets:
            assert isinstance(self.sut.supported_presets, list)
            assert len(self.sut.supported_presets) > 0
        else:
            assert self.sut.supported_presets == []

    def test_property_current_preset(self) -> None:
        if self.sut.supports_presets:
            assert self.sut.current_preset is None or isinstance(
                self.sut.current_preset, str
            )
        else:
            assert self.sut.current_preset is None

    def test_property_supports_set_speed_percentage(self) -> None:
        assert isinstance(self.sut.supports_set_speed_percentage, bool)

    @respx.mock
    async def test_set_speed_percentage_0(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_set_speed_percentage:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_speed_percentage(0)
            return
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_speed_percentage(0)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_speed_percentage_50(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_set_speed_percentage:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_speed_percentage(50)
            return
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_speed_percentage(50)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_speed_percentage_100(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_set_speed_percentage:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_speed_percentage(100)
            return
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_speed_percentage(100)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_speed_percentage_invalid_negative(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_set_speed_percentage:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_speed_percentage(-1)
            return
        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_speed_percentage(-1)
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_set_speed_percentage_invalid_150(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_set_speed_percentage:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_speed_percentage(150)
            return
        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_speed_percentage(150)
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_set_preset(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_presets:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_preset("any")
            return
        respx_mock.route(dotstar).mock(resp_200)
        preset = self.sut.supported_presets[0]
        await self.sut.set_preset(preset)
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_set_preset_invalid(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        if not self.sut.supports_presets:
            with pytest.raises(AqualinkOperationNotSupportedException):
                await self.sut.set_preset("nonexistent")
            return
        respx_mock.route(dotstar).mock(resp_200)
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_preset("nonexistent_preset")
        assert len(respx_mock.calls) == 0
