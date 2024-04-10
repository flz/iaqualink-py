from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.exo.system import ExoSystem

from ...common import async_noop, async_raises

SAMPLE_DATA = {
    "state": {
        "reported": {
            "vr": "V85W4",
            "aws": {
                "status": "connected",
                "timestamp": 123,
                "session_id": "xxxx",
            },
            "hmi": {
                "ff": {
                    "fn": "/fluidra-ota-prod/exo/V85W4_OTA.bin",
                    "vr": "V85W4",
                    "ts": 123,
                    "pg": {"fs": 507300, "bd": 507300, "ts": 123, "te": 123},
                },
                "fw": {
                    "fn": "/fluidra-ota-prod/exo/V85W4_OTA.bin",
                    "vr": "V85W4",
                },
            },
            "main": {
                "ff": {
                    "fn": "/fluidra-ota-prod/exo/V85R67_OTA.bin",
                    "vr": "V85R67",
                    "ts": 123,
                    "pg": {"fs": 402328, "bd": 402328, "ts": 123, "te": 123},
                }
            },
            "debug": {
                "RSSI": -26,
                "OTA fail": 1,
                "OTA State": 0,
                "Last error": 65278,
                "Still alive": 2,
                "OTA success": 9,
                "MQTT connection": 2,
                "OTA fail global": 0,
                "Version Firmware": "V85W4B0",
                "Nb_Success_Pub_MSG": 463,
                "Nb_Fail_Publish_MSG": 0,
                "Nb_Success_Sub_Receive": 2,
                "MQTT disconnection total": 1,
                "OTA fail by disconnection": 0,
                "Nb reboot du to MQTT issue": 669,
            },
            "state": {"reported": {"debug_main": {"tr": 100}}},
            "equipment": {
                "swc_0": {
                    "vr": "V85R67",
                    "sn": "xxxxx",
                    "amp": 1,
                    "vsp": 1,
                    "low": 0,
                    "swc": 50,
                    "temp": 1,
                    "lang": 2,
                    "ph_sp": 74,
                    "sns_1": {"state": 1, "value": 75, "sensor_type": "Ph"},
                    "aux_1": {
                        "type": "none",
                        "mode": 0,
                        "color": 0,
                        "state": 0,
                    },
                    "sns_2": {"state": 1, "value": 780, "sensor_type": "Orp"},
                    "sns_3": {
                        "state": 1,
                        "value": 29,
                        "sensor_type": "Water temp",
                    },
                    "aux_2": {
                        "type": "none",
                        "mode": 0,
                        "state": 0,
                        "color": 0,
                    },
                    "boost": 0,
                    "orp_sp": 830,
                    "aux230": 1,
                    "ph_only": 1,
                    "swc_low": 0,
                    "version": "V1",
                    "exo_state": 1,
                    "dual_link": 1,
                    "production": 1,
                    "error_code": 0,
                    "boost_time": "24:00",
                    "filter_pump": {"type": 1, "state": 1},
                    "error_state": 0,
                }
            },
            "schedules": {
                "sch9": {
                    "id": "sch_9",
                    "name": "Aux 1",
                    "timer": {"end": "00:00", "start": "00:00"},
                    "active": 0,
                    "enabled": 0,
                    "endpoint": "aux1",
                },
                "sch1": {
                    "id": "sch_1",
                    "name": "Salt Water Chlorinator 1",
                    "timer": {"end": "00:00", "start": "00:00"},
                    "active": 0,
                    "enabled": 0,
                    "endpoint": "swc_1",
                },
                "sch3": {
                    "id": "sch_3",
                    "name": "Filter Pump 1",
                    "timer": {"end": "00:00", "start": "00:00"},
                    "active": 0,
                    "enabled": 0,
                    "endpoint": "ssp_1",
                },
                "sch4": {
                    "id": "sch_4",
                    "name": "Filter Pump 2",
                    "timer": {"end": "00:00", "start": "00:00"},
                    "active": 0,
                    "enabled": 0,
                    "endpoint": "ssp_2",
                },
                "sch2": {
                    "id": "sch_2",
                    "name": "Salt Water Chlorinator 2",
                    "timer": {"end": "00:00", "start": "00:00"},
                    "active": 0,
                    "enabled": 0,
                    "endpoint": "swc_2",
                },
                "sch10": {
                    "id": "sch_10",
                    "name": "Aux 2",
                    "timer": {"end": "00:00", "start": "00:00"},
                    "active": 0,
                    "enabled": 0,
                    "endpoint": "aux2",
                },
                "supported": 6,
                "programmed": 0,
            },
        }
    },
    "deviceId": "123",
    "ts": 123,
}


class TestExoSystem(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        pass

    def test_from_data_iaqua(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is not None
        assert isinstance(r, ExoSystem)

    async def test_update_success(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.send_reported_state_request = async_noop
        r._parse_shadow_response = MagicMock()
        await r.update()
        assert r.online is True

    async def test_update_service_exception(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.send_reported_state_request = async_raises(AqualinkServiceException)
        with pytest.raises(AqualinkServiceException):
            await r.update()
        assert r.online is None

    async def test_update_offline(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.send_reported_state_request = async_noop
        r._send_devices_screen_request = async_noop
        r._parse_shadow_response = MagicMock(
            side_effect=AqualinkSystemOfflineException
        )

        with pytest.raises(AqualinkSystemOfflineException):
            await r.update()
        assert r.online is False

    @pytest.mark.xfail
    async def test_parse_devices_offline(self):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        aqualink = MagicMock()
        system = AqualinkSystem.from_data(aqualink, data)

        message = {"message": "", "devices_screen": [{"status": "Offline"}]}
        response = MagicMock()
        response.json.return_value = message

        with pytest.raises(AqualinkSystemOfflineException):
            system._parse_shadow_response(response)
        assert system.devices == {}

    @pytest.mark.xfail
    async def test_parse_devices_good(self):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        aqualink = MagicMock()
        system = ExoSystem.from_data(aqualink, data)

        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        system._parse_shadow_response(response)
        assert system.devices == {}

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request(self, mock_request):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        aqualink = AqualinkClient("user", "pass")
        system = ExoSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 200

        await system.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_unauthorized(self, mock_request):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "exo"}
        aqualink = AqualinkClient("user", "pass")
        system = ExoSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await system.send_reported_state_request()
