from __future__ import annotations
from collections import namedtuple

import asynctest
import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkLoginException,
    AqualinkServiceException,
)

from .common import async_raises, async_returns

MockResponse = namedtuple("MockResponse", ["status", "reason"])


class TestAqualinkClient(asynctest.TestCase):
    def setUp(self) -> None:
        self.aqualink = AqualinkClient("foo", "bar")

    @asynctest.strict
    async def test_send_request_success(self):
        url = "http://foo"
        r = MockResponse(status=200, reason="Passing test")
        self.aqualink.session.request = async_returns(r)
        await self.aqualink._send_request(url)

    @asynctest.strict
    async def test_send_request_failure(self):
        url = "http://foo"
        r = MockResponse(status=500, reason="Failing test")
        self.aqualink.session.request = async_returns(r)

        with pytest.raises(AqualinkServiceException):
            await self.aqualink._send_request(url)

    @asynctest.strict
    async def test_session_closed_on_failed_login(self):
        self.aqualink.login = async_raises(AqualinkLoginException)

        with pytest.raises(AqualinkLoginException):
            async with self.aqualink:
                pass
        assert self.aqualink.session.closed is True
