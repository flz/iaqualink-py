from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.i2d.device import (
    I2dBinarySensor,
    I2dNumber,
    I2dSensor,
    I2dSwitch,
    I2dPump,
    I2dOpMode,
)
from iaqualink.systems.i2d.system import I2dSystem

from ...base_test_system import TestBaseSystem
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
        "primingtimer": "0",
        "freezeprotectenable": "1",
        "freezeprotectrpm": "1000",
        "freezeprotectperiod": "30",
        "freezeprotectsetpointc": "4",
        "freezeprotectstatus": "0",
        "currentspan": "-1",
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


_CONTRACT_DATA = {
    "id": 1,
    "serial_number": "ABC123",
    "name": "Pool Pump",
    "device_type": "i2d",
}


class TestI2dSystemContract(TestBaseSystem):
    """Verifies I2dSystem satisfies the AqualinkSystem API contract."""

    def setUp(self) -> None:
        super().setUp()
        self.sut = I2dSystem.from_data(self.client, _CONTRACT_DATA)
        self.sut_class = I2dSystem

    def _set_online(self, _response: object) -> None:
        self.sut.status = SystemStatus.ONLINE

    async def test_refresh_success(self) -> None:
        with patch.object(
            self.sut, "_parse_alldata_response", side_effect=self._set_online
        ):
            await super().test_refresh_success()

    async def test_get_devices_needs_update(self) -> None:
        with patch.object(
            self.sut, "_parse_alldata_response", side_effect=self._set_online
        ):
            await super().test_get_devices_needs_update()


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

        # 1 pump + 16 numbers + 1 switch + 11 sensors + 1 binary sensor
        assert len(system.devices) == 30
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

        pt = system.devices["primingtimer"]
        assert isinstance(pt, I2dSensor)
        assert pt.state == "0"
        assert pt.unit == "s"

        qct = system.devices["quickcleantimer"]
        assert isinstance(qct, I2dSensor)
        assert qct.state == "0"
        assert qct.unit == "s"

        cdt = system.devices["countdowntimer"]
        assert isinstance(cdt, I2dSensor)
        assert cdt.state == "0"
        assert cdt.unit == "s"

        tot = system.devices["timeouttimer"]
        assert isinstance(tot, I2dSensor)
        assert tot.state == "0"
        assert tot.unit == "s"

        cs = system.devices["currentspan"]
        assert isinstance(cs, I2dSensor)
        assert cs.state == "-1"
        assert cs.unit is None

        fps = system.devices["freezeprotectstatus"]
        assert isinstance(fps, I2dBinarySensor)
        assert fps.is_on is False
        assert fps.state == "off"

        k1 = system.devices["relayK1Rpm"]
        assert isinstance(k1, I2dNumber)
        assert k1.current_value == 1500.0
        assert k1.min_value == 600.0
        assert k1.max_value == 3450.0
        assert k1.step == 25.0
        assert k1.unit == "RPM"

        k2 = system.devices["relayK2Rpm"]
        assert isinstance(k2, I2dNumber)
        assert k2.current_value == 1200.0

        ws = system.devices["wifistate"]
        assert isinstance(ws, I2dSensor)
        assert ws.state == "connected"
        assert ws.label == "WiFi State"
        assert ws.unit is None

        wssid = system.devices["wifissid"]
        assert isinstance(wssid, I2dSensor)
        assert wssid.state == "MyNetwork"
        assert wssid.label == "WiFi SSID"

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
        aqualink.authentication_token = "tok123"
        aqualink.user_id = "42"
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)

        mock_request.return_value.status_code = 200
        await system.send_control_command("/opmode/write", "value=1")

        assert mock_request.called
        call_kwargs = mock_request.call_args
        assert call_kwargs[0][0] == "post"
        body = call_kwargs[1]["json"]
        assert body["api_key"] == AQUALINK_API_KEY
        assert body["authentication_token"] == "tok123"
        assert body["user_id"] == "42"
        assert body["command"] == "/opmode/write"
        assert body["params"] == "value=1"

    @patch("httpx.AsyncClient.request")
    async def test_send_control_command_unauthorized(self, mock_request):
        aqualink = AqualinkClient("user", "pass")
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)

        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await system.send_control_command("/alldata/read")

    def _make_system_with_devices(self):
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
        return system

    def _write_response(self, key: str, value: str) -> MagicMock:
        r = MagicMock()
        r.json.return_value = {
            key: {"operation": "write", "value": value},
            "requestID": "x",
        }
        return r

    def test_apply_write_response_updates_shared_data(self):
        system = self._make_system_with_devices()
        r = self._write_response("opmode", "1")
        system._apply_write_response(r)
        assert system.devices["ABC123"].data["opmode"] == "1"

    def test_apply_write_response_skips_requestid(self):
        system = self._make_system_with_devices()
        r = MagicMock()
        r.json.return_value = {
            "requestID": "abc",
            "opmode": {"operation": "write", "value": "2"},
        }
        system._apply_write_response(r)
        assert system.devices["ABC123"].data["opmode"] == "2"
        assert (
            "requestID" not in system.devices["ABC123"].data
            or system.devices["ABC123"].data.get("requestID") != "abc"
        )

    def test_apply_write_response_ignores_non_write_operation(self):
        system = self._make_system_with_devices()
        original = system.devices["ABC123"].data["opmode"]
        r = MagicMock()
        r.json.return_value = {"opmode": {"operation": "read", "value": "5"}}
        system._apply_write_response(r)
        assert system.devices["ABC123"].data["opmode"] == original

    def test_apply_write_response_ignores_missing_value(self):
        system = self._make_system_with_devices()
        original = system.devices["ABC123"].data["opmode"]
        r = MagicMock()
        r.json.return_value = {"opmode": {"operation": "write"}}
        system._apply_write_response(r)
        assert system.devices["ABC123"].data["opmode"] == original

    def test_apply_write_response_noop_before_devices_populated(self):
        aqualink = MagicMock()
        system = I2dSystem.from_data(aqualink, _SYSTEM_DATA)
        r = self._write_response("opmode", "1")
        system._apply_write_response(r)  # no error; serial not in devices yet

    def test_apply_write_response_noop_on_invalid_json(self):
        system = self._make_system_with_devices()
        r = MagicMock()
        r.json.side_effect = ValueError("not json")
        system._apply_write_response(r)  # no error

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
