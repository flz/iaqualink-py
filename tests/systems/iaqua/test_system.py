from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock, ANY

import pytest
import httpx

from iaqualink.exception import (
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.iaqua.device import IaquaAuxSwitch
from iaqualink.systems.iaqua.system import IaquaSystem

from ...base_test_system import TestBaseSystem


class TestIaquaSystem(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "id": 123456,
            "serial_number": "SN123456",
            "created_at": "2017-09-23T01:00:08.000Z",
            "updated_at": "2017-09-23T01:00:08.000Z",
            "name": "Pool",
            "device_type": "iaqua",
            "owner_id": None,
            "updating": False,
            "firmware_version": None,
            "target_firmware_version": None,
            "update_firmware_start_at": None,
            "last_activity_at": None,
        }
        self.sut = AqualinkSystem.from_data(self.client, data=data)
        self.sut_class = IaquaSystem

    async def test_update_success(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            await super().test_update_success()

    async def test_update_offline(self) -> None:
        with patch.object(self.sut, "_parse_home_response") as mock_parse:
            mock_parse.side_effect = AqualinkSystemOfflineException
            with pytest.raises(AqualinkSystemOfflineException):
                await super().test_update_success()
            assert self.sut.online is False

    async def test_update_consecutive(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            await super().test_update_consecutive()

    async def test_get_devices_needs_update(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            await super().test_get_devices_needs_update()

    async def test_parse_devices_offline(self) -> None:
        message = {"message": "", "devices_screen": [{"status": "Offline"}]}
        response = MagicMock()
        response.json.return_value = message

        with pytest.raises(AqualinkSystemOfflineException):
            self.sut._parse_devices_response(response)
        assert self.sut.devices == {}

    async def test_parse_devices_good(self) -> None:
        message = {
            "message": "",
            "devices_screen": [
                {"status": "Online"},
                {"response": ""},
                {"group": "1"},
                {
                    "aux_B1": [
                        {"state": "0"},
                        {"label": "Label B1"},
                        {"icon": "aux_1_0.png"},
                        {"type": "0"},
                        {"subtype": "0"},
                    ]
                },
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        expected = {
            "aux_B1": IaquaAuxSwitch(
                system=self.sut,
                data={
                    "aux": "B1",
                    "name": "aux_B1",
                    "state": "0",
                    "label": "Label B1",
                    "icon": "aux_1_0.png",
                    "type": "0",
                    "subtype": "0",
                },
            )
        }
        self.sut._parse_devices_response(response)
        assert self.sut.devices == expected

    @patch("httpx.AsyncClient.request")
    async def test_home_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200

        await self.sut._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_home_request_unauthorized(self, mock_request) -> None:
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.sut._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200

        await self.sut._send_devices_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request_unauthorized(self, mock_request) -> None:
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.sut._send_devices_screen_request()

    @patch("httpx.AsyncClient.request", new_callable=AsyncMock)
    async def test_get_onetouch(self, mock_httpx_request):
        if not isinstance(self.sut.aqualink._client, httpx.AsyncClient) or isinstance(self.sut.aqualink._client, MagicMock):
             self.sut.aqualink._client = httpx.AsyncClient()
        self.sut.aqualink._id_token = "mock_test_id_token"
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={
            "onetouch_screen": [
                {"onetouch_1": [{"status": "1"}, {"state": "0"}, {"label": "All OFF"}]},
                {"onetouch_2": [{"status": "1"}, {"state": "0"}, {"label": "Spa Mode"}]},
            ]
        })
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_request.return_value = mock_response

        result = await self.sut.get_onetouch()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["label"] == "All OFF"
        assert result[0]["index"] == 1
        assert result[1]["label"] == "Spa Mode"
        assert result[1]["index"] == 2
        
        expected_url = f"https://p-api.iaqualink.net/v2/mobile/session.json?actionID=command&command=get_onetouch&serial={self.sut.serial}"
        # These are the headers as they are passed to httpx.AsyncClient.request
        expected_final_headers = {
            "user-agent": "okhttp/3.14.7",
            "content-type": "application/json",
            "authorization": "mock_test_id_token"
        }

        mock_httpx_request.assert_any_call(
            "get",
            expected_url,
            headers=expected_final_headers
            # No json, params, content, or data for this GET request directly to client.request
        )

    @patch("httpx.AsyncClient.request", new_callable=AsyncMock)
    async def test_set_onetouch(self, mock_httpx_request):
        if not isinstance(self.sut.aqualink._client, httpx.AsyncClient) or isinstance(self.sut.aqualink._client, MagicMock):
             self.sut.aqualink._client = httpx.AsyncClient()
        self.sut.aqualink._id_token = "mock_test_id_token"
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={
            "onetouch_screen": [
                {"onetouch_1": [{"status": "1"}, {"state": "1"}, {"label": "All OFF"}]},
                {"onetouch_2": [{"status": "1"}, {"state": "0"}, {"label": "Spa Mode"}]},
            ]
        })
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_request.return_value = mock_response

        onetouch_index_to_set = 1
        result = await self.sut.set_onetouch(onetouch_index_to_set)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["state"] == "1"
        assert result[0]["index"] == onetouch_index_to_set

        expected_url = "https://p-api.iaqualink.net/v2/mobile/session.json"
        expected_payload = {
            "actionID": "command", # Order changed to match code construction
            "command": f"set_onetouch_{onetouch_index_to_set}",
            "serial": self.sut.serial,
        }
        # These are the headers as they are passed to httpx.AsyncClient.request
        expected_final_headers = {
            "user-agent": "okhttp/3.14.7",
            "content-type": "application/json",
            "authorization": "mock_test_id_token"
        }
        
        mock_httpx_request.assert_any_call(
            "post",
            expected_url,
            headers=expected_final_headers,
            json=expected_payload
            # No params, content, or data for this POST request directly to client.request
        )
