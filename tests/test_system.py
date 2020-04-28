from __future__ import annotations

import asynctest
import pytest

from iaqualink.exception import AqualinkSystemOfflineException
from iaqualink.system import AqualinkSystem, AqualinkPoolSystem

from .common import async_noop, async_raises


pytestmark = pytest.mark.asyncio


class TestAqualinkSystem(asynctest.TestCase):
    def setUp(self) -> None:
        pass

    @asynctest.fail_on(unused_loop=False)
    def test_from_data_iaqua(self):
        aqualink = asynctest.MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is not None
        assert isinstance(r, AqualinkPoolSystem)

    @asynctest.fail_on(unused_loop=False)
    def test_from_data_unsupported(self):
        aqualink = asynctest.MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "foo"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is None

    @asynctest.strict
    async def test_update_success(self):
        aqualink = asynctest.MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.aqualink.send_home_screen_request = async_noop
        r.aqualink.send_devices_screen_request = async_noop
        r._parse_home_response = async_noop
        r._parse_devices_response = async_noop
        await r.update()
        assert r.last_run_success is True
        assert r.online is True

    @asynctest.strict
    async def test_update_failure(self):
        aqualink = asynctest.MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.aqualink.send_home_screen_request = async_raises
        await r.update()
        assert r.last_run_success is False
        assert r.online is None

    @asynctest.strict
    async def test_update_offline(self):
        aqualink = asynctest.MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        r.aqualink.send_home_screen_request = async_noop
        r.aqualink.send_devices_screen_request = async_noop
        r._parse_home_response = async_raises(AqualinkSystemOfflineException)
        await r.update()
        assert r.last_run_success is True
        assert r.online is False
