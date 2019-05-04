import asynctest
import pytest

from iaqualink.system import AqualinkSystem, AqualinkPoolSystem


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
