from __future__ import annotations

import copy
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.exo.system import ExoSystem

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


def _make_exo_system() -> tuple[AqualinkClient, ExoSystem]:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "ABCDEFG",
        "device_type": "exo",
        "name": "Pool",
    }
    sut = cast(ExoSystem, AqualinkSystem.from_data(client, data=data))
    return client, sut


def _make_shadow_response(aws_status: str | None) -> MagicMock:
    data: dict[str, Any] = copy.deepcopy(SAMPLE_DATA)
    if aws_status is None:
        del data["state"]["reported"]["aws"]
    else:
        data["state"]["reported"]["aws"]["status"] = aws_status
    response = MagicMock()
    response.json.return_value = data
    return response


class TestExoSystem:
    def test_parse_shadow_absent_aws_status(self) -> None:
        _, sut = _make_exo_system()
        response = _make_shadow_response(None)
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    def test_parse_shadow_empty_aws_status(self) -> None:
        _, sut = _make_exo_system()
        response = _make_shadow_response("")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    def test_parse_shadow_disconnected(self) -> None:
        _, sut = _make_exo_system()
        response = _make_shadow_response("disconnected")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.DISCONNECTED

    def test_parse_shadow_service(self) -> None:
        _, sut = _make_exo_system()
        response = _make_shadow_response("service")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.SERVICE

    def test_parse_shadow_firmware_update(self) -> None:
        _, sut = _make_exo_system()
        response = _make_shadow_response("firmware_update")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.FIRMWARE_UPDATE

    def test_parse_shadow_unknown_string(self) -> None:
        _, sut = _make_exo_system()
        response = _make_shadow_response("something_unknown")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request(self, mock_request) -> None:
        _, sut = _make_exo_system()
        mock_request.return_value.status_code = 200
        await sut.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_unauthorized(
        self, mock_request
    ) -> None:
        _, sut = _make_exo_system()
        mock_request.return_value.status_code = 401
        with pytest.raises(AqualinkServiceUnauthorizedException):
            await sut.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_retries_after_refresh(
        self, mock_request
    ) -> None:
        client, sut = _make_exo_system()
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=200),
        ]
        client.id_token = "old-id-token"

        async def fake_refresh() -> None:
            client.id_token = "new-id-token"

        with patch.object(
            client, "_refresh_auth", side_effect=fake_refresh
        ) as mock_refresh:
            await sut.send_reported_state_request()

        retry_headers = mock_request.call_args_list[1][1]["headers"]

        mock_refresh.assert_awaited_once()
        assert retry_headers["Authorization"] == "new-id-token"

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_refreshes_only_once_on_repeated_401(
        self, mock_request
    ) -> None:
        client, sut = _make_exo_system()
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=401),
        ]

        with (
            patch.object(
                client, "_refresh_auth", return_value=None
            ) as mock_refresh,
            pytest.raises(AqualinkServiceUnauthorizedException),
        ):
            await sut.send_reported_state_request()

        mock_refresh.assert_awaited_once()
