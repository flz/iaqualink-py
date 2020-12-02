import asynctest
import pytest
from asynctest.mock import patch

from iaqualink.client import AqualinkClient
from iaqualink import AqualinkLoginException


class TestAqualinkClient(asynctest.TestCase):
    def setUp(self) -> None:
        pass

    async def test_session_closed_on_failed_login(self):
        aqualink = AqualinkClient("foo", "bar")
        with patch(
            "iaqualink.AqualinkClient.login", side_effect=AqualinkLoginException
        ):
            with pytest.raises(AqualinkLoginException):
                async with aqualink:
                    pass
            assert aqualink.session.closed
