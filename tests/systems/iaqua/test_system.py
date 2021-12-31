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
from iaqualink.systems.iaqua.device import IaquaAuxToggle
from iaqualink.systems.iaqua.system import IaquaSystem

from ...common import async_noop, async_raises


class TestIaquaSystem(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        pass

    def test_from_data_iaqua(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is not None
        assert isinstance(r, IaquaSystem)

    async def test_update_success(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r._send_home_screen_request = async_noop
        r._send_devices_screen_request = async_noop
        r._parse_home_response = MagicMock()
        r._parse_devices_response = MagicMock()
        await r.update()
        assert r.online is True

    async def test_update_service_exception(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r._send_home_screen_request = async_raises(AqualinkServiceException)
        with pytest.raises(AqualinkServiceException):
            await r.update()
        assert r.online is None

    async def test_update_offline(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r._send_home_screen_request = async_noop
        r._send_devices_screen_request = async_noop
        r._parse_home_response = MagicMock(
            side_effect=AqualinkSystemOfflineException
        )

        with pytest.raises(AqualinkSystemOfflineException):
            await r.update()
        assert r.online is False

    async def test_parse_devices_offline(self):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        aqualink = MagicMock()
        system = AqualinkSystem.from_data(aqualink, data)

        message = {"message": "", "devices_screen": [{"status": "Offline"}]}
        response = MagicMock()
        response.json.return_value = message

        with pytest.raises(AqualinkSystemOfflineException):
            system._parse_devices_response(response)
        assert system.devices == {}

    async def test_parse_devices_good(self):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        aqualink = MagicMock()
        system = IaquaSystem.from_data(aqualink, data)

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
            "aux_B1": IaquaAuxToggle(
                system=system,
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
        system._parse_devices_response(response)
        assert system.devices == expected

    @patch("httpx.AsyncClient.request")
    async def test_home_request(self, mock_request):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        aqualink = AqualinkClient("user", "pass")
        system = IaquaSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 200

        await system._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_home_request_unauthorized(self, mock_request):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        aqualink = AqualinkClient("user", "pass")
        system = IaquaSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await system._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request(self, mock_request):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        aqualink = AqualinkClient("user", "pass")
        system = IaquaSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 200

        await system._send_devices_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request_unauthorized(self, mock_request):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        aqualink = AqualinkClient("user", "pass")
        system = IaquaSystem.from_data(aqualink, data)

        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await system._send_devices_screen_request()
