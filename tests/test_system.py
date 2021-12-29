from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pytest

from iaqualink.device import AqualinkAuxToggle
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkPoolSystem, AqualinkSystem

from .common import async_noop, async_raises


class TestAqualinkSystem(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        pass

    def test_from_data_iaqua(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is not None
        assert isinstance(r, AqualinkPoolSystem)

    def test_from_data_unsupported(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "foo"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is None

    async def test_update_success(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.aqualink.send_home_screen_request = async_noop
        r.aqualink.send_devices_screen_request = async_noop
        r._parse_home_response = MagicMock()
        r._parse_devices_response = MagicMock()
        await r.update()
        assert r.online is True

    async def test_update_service_exception(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.aqualink.send_home_screen_request = async_raises(
            AqualinkServiceException
        )
        with pytest.raises(AqualinkServiceException):
            await r.update()
        assert r.online is None

    async def test_update_offline(self):
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.aqualink.send_home_screen_request = async_noop
        r.aqualink.send_devices_screen_request = async_noop
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
            await system._parse_devices_response(response)
        assert system.devices == {}

    async def test_parse_devices_good(self):
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        aqualink = MagicMock()
        system = AqualinkSystem.from_data(aqualink, data)

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
            "aux_B1": AqualinkAuxToggle(
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
