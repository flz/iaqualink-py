from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx.router

from iaqualink.exception import (
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.exo.device import (
    ExoAttributeSwitch,
    ExoAuxSwitch,
    ExoSensor,
)
from iaqualink.systems.exo.system import ExoSystem

import respx

from ...base import dotstar
from ...base_test_system import TestBaseSystem

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


class TestExoSystem(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "id": 1,
            "serial_number": "ABCDEFG",
            "device_type": "exo",
            "name": "Pool",
        }
        self.sut = AqualinkSystem.from_data(self.client, data=data)
        self.sut_class = ExoSystem

    @respx.mock
    async def test_update_success(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(httpx.Response(200, json=SAMPLE_DATA))
        await self.sut.update()
        assert len(respx_mock.calls) > 0
        assert self.sut.status is SystemStatus.CONNECTED
        self.respx_calls = copy.copy(respx_mock.calls)

    async def test_update_throttled(self) -> None:
        with patch.object(self.sut, "send_reported_state_request") as mock_req:
            mock_req.side_effect = AqualinkServiceThrottledException
            with pytest.raises(AqualinkServiceThrottledException):
                await self.sut.update()
        assert self.sut.status is SystemStatus.UNKNOWN

    async def test_update_offline(self) -> None:
        with patch.object(self.sut, "_parse_shadow_response") as mock_parse:
            mock_parse.side_effect = AqualinkSystemOfflineException
            with pytest.raises(AqualinkSystemOfflineException):
                await super().test_update_success()

    async def test_get_devices_needs_update(self) -> None:
        with patch.object(self.sut, "_parse_shadow_response"):
            await super().test_get_devices_needs_update()

    def test_parse_devices_good(self) -> None:
        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        self.sut._parse_shadow_response(response)

        assert self.sut.status is SystemStatus.CONNECTED
        assert len(self.sut.devices) > 0
        # Chemistry sensors
        assert "sns_1" in self.sut.devices
        assert isinstance(self.sut.devices["sns_1"], ExoSensor)
        assert "sns_2" in self.sut.devices
        assert isinstance(self.sut.devices["sns_2"], ExoSensor)
        assert "sns_3" in self.sut.devices
        assert isinstance(self.sut.devices["sns_3"], ExoSensor)
        # Auxiliary switches
        assert "aux_1" in self.sut.devices
        assert isinstance(self.sut.devices["aux_1"], ExoAuxSwitch)
        assert "aux_2" in self.sut.devices
        assert isinstance(self.sut.devices["aux_2"], ExoAuxSwitch)
        # Attribute switches
        assert "boost" in self.sut.devices
        assert isinstance(self.sut.devices["boost"], ExoAttributeSwitch)
        assert "production" in self.sut.devices
        assert isinstance(self.sut.devices["production"], ExoAttributeSwitch)
        # Filter pump
        assert "filter_pump" in self.sut.devices
        # Excluded keys must be absent
        assert "sn" not in self.sut.devices
        assert "vr" not in self.sut.devices
        assert "version" not in self.sut.devices
        assert "boost_time" not in self.sut.devices

    def _make_shadow_response(self, aws_status: str | None) -> MagicMock:
        import copy as _copy

        data = _copy.deepcopy(SAMPLE_DATA)
        if aws_status is None:
            del data["state"]["reported"]["aws"]
        else:
            data["state"]["reported"]["aws"]["status"] = aws_status
        response = MagicMock()
        response.json.return_value = data
        return response

    def test_parse_shadow_absent_aws_status(self) -> None:
        response = self._make_shadow_response(None)
        self.sut._parse_shadow_response(response)
        assert self.sut.status is SystemStatus.ONLINE

    def test_parse_shadow_empty_aws_status(self) -> None:
        response = self._make_shadow_response("")
        self.sut._parse_shadow_response(response)
        assert self.sut.status is SystemStatus.IN_PROGRESS

    def test_parse_shadow_disconnected(self) -> None:
        response = self._make_shadow_response("disconnected")
        self.sut._parse_shadow_response(response)
        assert self.sut.status is SystemStatus.DISCONNECTED

    def test_parse_shadow_service(self) -> None:
        response = self._make_shadow_response("service")
        self.sut._parse_shadow_response(response)
        assert self.sut.status is SystemStatus.SERVICE

    def test_parse_shadow_firmware_update(self) -> None:
        response = self._make_shadow_response("firmware_update")
        self.sut._parse_shadow_response(response)
        assert self.sut.status is SystemStatus.FIRMWARE_UPDATE

    def test_parse_shadow_unknown_string(self) -> None:
        response = self._make_shadow_response("something_unknown")
        self.sut._parse_shadow_response(response)
        assert self.sut.status is SystemStatus.UNKNOWN

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200

        await self.sut.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_unauthorized(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.sut.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_retries_after_refresh(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=200),
        ]
        self.client.id_token = "old-id-token"

        async def fake_refresh() -> None:
            self.client.id_token = "new-id-token"

        with patch.object(
            self.client, "_refresh_auth", side_effect=fake_refresh
        ) as mock_refresh:
            await self.sut.send_reported_state_request()

        retry_headers = mock_request.call_args_list[1][1]["headers"]

        mock_refresh.assert_awaited_once()
        assert retry_headers["Authorization"] == "new-id-token"

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_refreshes_only_once_on_repeated_401(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=401),
        ]

        with (
            patch.object(
                self.client, "_refresh_auth", return_value=None
            ) as mock_refresh,
            pytest.raises(AqualinkServiceUnauthorizedException),
        ):
            await self.sut.send_reported_state_request()

        mock_refresh.assert_awaited_once()
