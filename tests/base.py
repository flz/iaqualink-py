import unittest

import httpx
from respx.patterns import M

from iaqualink.client import AqualinkClient

dotstar = M(host__regex=".*")
resp_200 = httpx.Response(status_code=200, json={})


class TestBase(unittest.IsolatedAsyncioTestCase):
    __test__ = False

    def __init_subclass__(cls) -> None:
        if cls.__name__.startswith("TestBase"):
            cls.__test__ = False
        else:
            cls.__test__ = True
        return super().__init_subclass__()

    def setUp(self) -> None:
        super().setUp()

        self.client = AqualinkClient("foo", "bar")
        self.addAsyncCleanup(self.client.close)
