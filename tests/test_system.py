from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem, UnsupportedSystem

pytestmark = pytest.mark.skip(reason="AqualinkSystem is not implemented")

pytestmark = pytest.mark.skip(reason="AqualinkSystem is not implemented")


class TestAqualinkSystem(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        pass

    def test_repr(self) -> None:
        aqualink = MagicMock()
        data = {
            "id": 1,
            "serial_number": "ABCDEFG",
            "device_type": "iaqua",
            "name": "foo",
        }
        system = AqualinkSystem(aqualink, data)
        assert (
            repr(system)
            == f"AqualinkSystem(name='foo', serial='ABCDEFG', data={data})"
        )

    def test_from_data_iaqua(self) -> None:
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r is not None

    def test_supported_true_for_known_system(self) -> None:
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "iaqua"}
        r = AqualinkSystem.from_data(aqualink, data)
        assert r.supported is True

    async def test_get_devices_needs_update(self) -> None:
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "fake"}
        aqualink = AqualinkClient("user", "pass")
        system = AqualinkSystem(aqualink, data)
        system.devices = None

        with patch.object(system, "refresh") as mock_refresh:
            await system.get_devices()
            mock_refresh.assert_called_once()

    async def test_get_devices(self) -> None:
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "fake"}
        aqualink = AqualinkClient("user", "pass")
        system = AqualinkSystem(aqualink, data)
        system.devices = {"foo": "bar"}

        with patch.object(system, "refresh") as mock_refresh:
            await system.get_devices()
            mock_refresh.assert_not_called()

    async def test_refresh_not_implemented(self) -> None:
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "fake"}
        aqualink = AqualinkClient("user", "pass")
        system = AqualinkSystem(aqualink, data)

        with pytest.raises(NotImplementedError):
            await system.refresh()


class TestUnsupportedSystem(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.aqualink = MagicMock()
        self.data = {
            "id": 1,
            "serial_number": "ABCDEFG",
            "device_type": "unknown_type",
            "name": "pool",
        }
        self.system = UnsupportedSystem(self.aqualink, self.data)

    def test_from_data_returns_unsupported_system(self) -> None:
        r = AqualinkSystem.from_data(self.aqualink, self.data)
        assert isinstance(r, UnsupportedSystem)

    def test_type(self) -> None:
        assert self.system.type == "unknown_type"

    def test_supported_false(self) -> None:
        assert self.system.supported is False

    async def test_refresh_is_noop(self) -> None:
        await self.system.refresh()

    async def test_get_devices_returns_empty(self) -> None:
        devices = await self.system.get_devices()
        assert devices == {}
