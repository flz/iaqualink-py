from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.i2d.device import (
    I2dNumber,
    I2dSensor,
    I2dSwitch,
    I2dPump,
    I2dOpMode,
)
from iaqualink.systems.i2d.system import I2dSystem

from ...common import async_raises, async_returns

# Values captured from a real iQPump device. Some period/timer fields fall
# outside the step-aligned write ranges — read values are not required to
# satisfy write constraints.
SAMPLE_DATA = {
    "alldata": {
        "motordata": {
            "speed": "1500",
            "power": "180",
            "temperature": "110",
            "productid": "1A",
            "horsepower": "1.65",
            "horsepowercode": "0A",
            "updateprogress": "0",
        },
        "wifistatus": {"state": "connected", "ssid": "MyNetwork"},
        "opmode": "0",
        "runstate": "on",
        "fwversion": "1.5.2",
        "RS485fwversion": "1.0.0",
        "localtime": "12:34",
        "timezone": "America/Los_Angeles",
        "utctime": "1700000000",
        "hotspottimer": "5",
        "busstatus": "0",
        "updateprogress": "0",
        "updateflag": "0",
        "serialnumber": "ABC123",
        "rpmtarget": "1500",
        "globalrpmmin": "600",
        "globalrpmmax": "3450",
        "customspeedrpm": "1500",
        "customspeedtimer": "60",
        "quickcleanrpm": "3450",
        "quickcleanperiod": "8",
        "quickcleantimer": "0",
        "countdownrpm": "1500",
        "countdownperiod": "30",
        "countdowntimer": "0",
        "timeoutperiod": "10",
        "timeouttimer": "0",
        "primingrpm": "3450",
        "primingperiod": "3",
        "freezeprotectenable": "1",
        "freezeprotectrpm": "1000",
        "freezeprotectperiod": "30",
        "freezeprotectsetpointc": "4",
        "freezeprotectstatus": "0",
        "demandvisible": "0",
        "faultvisible": "0",
        "relayK1Rpm": "1500",
        "relayK2Rpm": "1200",
    },
    "requestID": "abc123",
}

OFFLINE_DATA = {
    "status": "500",
    "error": {"message": "Device offline."},
}

_SYSTEM_DATA = {"id": 1, "serial_number": "ABC123", "device_type": "i2d"}


class TestI2dSystem(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        pass

    def test_from_data_i2d(self):
        aqualink = MagicMock()
        r = AqualinkSystem.from_data(aqualink, _SYSTEM_DATA)
        assert r is not None
        assert isinstance(r, I2dSystem)

    async def test_refresh_connected(self):
        aqualink = MagicMock()
        system = AqualinkSystem.from_data(aqualink, _SYSTEM_DATA)
        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        system.send_control_command = async_returns(response)
        await system.refresh()
        assert system.status is SystemStatus.CONNECTED

    async def test_refresh_service_exception(self):
        aqualink = MagicMock()
        system = AqualinkSystem.from_data(aqualink, _SYSTEM_DATA)
        system.send_control_command = async_raises(AqualinkServiceException)
        with pytest.raises(AqualinkServiceException):
            await system.refresh()
        assert system.status is SystemStatus.DISCONNECTED

    async def test_refresh_offline_body(self):
        aqualink = MagicMock()
        system = AqualinkSystem.from_data(aqualink, _SYSTEM_DATA)
        response = MagicMock()
        response.json.return_value = OFFLINE_DATA
        system.send_control_command = async_returns(response)
        await system.refresh()
        assert system.status is SystemStatus.DISCONNECTED

    async def test_refresh_throttled(self):
        aqualink = MagicMock()
        system = AqualinkSystem.from_data(aqualink, _SYSTEM_DATA)
        system.send_control_command = async_raises(
            AqualinkServiceThrottledException
        )
        with pytest.raises(AqualinkServiceThrottledException):
            await system.refresh()
        assert system.status is SystemStatus.UNKNOWN

    def test_parse_alldata_response(self):
        aqualink = MagicMock()
        aqualink.name = "Pool Pump"
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)

        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        system._parse_alldata_response(response)

        # 1 pump + 14 numbers + 1 switch + 4 sensors
        assert len(system.devices) == 20
        assert "ABC123" in system.devices
        device = system.devices["ABC123"]
        assert isinstance(device, I2dPump)

        assert device.is_on is True
        assert device.state == "0"
        assert device.state_translated == "SCHEDULE"
        assert device.rpm_min == 600
        assert device.rpm_max == 3450
        assert device.custom_speed_rpm == 1500

        # spot-check a few number devices
        qc = system.devices["quickcleanrpm"]
        assert isinstance(qc, I2dNumber)
        assert qc.current_value == 3450.0
        assert qc.min_value == 600.0
        assert qc.max_value == 3450.0
        assert qc.unit == "RPM"

        cs = system.devices["customspeedrpm"]
        assert isinstance(cs, I2dNumber)
        assert cs.current_value == 1500.0

        rpmmin = system.devices["globalrpmmin"]
        assert isinstance(rpmmin, I2dNumber)
        assert (
            rpmmin.min_value == 600.0
        )  # productid "1A" = non-SVRS, _rpmhwmin=600
        assert rpmmin.max_value == 3450.0  # live from globalrpmmax
        assert rpmmin.step == 25.0

        rpmmax = system.devices["globalrpmmax"]
        assert isinstance(rpmmax, I2dNumber)
        assert rpmmax.min_value == 600.0  # live from globalrpmmin
        assert rpmmax.max_value == 3450.0

        sp = system.devices["freezeprotectsetpointc"]
        assert isinstance(sp, I2dNumber)
        assert sp.current_value == 4.0
        assert sp.unit == "°C"

        sw = system.devices["freezeprotectenable"]
        assert isinstance(sw, I2dSwitch)
        assert sw.is_on is True

        speed = system.devices["speed"]
        assert isinstance(speed, I2dSensor)
        assert speed.state == "1500"
        assert speed.unit == "RPM"

        hp = system.devices["horsepower"]
        assert isinstance(hp, I2dSensor)
        assert hp.state == "1.65"
        assert hp.unit == "HP"

    def test_parse_alldata_response_updates_existing_device(self):
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)

        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        system._parse_alldata_response(response)
        first_pump = system.devices["ABC123"]
        first_qc = system.devices["quickcleanrpm"]
        first_sw = system.devices["freezeprotectenable"]

        system._parse_alldata_response(response)
        assert system.devices["ABC123"] is first_pump
        assert system.devices["quickcleanrpm"] is first_qc
        assert system.devices["freezeprotectenable"] is first_sw

    def test_parse_alldata_response_offline(self):
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)

        response = MagicMock()
        response.json.return_value = OFFLINE_DATA
        system._parse_alldata_response(response)
        assert system.status is SystemStatus.DISCONNECTED

    def test_parse_alldata_response_service_opmode(self):
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)
        service_data = {
            "alldata": {**SAMPLE_DATA["alldata"], "opmode": "5"},
            "requestID": "x",
        }
        response = MagicMock()
        response.json.return_value = service_data
        system._parse_alldata_response(response)
        assert system.status is SystemStatus.SERVICE

    def test_parse_alldata_response_firmware_update(self):
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)
        alldata_no_opmode = {
            k: v for k, v in SAMPLE_DATA["alldata"].items() if k != "opmode"
        }
        fw_data = {
            "alldata": {**alldata_no_opmode, "updateprogress": "50/100"},
            "requestID": "x",
        }
        response = MagicMock()
        response.json.return_value = fw_data
        system._parse_alldata_response(response)
        assert system.status is SystemStatus.FIRMWARE_UPDATE

    def test_parse_alldata_response_unknown_no_opmode_no_progress(self):
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)
        alldata_no_opmode = {
            k: v for k, v in SAMPLE_DATA["alldata"].items() if k != "opmode"
        }
        unknown_data = {
            "alldata": {**alldata_no_opmode, "updateprogress": "0/0"},
            "requestID": "x",
        }
        response = MagicMock()
        response.json.return_value = unknown_data
        system._parse_alldata_response(response)
        assert system.status is SystemStatus.UNKNOWN

    @patch("httpx.AsyncClient.request")
    async def test_send_control_command(self, mock_request):
        aqualink = AqualinkClient("user", "pass")
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)

        mock_request.return_value.status_code = 200
        await system.send_control_command("/opmode/write", "value=1")

        assert mock_request.called
        call_kwargs = mock_request.call_args
        assert call_kwargs[0][0] == "post"

    @patch("httpx.AsyncClient.request")
    async def test_send_control_command_unauthorized(self, mock_request):
        aqualink = AqualinkClient("user", "pass")
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)

        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await system.send_control_command("/alldata/read")

    def test_opmode_enum_values(self):
        assert I2dOpMode.SCHEDULE == "0"
        assert I2dOpMode.CUSTOM == "1"
        assert I2dOpMode.STOP == "2"
        assert I2dOpMode.QUICK_CLEAN == "3"
        assert I2dOpMode.TIMED_RUN == "4"
        assert I2dOpMode.TIMEOUT == "5"
        assert I2dOpMode.SERVICE_OFF == "7"

    def test_pump_supports_presets(self):
        aqualink = MagicMock()
        aqualink.name = "Pool Pump"
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)
        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        system._parse_alldata_response(response)
        pump = system.devices["ABC123"]
        assert pump.supports_presets is True
        assert set(pump.supported_presets) == {"SCHEDULE", "CUSTOM", "STOP"}

    def test_pump_current_preset(self):
        aqualink = MagicMock()
        aqualink.name = "Pool Pump"
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "i2d",
        }
        system = I2dSystem.from_data(aqualink, data)
        response = MagicMock()
        response.json.return_value = SAMPLE_DATA  # opmode=0 → SCHEDULE
        system._parse_alldata_response(response)
        pump = system.devices["ABC123"]
        assert pump.current_preset == "SCHEDULE"

    async def test_pump_set_preset_valid(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        system.send_control_command = async_returns(MagicMock())
        system._parse_alldata_response = MagicMock()
        # Directly construct a pump to test set_preset
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(
            system, {"name": "ABC123", "opmode": "0", "runstate": "on"}
        )
        await pump.set_preset("STOP")
        system.send_control_command.assert_awaited_once_with(
            "/opmode/write", "value=2"
        )

    async def test_pump_set_preset_invalid_raises(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(system, {"name": "ABC123", "opmode": "0"})
        with pytest.raises(AqualinkInvalidParameterException):
            await pump.set_preset("QUICK_CLEAN")

    async def test_pump_set_preset_unknown_raises(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(system, {"name": "ABC123", "opmode": "0"})
        with pytest.raises(AqualinkInvalidParameterException):
            await pump.set_preset("BOGUS")

    def test_pump_supports_set_speed_percentage(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(
            system,
            {"name": "ABC123", "globalrpmmin": "600", "globalrpmmax": "3450"},
        )
        assert pump.supports_set_speed_percentage is True

    async def test_set_speed_percentage_0_gives_rpm_min(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        system.send_control_command = async_returns(MagicMock())
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(
            system,
            {"name": "ABC123", "globalrpmmin": "600", "globalrpmmax": "3450"},
        )
        await pump.set_speed_percentage(0)
        system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=600"
        )

    async def test_set_speed_percentage_100_gives_rpm_max(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        system.send_control_command = async_returns(MagicMock())
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(
            system,
            {"name": "ABC123", "globalrpmmin": "600", "globalrpmmax": "3450"},
        )
        await pump.set_speed_percentage(100)
        system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=3450"
        )

    async def test_set_speed_percentage_50_rounded(self):
        # 600 + (3450-600)*0.5 = 2025 — already multiple of 25
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        system.send_control_command = async_returns(MagicMock())
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(
            system,
            {"name": "ABC123", "globalrpmmin": "600", "globalrpmmax": "3450"},
        )
        await pump.set_speed_percentage(50)
        system.send_control_command.assert_awaited_once_with(
            "/customspeedrpm/write", "value=2025"
        )

    async def test_set_speed_percentage_out_of_range_raises(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        from iaqualink.systems.i2d.device import I2dPump

        pump = I2dPump(
            system,
            {"name": "ABC123", "globalrpmmin": "600", "globalrpmmax": "3450"},
        )
        with pytest.raises(AqualinkInvalidParameterException):
            await pump.set_speed_percentage(101)
        with pytest.raises(AqualinkInvalidParameterException):
            await pump.set_speed_percentage(-1)
