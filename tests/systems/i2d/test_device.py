from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pytest
import respx
import respx.router

from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.systems.i2d.device import (
    I2dBinarySensor,
    I2dNumber,
    I2dPump,
    I2dSensor,
    I2dSwitch,
)
from iaqualink.systems.i2d.system import I2dSystem

from ...base import dotstar, resp_200
from ...base_test_device import (
    TestBaseBinarySensor,
    TestBaseNumber,
    TestBasePump,
    TestBaseSensor,
    TestBaseSwitch,
)
from ...common import async_returns

_CONTRACT_SYSTEM_DATA = {
    "id": 1,
    "serial_number": "ABC123",
    "name": "Pool Pump",
    "device_type": "i2d",
}


class TestI2dSensorContract(TestBaseSensor):
    def setUp(self) -> None:
        super().setUp()
        system = I2dSystem.from_data(self.client, _CONTRACT_SYSTEM_DATA)
        self.sut = I2dSensor(
            system,
            {"speed": "1500"},
            key="speed",
            label="Motor Speed",
            unit="RPM",
        )
        self.sut_class = I2dSensor


class TestI2dBinarySensorContract(TestBaseBinarySensor):
    def setUp(self) -> None:
        super().setUp()
        system = I2dSystem.from_data(self.client, _CONTRACT_SYSTEM_DATA)
        self._data: dict = {"freezeprotectstatus": "0"}
        self.sut = I2dBinarySensor(
            system,
            self._data,
            key="freezeprotectstatus",
            label="Freeze Protect Status",
        )
        self.sut_class = I2dBinarySensor

    def test_property_is_on_false(self) -> None:
        self._data["freezeprotectstatus"] = "0"
        assert self.sut.is_on is False

    def test_property_is_on_true(self) -> None:
        self._data["freezeprotectstatus"] = "1"
        assert self.sut.is_on is True


class TestI2dSwitchContract(TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()
        system = I2dSystem.from_data(self.client, _CONTRACT_SYSTEM_DATA)
        self._data: dict = {"freezeprotectenable": "0"}
        self.sut = I2dSwitch(
            system,
            self._data,
            key="freezeprotectenable",
            label="Freeze Protection",
        )
        self.sut_class = I2dSwitch

    def test_property_is_on_false(self) -> None:
        self._data["freezeprotectenable"] = "0"
        assert self.sut.is_on is False

    def test_property_is_on_true(self) -> None:
        self._data["freezeprotectenable"] = "1"
        assert self.sut.is_on is True

    @respx.mock
    async def test_turn_on_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        # I2dSwitch has no is_on guard: always writes (idempotent hardware setting)
        self._data["freezeprotectenable"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self._data["freezeprotectenable"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestI2dNumberContract(TestBaseNumber):
    def setUp(self) -> None:
        super().setUp()
        system = I2dSystem.from_data(self.client, _CONTRACT_SYSTEM_DATA)
        data = {
            "quickcleanrpm": "3000",
            "globalrpmmin": "600",
            "globalrpmmax": "3450",
        }
        self.sut = I2dNumber(
            system,
            data,
            key="quickcleanrpm",
            label="Quick Clean RPM",
            min_value=600.0,
            max_value=3450.0,
            step=25.0,
            unit="RPM",
        )
        self.sut_class = I2dNumber


class TestI2dPumpContract(TestBasePump):
    def setUp(self) -> None:
        super().setUp()
        system = I2dSystem.from_data(self.client, _CONTRACT_SYSTEM_DATA)
        self._data: dict = {
            "name": "ABC123",
            "runstate": "off",
            "opmode": "2",
            "globalrpmmin": "600",
            "globalrpmmax": "3450",
        }
        self.sut = I2dPump(system, self._data)
        self.sut_class = I2dPump

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self._data["runstate"] = "on"
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_off()
        assert len(respx_mock.calls) > 0
        self.respx_calls = respx_mock.calls[:]


def _make_sensor(
    data: dict,
    key: str = "speed",
    label: str = "Motor Speed",
    unit: str = "RPM",
) -> I2dSensor:
    system = MagicMock()
    system.serial = "ABC123"
    return I2dSensor(system, data, key=key, label=label, unit=unit)


class TestI2dSensor(unittest.IsolatedAsyncioTestCase):
    def test_name(self):
        s = _make_sensor({"speed": "1500"})
        assert s.name == "speed"

    def test_label(self):
        s = _make_sensor({"speed": "1500"})
        assert s.label == "Motor Speed"

    def test_state_present(self):
        s = _make_sensor({"speed": "1500"})
        assert s.state == "1500"

    def test_state_missing(self):
        s = _make_sensor({})
        assert s.state == ""

    def test_unit(self):
        s = _make_sensor({})
        assert s.unit == "RPM"

    def test_manufacturer(self):
        s = _make_sensor({})
        assert s.manufacturer == "Zodiac"

    def test_model(self):
        s = _make_sensor({})
        assert s.model == "iQPump"

    def test_state_updates_live(self):
        data: dict = {"speed": "1500"}
        s = _make_sensor(data)
        assert s.state == "1500"
        data["speed"] = "3000"
        assert s.state == "3000"

    def test_path_reads_nested_value(self):
        data: dict = {"wifistatus": {"state": "connected", "ssid": "Home"}}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.state == "connected"

    def test_path_updates_live(self):
        data: dict = {"wifistatus": {"state": "connected"}}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.state == "connected"
        data["wifistatus"]["state"] = "disconnected"
        assert s.state == "disconnected"

    def test_path_missing_container_returns_empty(self):
        data: dict = {}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.state == ""

    def test_path_missing_leaf_returns_empty(self):
        data: dict = {"wifistatus": {}}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.state == ""


def _make_number(data: dict, **kwargs) -> I2dNumber:
    system = MagicMock()
    system.serial = "ABC123"
    defaults = dict(
        key="quickcleanrpm",
        label="Quick Clean RPM",
        min_value=600.0,
        max_value=3450.0,
        unit="RPM",
    )
    defaults.update(kwargs)
    return I2dNumber(system, data, **defaults)


class TestI2dNumber(unittest.IsolatedAsyncioTestCase):
    def test_name(self):
        num = _make_number({"quickcleanrpm": "3000"})
        assert num.name == "quickcleanrpm"

    def test_label(self):
        num = _make_number({"quickcleanrpm": "3000"})
        assert num.label == "Quick Clean RPM"

    def test_current_value_present(self):
        num = _make_number({"quickcleanrpm": "3000"})
        assert num.current_value == 3000.0

    def test_current_value_missing(self):
        num = _make_number({})
        assert num.current_value is None

    def test_state(self):
        num = _make_number({"quickcleanrpm": "3000"})
        assert num.state == "3000"

    def test_state_missing(self):
        num = _make_number({})
        assert num.state == ""

    def test_min_value_static(self):
        num = _make_number({})
        assert num.min_value == 600.0

    def test_max_value_static(self):
        num = _make_number({})
        assert num.max_value == 3450.0

    def test_min_value_from_data_key(self):
        num = _make_number(
            {
                "quickcleanrpm": "3000",
                "globalrpmmin": "800",
                "globalrpmmax": "3450",
            },
            min_value=None,
            min_key="globalrpmmin",
        )
        assert num.min_value == 800.0

    def test_max_value_from_data_key(self):
        num = _make_number(
            {
                "quickcleanrpm": "3000",
                "globalrpmmin": "600",
                "globalrpmmax": "3200",
            },
            max_value=None,
            max_key="globalrpmmax",
        )
        assert num.max_value == 3200.0

    def test_unit(self):
        num = _make_number({})
        assert num.unit == "RPM"

    def test_step_default(self):
        num = _make_number({})
        assert num.step == 1.0

    def test_manufacturer(self):
        num = _make_number({})
        assert num.manufacturer == "Zodiac"

    def test_model(self):
        num = _make_number({})
        assert num.model == "iQPump"

    async def test_set_value_calls_command(self):
        num = _make_number({"quickcleanrpm": "3000"})
        mock_response = MagicMock()
        num.system.send_control_command = async_returns(mock_response)
        await num.set_value(3000.0)
        num.system.send_control_command.assert_awaited_once_with(
            "/quickcleanrpm/write", "value=3000"
        )

    async def test_set_value_truncates_to_int(self):
        num = _make_number({"quickcleanrpm": "3000"})
        mock_response = MagicMock()
        num.system.send_control_command = async_returns(mock_response)
        await num.set_value(3000.9)
        num.system.send_control_command.assert_awaited_once_with(
            "/quickcleanrpm/write", "value=3000"
        )

    async def test_set_value_below_min_raises(self):
        num = _make_number({})
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(599.0)

    async def test_set_value_above_max_raises(self):
        num = _make_number({})
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(3451.0)

    async def test_set_value_at_min_ok(self):
        num = _make_number({})
        num.system.send_control_command = async_returns(MagicMock())
        await num.set_value(600.0)
        num.system.send_control_command.assert_awaited_once()

    async def test_set_value_at_max_ok(self):
        num = _make_number({})
        num.system.send_control_command = async_returns(MagicMock())
        await num.set_value(3450.0)
        num.system.send_control_command.assert_awaited_once()

    async def test_set_value_not_multiple_of_step_raises(self):
        num = _make_number({"quickcleanrpm": "3000"}, step=300.0)
        num.system.send_control_command = async_returns(MagicMock())
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(1201.0)

    async def test_set_value_step_1_any_integer_ok(self):
        num = _make_number({"quickcleanrpm": "3000"}, step=1.0)
        num.system.send_control_command = async_returns(MagicMock())
        await num.set_value(3001.0)  # any integer is a multiple of 1
        num.system.send_control_command.assert_awaited_once()

    async def test_set_value_multiple_of_step_ok(self):
        num = _make_number({"quickcleanrpm": "3000"}, step=300.0)
        num.system.send_control_command = async_returns(MagicMock())
        await num.set_value(1200.0)
        num.system.send_control_command.assert_awaited_once()

    def test_min_max_from_shared_data_updates_live(self):
        """min/max read live from data dict — updates reflected immediately."""
        data: dict = {
            "quickcleanrpm": "3000",
            "globalrpmmin": "600",
            "globalrpmmax": "3450",
        }
        num = _make_number(
            data,
            min_value=None,
            max_value=None,
            min_key="globalrpmmin",
            max_key="globalrpmmax",
        )
        assert num.min_value == 600.0
        data["globalrpmmin"] = "800"
        data["globalrpmmax"] = "3200"
        assert num.min_value == 800.0
        assert num.max_value == 3200.0

    async def test_set_value_calls_apply_write_response(self):
        num = _make_number({"quickcleanrpm": "3000"})
        mock_resp = MagicMock()
        num.system.send_control_command = async_returns(mock_resp)
        await num.set_value(2000.0)
        num.system._apply_write_response.assert_called_once_with(mock_resp)


def _make_switch(
    data: dict,
    key: str = "freezeprotectenable",
    label: str = "Freeze Protection",
) -> I2dSwitch:
    system = MagicMock()
    system.serial = "ABC123"
    return I2dSwitch(system, data, key=key, label=label)


class TestI2dSwitch(unittest.IsolatedAsyncioTestCase):
    def test_name(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        assert sw.name == "freezeprotectenable"

    def test_label(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        assert sw.label == "Freeze Protection"

    def test_is_on_when_one(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        assert sw.is_on is True

    def test_is_on_when_zero(self):
        sw = _make_switch({"freezeprotectenable": "0"})
        assert sw.is_on is False

    def test_is_on_when_missing(self):
        sw = _make_switch({})
        assert sw.is_on is False

    def test_state_on(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        assert sw.state == "on"

    def test_state_off(self):
        sw = _make_switch({"freezeprotectenable": "0"})
        assert sw.state == "off"

    def test_manufacturer(self):
        sw = _make_switch({})
        assert sw.manufacturer == "Zodiac"

    def test_model(self):
        sw = _make_switch({})
        assert sw.model == "iQPump"

    async def test_turn_on_sends_command(self):
        sw = _make_switch({"freezeprotectenable": "0"})
        sw.system.send_control_command = async_returns(MagicMock())
        await sw.turn_on()
        sw.system.send_control_command.assert_awaited_once_with(
            "/freezeprotectenable/write", "value=1"
        )

    async def test_turn_off_sends_command(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        sw.system.send_control_command = async_returns(MagicMock())
        await sw.turn_off()
        sw.system.send_control_command.assert_awaited_once_with(
            "/freezeprotectenable/write", "value=0"
        )

    async def test_turn_on_calls_apply_write_response(self):
        sw = _make_switch({"freezeprotectenable": "0"})
        mock_resp = MagicMock()
        sw.system.send_control_command = async_returns(mock_resp)
        await sw.turn_on()
        sw.system._apply_write_response.assert_called_once_with(mock_resp)

    async def test_turn_off_calls_apply_write_response(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        mock_resp = MagicMock()
        sw.system.send_control_command = async_returns(mock_resp)
        await sw.turn_off()
        sw.system._apply_write_response.assert_called_once_with(mock_resp)


class TestI2dPump(unittest.IsolatedAsyncioTestCase):
    def _make_pump(self, data: dict):
        from iaqualink.systems.i2d.device import I2dPump

        system = MagicMock()
        system.serial = "ABC123"
        return I2dPump(system, {"name": "ABC123", **data})

    async def test_turn_on_when_off_sends_custom_opmode(self):
        pump = self._make_pump({"runstate": "off", "opmode": "2"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.turn_on()
        pump.system.send_control_command.assert_awaited_once_with(
            "/opmode/write", "value=1"
        )

    async def test_turn_on_when_already_on_does_nothing(self):
        pump = self._make_pump({"runstate": "on", "opmode": "1"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.turn_on()
        pump.system.send_control_command.assert_not_awaited()

    async def test_turn_off_when_on_sends_stop_opmode(self):
        pump = self._make_pump({"runstate": "on", "opmode": "1"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.turn_off()
        pump.system.send_control_command.assert_awaited_once_with(
            "/opmode/write", "value=2"
        )

    async def test_turn_off_when_already_off_does_nothing(self):
        pump = self._make_pump({"runstate": "off", "opmode": "2"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.turn_off()
        pump.system.send_control_command.assert_not_awaited()

    def test_current_preset_for_internal_mode_readable(self):
        from iaqualink.systems.i2d.device import I2dOpMode

        pump = self._make_pump({"opmode": str(I2dOpMode.QUICK_CLEAN)})
        assert pump.current_preset == "QUICK_CLEAN"
        assert "QUICK_CLEAN" not in pump.supported_presets

    def test_current_preset_when_opmode_missing(self):
        pump = self._make_pump({})
        assert pump.current_preset is None

    async def test_set_speed_percentage_svrs_bounds(self):
        # SVRS pump: min=1050, max=3450 — 0% → 1050, 100% → 3450
        pump = self._make_pump(
            {"globalrpmmin": "1050", "globalrpmmax": "3450", "productid": "0F"}
        )
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.set_speed_percentage(0)
        pump.system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=1050"
        )

    async def test_set_speed_percentage_rounding(self):
        # 600 + (3450-600)*33/100 = 600 + 940.5 = 1540.5 → round to nearest 25 = 1550
        pump = self._make_pump({"globalrpmmin": "600", "globalrpmmax": "3450"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.set_speed_percentage(33)
        pump.system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=1550"
        )

    async def test_set_speed_percentage_clamps_to_max(self):
        pump = self._make_pump({"globalrpmmin": "600", "globalrpmmax": "3450"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.set_speed_percentage(100)
        pump.system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=3450"
        )

    async def test_turn_on_calls_apply_write_response(self):
        pump = self._make_pump({"runstate": "off", "opmode": "2"})
        mock_resp = MagicMock()
        pump.system.send_control_command = async_returns(mock_resp)
        await pump.turn_on()
        pump.system._apply_write_response.assert_called_once_with(mock_resp)

    async def test_set_speed_percentage_calls_apply_write_response(self):
        pump = self._make_pump(
            {
                "globalrpmmin": "600",
                "globalrpmmax": "3450",
                "customspeedrpm": "600",
            }
        )
        mock_resp = MagicMock()
        pump.system.send_control_command = async_returns(mock_resp)
        await pump.set_speed_percentage(50)
        pump.system._apply_write_response.assert_called_once_with(mock_resp)


class TestI2dBinaryState(unittest.TestCase):
    def test_on_value(self):
        from iaqualink.systems.i2d.device import I2dBinaryState

        assert I2dBinaryState.ON == "1"

    def test_off_value(self):
        from iaqualink.systems.i2d.device import I2dBinaryState

        assert I2dBinaryState.OFF == "0"


class TestI2dNumberConstructorValidation(unittest.TestCase):
    def test_missing_both_min_raises(self):
        system = MagicMock()
        with pytest.raises(ValueError):
            I2dNumber(system, {}, key="x", label="X", max_value=100.0)

    def test_missing_both_max_raises(self):
        system = MagicMock()
        with pytest.raises(ValueError):
            I2dNumber(system, {}, key="x", label="X", min_value=0.0)


def _make_binary_sensor(
    data: dict,
    key: str = "freezeprotectstatus",
    label: str = "Freeze Protect Status",
) -> I2dBinarySensor:
    system = MagicMock()
    system.serial = "ABC123"
    return I2dBinarySensor(system, data, key=key, label=label)


class TestI2dBinarySensor(unittest.TestCase):
    def test_name(self):
        s = _make_binary_sensor({"freezeprotectstatus": "0"})
        assert s.name == "freezeprotectstatus"

    def test_label(self):
        s = _make_binary_sensor({"freezeprotectstatus": "0"})
        assert s.label == "Freeze Protect Status"

    def test_is_on_when_one(self):
        s = _make_binary_sensor({"freezeprotectstatus": "1"})
        assert s.is_on is True

    def test_is_on_when_zero(self):
        s = _make_binary_sensor({"freezeprotectstatus": "0"})
        assert s.is_on is False

    def test_is_on_when_missing(self):
        s = _make_binary_sensor({})
        assert s.is_on is False

    def test_state_on(self):
        s = _make_binary_sensor({"freezeprotectstatus": "1"})
        assert s.state == "on"

    def test_state_off(self):
        s = _make_binary_sensor({"freezeprotectstatus": "0"})
        assert s.state == "off"

    def test_manufacturer(self):
        s = _make_binary_sensor({})
        assert s.manufacturer == "Zodiac"

    def test_model(self):
        s = _make_binary_sensor({})
        assert s.model == "iQPump"

    def test_state_updates_live(self):
        data: dict = {"freezeprotectstatus": "0"}
        s = _make_binary_sensor(data)
        assert s.is_on is False
        data["freezeprotectstatus"] = "1"
        assert s.is_on is True
