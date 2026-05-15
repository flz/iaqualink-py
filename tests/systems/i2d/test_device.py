from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pytest


from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.systems.i2d.device import (
    I2dNumber,
    I2dSensor,
    I2dSwitch,
    I2dRpmBoundNumber,
)

from ...common import async_returns


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

    async def test_set_value_step_1_skips_step_check(self):
        num = _make_number({"quickcleanrpm": "3000"}, step=1.0)
        num.system.send_control_command = async_returns(MagicMock())
        await num.set_value(3000.0)  # any integer fine with step=1
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


def _make_rpm_bound(
    data: dict, key: str = "globalrpmmin", *, value_lt_cross: bool = True
) -> I2dRpmBoundNumber:
    system = MagicMock()
    system.serial = "ABC123"
    cross_key = "globalrpmmax" if value_lt_cross else "globalrpmmin"
    return I2dRpmBoundNumber(
        system,
        data,
        key=key,
        label="Global RPM Min" if value_lt_cross else "Global RPM Max",
        cross_key=cross_key,
        value_lt_cross=value_lt_cross,
    )


class TestI2dRpmBoundNumber(unittest.IsolatedAsyncioTestCase):
    def test_min_value_non_svrs(self):
        num = _make_rpm_bound(
            {"productid": "1A", "globalrpmmin": "600", "globalrpmmax": "3450"}
        )
        assert num.min_value == 600.0

    def test_min_value_svrs_0f(self):
        num = _make_rpm_bound(
            {"productid": "0F", "globalrpmmin": "1050", "globalrpmmax": "3450"}
        )
        assert num.min_value == 1050.0

    def test_min_value_svrs_18(self):
        num = _make_rpm_bound(
            {"productid": "18", "globalrpmmin": "1050", "globalrpmmax": "3450"}
        )
        assert num.min_value == 1050.0

    def test_min_value_missing_productid(self):
        num = _make_rpm_bound({"globalrpmmin": "600", "globalrpmmax": "3450"})
        assert num.min_value == 600.0

    def test_max_value_always_3450(self):
        num = _make_rpm_bound(
            {"productid": "0F", "globalrpmmin": "1050", "globalrpmmax": "3450"}
        )
        assert num.max_value == 3450.0

    def test_step_is_25(self):
        num = _make_rpm_bound({})
        assert num.step == 25.0

    def test_unit_is_rpm(self):
        num = _make_rpm_bound({})
        assert num.unit == "RPM"

    async def test_set_value_not_multiple_of_25_raises(self):
        num = _make_rpm_bound(
            {"productid": "1A", "globalrpmmin": "600", "globalrpmmax": "3450"}
        )
        num.system.send_control_command = async_returns(MagicMock())
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(1201.0)

    async def test_set_value_multiple_of_25_ok(self):
        num = _make_rpm_bound(
            {"productid": "1A", "globalrpmmin": "600", "globalrpmmax": "3450"}
        )
        num.system.send_control_command = async_returns(MagicMock())
        await num.set_value(1200.0)
        num.system.send_control_command.assert_awaited_once_with(
            "/globalrpmmin/write", "value=1200"
        )

    async def test_globalrpmmin_gte_globalrpmmax_raises(self):
        num = _make_rpm_bound(
            {"productid": "1A", "globalrpmmin": "600", "globalrpmmax": "3450"}
        )
        num.system.send_control_command = async_returns(MagicMock())
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(3450.0)  # equal — not strictly less

    async def test_globalrpmmax_lte_globalrpmmin_raises(self):
        num = _make_rpm_bound(
            {"productid": "1A", "globalrpmmin": "600", "globalrpmmax": "3450"},
            key="globalrpmmax",
            value_lt_cross=False,
        )
        num.system.send_control_command = async_returns(MagicMock())
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(600.0)  # equal — not strictly greater

    async def test_below_hardware_min_raises(self):
        num = _make_rpm_bound(
            {"productid": "1A", "globalrpmmin": "600", "globalrpmmax": "3450"}
        )
        num.system.send_control_command = async_returns(MagicMock())
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(575.0)

    async def test_svrs_below_1050_raises(self):
        num = _make_rpm_bound(
            {"productid": "0F", "globalrpmmin": "1050", "globalrpmmax": "3450"}
        )
        num.system.send_control_command = async_returns(MagicMock())
        with pytest.raises(AqualinkInvalidParameterException):
            await num.set_value(600.0)  # valid for non-SVRS, invalid for SVRS

    async def test_cross_key_missing_skips_cross_check(self):
        # If globalrpmmax not in data, cross-constraint skipped, value still validated.
        num = _make_rpm_bound({"productid": "1A", "globalrpmmin": "600"})
        num.system.send_control_command = async_returns(MagicMock())
        await num.set_value(1200.0)
        num.system.send_control_command.assert_awaited_once()


class TestI2dPump(unittest.IsolatedAsyncioTestCase):
    def _make_pump(self, data: dict):
        from iaqualink.systems.i2d.device import I2dPump

        system = MagicMock()
        system.serial = "ABC123"
        return I2dPump(system, {"name": "ABC123", **data})

    async def test_turn_on_when_off_calls_set_opmode_custom(self):
        pump = self._make_pump({"runstate": "off", "opmode": "2"})
        pump.system.set_opmode = async_returns(None)
        await pump.turn_on()
        from iaqualink.systems.i2d.device import I2dOpMode

        pump.system.set_opmode.assert_awaited_once_with(I2dOpMode.CUSTOM)

    async def test_turn_on_when_already_on_does_nothing(self):
        pump = self._make_pump({"runstate": "on", "opmode": "1"})
        pump.system.set_opmode = async_returns(None)
        await pump.turn_on()
        pump.system.set_opmode.assert_not_awaited()

    async def test_turn_off_when_on_calls_set_opmode_stop(self):
        pump = self._make_pump({"runstate": "on", "opmode": "1"})
        pump.system.set_opmode = async_returns(None)
        await pump.turn_off()
        from iaqualink.systems.i2d.device import I2dOpMode

        pump.system.set_opmode.assert_awaited_once_with(I2dOpMode.STOP)

    async def test_turn_off_when_already_off_does_nothing(self):
        pump = self._make_pump({"runstate": "off", "opmode": "2"})
        pump.system.set_opmode = async_returns(None)
        await pump.turn_off()
        pump.system.set_opmode.assert_not_awaited()

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
        pump.system.set_custom_speed = async_returns(None)
        await pump.set_speed_percentage(0)
        pump.system.set_custom_speed.assert_awaited_once_with(1050)

    async def test_set_speed_percentage_rounding(self):
        # 600 + (3450-600)*33/100 = 600 + 940.5 = 1540.5 → round to nearest 25 = 1550
        pump = self._make_pump({"globalrpmmin": "600", "globalrpmmax": "3450"})
        pump.system.set_custom_speed = async_returns(None)
        await pump.set_speed_percentage(33)
        pump.system.set_custom_speed.assert_awaited_once_with(1550)

    async def test_set_speed_percentage_clamps_to_max(self):
        # Edge: rounding could push above rpm_max — clamp.
        pump = self._make_pump({"globalrpmmin": "600", "globalrpmmax": "3450"})
        pump.system.set_custom_speed = async_returns(None)
        await pump.set_speed_percentage(100)
        pump.system.set_custom_speed.assert_awaited_once_with(3450)


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
