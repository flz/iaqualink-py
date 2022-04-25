from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkSystemUnsupportedException
from iaqualink.system import AqualinkSystem


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

    def test_from_data_unsupported(self) -> None:
        aqualink = MagicMock()
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "foo"}
        with pytest.raises(AqualinkSystemUnsupportedException):
            AqualinkSystem.from_data(aqualink, data)

    async def test_get_devices_needs_update(self) -> None:
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "fake"}
        aqualink = AqualinkClient("user", "pass")
        system = AqualinkSystem(aqualink, data)
        system.devices = None

        with patch.object(system, "update") as mock_update:
            await system.get_devices()
            mock_update.assert_called_once()

    async def test_get_devices(self) -> None:
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "fake"}
        aqualink = AqualinkClient("user", "pass")
        system = AqualinkSystem(aqualink, data)
        system.devices = {"foo": "bar"}

        with patch.object(system, "update") as mock_update:
            await system.get_devices()
            mock_update.assert_not_called()

    async def test_update_not_implemented(self) -> None:
        data = {"id": 1, "serial_number": "ABCDEFG", "device_type": "fake"}
        aqualink = AqualinkClient("user", "pass")
        system = AqualinkSystem(aqualink, data)

        with pytest.raises(NotImplementedError):
            await system.update()
