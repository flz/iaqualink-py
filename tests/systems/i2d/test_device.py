from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.systems.i2d.device import (
    I2dBinarySensor,
    I2dFan,
    I2dNumber,
    I2dSensor,
    I2dSwitch,
)
from iaqualink.systems.i2d.system import I2dSystem

from ...conftest import async_returns
from .factories import CONTRACT_SYSTEM_DATA


def _make_fan_with_data(data: dict) -> I2dFan:
    client = create_autospec(AqualinkClient, instance=True)
    system = I2dSystem.from_data(client, CONTRACT_SYSTEM_DATA)
    return I2dFan(system, data)


class TestI2dFanPercentage:
    @pytest.mark.parametrize(
        "rpm,min_rpm,max_rpm,expected",
        [
            ("1500", "600", "3450", 32),
            ("600", "600", "3450", 0),
            ("3450", "600", "3450", 100),
            ("4000", "600", "3450", 100),
            ("100", "600", "3450", 0),
        ],
        ids=["mid-range", "at-min", "at-max", "above-max", "below-min"],
    )
    def test_percentage(
        self, rpm: str, min_rpm: str, max_rpm: str, expected: int
    ) -> None:
        fan = _make_fan_with_data(
            {
                "customspeedrpm": rpm,
                "globalrpmmin": min_rpm,
                "globalrpmmax": max_rpm,
            }
        )
        assert fan.percentage == expected

    def test_none_when_rpm_missing(self) -> None:
        fan = _make_fan_with_data(
            {"globalrpmmin": "600", "globalrpmmax": "3450"}
        )
        assert fan.percentage is None

    def test_none_when_min_equals_max(self) -> None:
        fan = _make_fan_with_data(
            {
                "customspeedrpm": "1500",
                "globalrpmmin": "1500",
                "globalrpmmax": "1500",
            }
        )
        assert fan.percentage is None

    def test_uses_hardware_default_min_when_key_absent(self) -> None:
        # rpm_min defaults to _RPM_HARDWARE_MIN_DEFAULT (600) when globalrpmmin absent
        fan = _make_fan_with_data(
            {"customspeedrpm": "600", "globalrpmmax": "3450"}
        )
        assert fan.percentage == 0


def _make_sensor(
    data: dict,
    key: str = "speed",
    label: str = "Motor Speed",
    unit: str = "RPM",
) -> I2dSensor:
    system = create_autospec(I2dSystem, instance=True)
    return I2dSensor(system, data, key=key, label=label, unit=unit)


class TestI2dSensor:
    def test_name(self):
        s = _make_sensor({"speed": "1500"})
        assert s.name == "speed"

    def test_label(self):
        s = _make_sensor({"speed": "1500"})
        assert s.label == "Motor Speed"

    def test_value_present(self):
        s = _make_sensor({"speed": "1500"})
        assert s.value == "1500"

    def test_value_missing(self):
        s = _make_sensor({})
        assert s.value == ""

    def test_unit_of_measurement(self):
        s = _make_sensor({})
        assert s.unit_of_measurement == "RPM"

    def test_manufacturer(self):
        s = _make_sensor({})
        assert s.manufacturer == "Zodiac"

    def test_model(self):
        s = _make_sensor({})
        assert s.model == "iQPump"

    def test_value_updates_live(self):
        data: dict = {"speed": "1500"}
        s = _make_sensor(data)
        assert s.value == "1500"
        data["speed"] = "3000"
        assert s.value == "3000"

    def test_path_reads_nested_value(self):
        data: dict = {"wifistatus": {"state": "connected", "ssid": "Home"}}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.value == "connected"

    def test_path_updates_live(self):
        data: dict = {"wifistatus": {"state": "connected"}}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.value == "connected"
        data["wifistatus"]["state"] = "disconnected"
        assert s.value == "disconnected"

    def test_path_missing_container_returns_empty(self):
        data: dict = {}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.value == ""

    def test_path_missing_leaf_returns_empty(self):
        data: dict = {"wifistatus": {}}
        s = _make_sensor(data, key="wifistate", label="WiFi State", unit=None)
        s._path = ("wifistatus", "state")
        assert s.value == ""


def _make_number(data: dict, **kwargs) -> I2dNumber:
    system = create_autospec(I2dSystem, instance=True)
    defaults = dict(
        key="quickcleanrpm",
        label="Quick Clean RPM",
        min_value=600.0,
        max_value=3450.0,
        unit="RPM",
    )
    defaults.update(kwargs)
    return I2dNumber(system, data, **defaults)


class TestI2dNumber:
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

    def test_unit_of_measurement(self):
        num = _make_number({})
        assert num.unit_of_measurement == "RPM"

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

    async def test_set_value_sends_as_int(self):
        num = _make_number({"quickcleanrpm": "3000"})
        mock_response = MagicMock()
        num.system.send_control_command = async_returns(mock_response)
        await num.set_value(3000.0)
        num.system.send_control_command.assert_awaited_once_with(
            "/quickcleanrpm/write", "value=3000"
        )

    @pytest.mark.parametrize(
        "value,should_raise",
        [
            (599.0, True),
            (3451.0, True),
            (600.0, False),
            (3450.0, False),
        ],
        ids=["below-min", "above-max", "at-min", "at-max"],
    )
    async def test_set_value_bounds(self, value: float, should_raise: bool):
        num = _make_number({})
        if should_raise:
            with pytest.raises(AqualinkInvalidParameterException):
                await num.set_value(value)
        else:
            num.system.send_control_command = async_returns(MagicMock())
            await num.set_value(value)
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
    system = create_autospec(I2dSystem, instance=True)
    return I2dSwitch(system, data, key=key, label=label)


class TestI2dSwitch:
    def test_name(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        assert sw.name == "freezeprotectenable"

    def test_label(self):
        sw = _make_switch({"freezeprotectenable": "1"})
        assert sw.label == "Freeze Protection"

    @pytest.mark.parametrize(
        "data,expected_is_on,expected_state",
        [
            ({"freezeprotectenable": "1"}, True, "on"),
            ({"freezeprotectenable": "0"}, False, "off"),
            ({}, False, "off"),
        ],
        ids=["on", "off", "missing"],
    )
    def test_state(self, data: dict, expected_is_on: bool, expected_state: str):
        sw = _make_switch(data)
        assert sw.is_on is expected_is_on
        assert sw.state == expected_state

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


class TestI2dFan:
    def _make_fan(self, data: dict):
        from iaqualink.systems.i2d.device import I2dFan

        system = create_autospec(I2dSystem, instance=True)
        return I2dFan(system, {"name": "ABC123", **data})

    @pytest.mark.parametrize(
        "runstate,opmode,action,expected_value",
        [
            ("off", "2", "turn_on", "1"),
            ("on", "1", "turn_on", None),
            ("on", "1", "turn_off", "2"),
            ("off", "2", "turn_off", None),
        ],
        ids=["on-when-off", "on-noop", "off-when-on", "off-noop"],
    )
    async def test_state_transition(
        self,
        runstate: str,
        opmode: str,
        action: str,
        expected_value: str | None,
    ):
        pump = self._make_fan({"runstate": runstate, "opmode": opmode})
        pump.system.send_control_command = async_returns(MagicMock())
        await getattr(pump, action)()
        if expected_value is not None:
            pump.system.send_control_command.assert_awaited_once_with(
                "/opmode/write", f"value={expected_value}"
            )
        else:
            pump.system.send_control_command.assert_not_awaited()

    def test_preset_modes_list(self):
        pump = self._make_fan({"opmode": "1"})
        assert "CUSTOM" in pump.preset_modes
        assert "QUICK_CLEAN" not in pump.preset_modes

    def test_preset_mode_for_external_mode(self):
        pump = self._make_fan({"opmode": "1"})
        assert pump.preset_mode == "CUSTOM"

    def test_preset_mode_for_internal_mode_readable(self):
        from iaqualink.systems.i2d.device import I2dOpMode

        pump = self._make_fan({"opmode": str(I2dOpMode.QUICK_CLEAN)})
        assert pump.preset_mode == "QUICK_CLEAN"
        assert "QUICK_CLEAN" not in pump.preset_modes

    def test_preset_mode_when_opmode_missing(self):
        pump = self._make_fan({})
        assert pump.preset_mode is None

    async def test_set_percentage_svrs_bounds(self):
        # SVRS pump: min=1050, max=3450 — 0% → 1050, 100% → 3450
        pump = self._make_fan(
            {"globalrpmmin": "1050", "globalrpmmax": "3450", "productid": "0F"}
        )
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.set_percentage(0)
        pump.system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=1050"
        )

    async def test_set_percentage_rounding(self):
        # 600 + (3450-600)*33/100 = 600 + 940.5 = 1540.5 → round to nearest 25 = 1550
        pump = self._make_fan({"globalrpmmin": "600", "globalrpmmax": "3450"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.set_percentage(33)
        pump.system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=1550"
        )

    async def test_set_percentage_clamps_to_max(self):
        pump = self._make_fan({"globalrpmmin": "600", "globalrpmmax": "3450"})
        pump.system.send_control_command = async_returns(MagicMock())
        await pump.set_percentage(100)
        pump.system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=3450"
        )

    async def test_turn_on_calls_apply_write_response(self):
        pump = self._make_fan({"runstate": "off", "opmode": "2"})
        mock_resp = MagicMock()
        pump.system.send_control_command = async_returns(mock_resp)
        await pump.turn_on()
        pump.system._apply_write_response.assert_called_once_with(mock_resp)

    async def test_set_percentage_calls_apply_write_response(self):
        pump = self._make_fan(
            {
                "globalrpmmin": "600",
                "globalrpmmax": "3450",
                "customspeedrpm": "600",
            }
        )
        mock_resp = MagicMock()
        pump.system.send_control_command = async_returns(mock_resp)
        await pump.set_percentage(50)
        pump.system._apply_write_response.assert_called_once_with(mock_resp)


class TestI2dBinaryState:
    def test_on_value(self):
        from iaqualink.systems.i2d.device import I2dBinaryState

        assert I2dBinaryState.ON == "1"

    def test_off_value(self):
        from iaqualink.systems.i2d.device import I2dBinaryState

        assert I2dBinaryState.OFF == "0"


class TestI2dNumberConstructorValidation:
    def test_missing_both_min_raises(self):
        system = create_autospec(I2dSystem, instance=True)
        with pytest.raises(ValueError):
            I2dNumber(system, {}, key="x", label="X", max_value=100.0)

    def test_missing_both_max_raises(self):
        system = create_autospec(I2dSystem, instance=True)
        with pytest.raises(ValueError):
            I2dNumber(system, {}, key="x", label="X", min_value=0.0)


def _make_binary_sensor(
    data: dict,
    key: str = "freezeprotectstatus",
    label: str = "Freeze Protect Status",
) -> I2dBinarySensor:
    system = create_autospec(I2dSystem, instance=True)
    return I2dBinarySensor(system, data, key=key, label=label)


class TestI2dBinarySensor:
    def test_name(self):
        s = _make_binary_sensor({"freezeprotectstatus": "0"})
        assert s.name == "freezeprotectstatus"

    def test_label(self):
        s = _make_binary_sensor({"freezeprotectstatus": "0"})
        assert s.label == "Freeze Protect Status"

    @pytest.mark.parametrize(
        "data,expected",
        [
            ({"freezeprotectstatus": "1"}, True),
            ({"freezeprotectstatus": "0"}, False),
            ({}, False),
        ],
        ids=["on", "off", "missing"],
    )
    def test_is_on(self, data: dict, expected: bool):
        s = _make_binary_sensor(data)
        assert s.is_on is expected

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
