from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.i2d.device import IQPumpDevice
from iaqualink.systems.i2d.system import I2DSystem

from ...common import async_noop, async_raises

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


class TestI2DSystem(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        pass

    def test_from_data_iqpump(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is not None
        assert isinstance(r, I2DSystem)

    async def test_update_success(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        system = AqualinkSystem.from_data(aqualink, data)
        system.send_devices_request = async_noop
        system._parse_alldata_response = MagicMock()
        await system.update()
        assert system.online is True

    async def test_update_service_exception(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        system = AqualinkSystem.from_data(aqualink, data)
        system.send_devices_request = async_raises(AqualinkServiceException)
        with pytest.raises(AqualinkServiceException):
            await system.update()
        assert system.online is None

    async def test_update_offline(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        system = AqualinkSystem.from_data(aqualink, data)
        system.send_devices_request = async_noop
        system._parse_alldata_response = MagicMock(
            side_effect=AqualinkSystemOfflineException
        )
        with pytest.raises(AqualinkSystemOfflineException):
            await system.update()
        assert system.online is False

    async def test_update_throttled(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        system = AqualinkSystem.from_data(aqualink, data)
        system.send_devices_request = async_raises(
            AqualinkServiceThrottledException
        )
        initial_online = system.online
        with pytest.raises(AqualinkServiceThrottledException):
            await system.update()
        # Rate limiting must not change online status.
        assert system.online is initial_online

    async def test_update_skipped_within_refresh_interval(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        system = AqualinkSystem.from_data(aqualink, data)
        system.send_devices_request = async_noop
        system._parse_alldata_response = MagicMock()

        # First update should go through.
        now = int(time.time())
        with patch("iaqualink.systems.i2d.system.time") as mock_time:
            mock_time.time.return_value = now
            await system.update()
        assert system._parse_alldata_response.call_count == 1

        # Second update within MIN_SECS_TO_REFRESH should be skipped.
        system._parse_alldata_response.reset_mock()
        with patch("iaqualink.systems.i2d.system.time") as mock_time:
            mock_time.time.return_value = (
                now + I2DSystem.MIN_SECS_TO_REFRESH - 1
            )
            await system.update()
        assert system._parse_alldata_response.call_count == 0

        # Update after MIN_SECS_TO_REFRESH should go through.
        with patch("iaqualink.systems.i2d.system.time") as mock_time:
            mock_time.time.return_value = now + I2DSystem.MIN_SECS_TO_REFRESH
            await system.update()
        assert system._parse_alldata_response.call_count == 1

    def test_parse_alldata_response(self):
        aqualink = MagicMock()
        aqualink.name = "Pool Pump"
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "iQPump",
        }
        system = I2DSystem.from_data(aqualink, data)

        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        system._parse_alldata_response(response)

        assert len(system.devices) == 1
        assert "ABC123" in system.devices
        device = system.devices["ABC123"]
        assert isinstance(device, IQPumpDevice)

        assert device.is_on is True
        assert device.state == "on"
        assert device.motor_speed == 1500
        assert device.motor_power == 180
        assert device.motor_temperature == 110
        assert device.horsepower == 1.65
        assert device.opmode == 0
        assert device.rpm_min == 600
        assert device.rpm_max == 3450
        assert device.custom_speed_rpm == 1500
        assert device.freeze_protect_enabled is True
        assert device.freeze_protect_active is False

    def test_parse_alldata_response_updates_existing_device(self):
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "iQPump",
        }
        system = I2DSystem.from_data(aqualink, data)

        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        system._parse_alldata_response(response)
        first_device = system.devices["ABC123"]

        # Parse again — should update existing device object, not replace it.
        system._parse_alldata_response(response)
        assert system.devices["ABC123"] is first_device

    def test_parse_alldata_response_offline(self):
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pool Pump",
            "device_type": "iQPump",
        }
        system = I2DSystem.from_data(aqualink, data)

        response = MagicMock()
        response.json.return_value = OFFLINE_DATA
        with pytest.raises(AqualinkSystemOfflineException):
            system._parse_alldata_response(response)

    @patch("httpx.AsyncClient.request")
    async def test_send_devices_request(self, mock_request):
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        aqualink = AqualinkClient("user", "pass")
        system = I2DSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 200
        await system.send_devices_request()

        assert mock_request.called
        call_kwargs = mock_request.call_args
        assert call_kwargs[0][0] == "post"

    @patch("httpx.AsyncClient.request")
    async def test_send_devices_request_unauthorized(self, mock_request):
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        aqualink = AqualinkClient("user", "pass")
        system = I2DSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await system.send_devices_request()

    @patch("httpx.AsyncClient.request")
    async def test_send_control_command(self, mock_request):
        data = {"id": 1, "serial_number": "ABC123", "device_type": "iQPump"}
        aqualink = AqualinkClient("user", "pass")
        system = I2DSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 200
        await system.send_control_command("/opmode/write", "value=1")

        assert mock_request.called
        call_kwargs = mock_request.call_args
        assert call_kwargs[0][0] == "post"
