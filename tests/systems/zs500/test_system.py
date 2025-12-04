from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch
from asyncio import Future

import pytest

from iaqualink.exception import (
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.zs500.system import Zs500System

from ...base_test_system import TestBaseSystem

class UpdatesDict(dict):

    def __init__(self, result=True):
        self.__result = result

    def __setitem__(self, name, value):
        value.set_result(self.__result)
        return super().__setitem__(name, value)

class TestZs500System(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "id": 123456,
            "serial_number": "SN123456",
            "created_at": "2017-09-23T01:00:08.000Z",
            "updated_at": "2017-09-23T01:00:08.000Z",
            "name": "Pool",
            "device_type": "zs500",
            "owner_id": None,
            "updating": False,
            "firmware_version": None,
            "target_firmware_version": None,
            "update_firmware_start_at": None,
            "last_activity_at": None,
        }
        self.sut = AqualinkSystem.from_data(self.client, data=data)
        self.sut_class = Zs500System

        self.sut._started = True
        self.sut._shadow = MagicMock()

    async def test_update_success(self) -> None:
        with patch.object(self.sut._shadow, "publish_get_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut._updates = UpdatesDict(
                result=Mock(state=Mock(reported={
                    "aws": { "status": "connected" },
                    "equipment": {},
                })),
            )
            await self.sut.update()
            mock.assert_called_once()

    async def test_update_offline(self) -> None:
        with patch.object(self.sut._shadow, "publish_get_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut._updates = UpdatesDict(
                result=Mock(state=Mock(reported={
                    "aws": { "status": "offline" },
                    "equipment": {},
                })),
            )

            with pytest.raises(AqualinkSystemOfflineException):
                await self.sut.update()

            assert self.sut.online is False

    async def test_update_consecutive(self) -> None:
        with patch.object(self.sut._shadow, "publish_get_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut._updates = UpdatesDict(
                result=Mock(state=Mock(reported={
                    "aws": { "status": "connected" },
                    "equipment": {},
                })),
            )

            await self.sut.update()
            await self.sut.update()

            assert mock.call_count == 1

    async def test_get_devices_needs_update(self) -> None:
        with patch.object(self.sut._shadow, "publish_get_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut._updates = UpdatesDict(
                result=Mock(state=Mock(reported={
                    "aws": { "status": "connected" },
                    "equipment": {},
                })),
            )

            await self.sut.get_devices()

            mock.assert_called_once()

    async def test_parse_devices_offline(self) -> None:
        message = {
            "aws": { "status": "connected" },
            "equipment": {}
        }
        await self.sut._parse_device_info(message)
        assert self.sut.devices == {}

    async def test_parse_devices_good(self) -> None:
        message = {
            "aws": { "status": "connected" },
            "equipment": {
                "123456": {
                    "et": "HEAT_PUMP",
                    "tsp": 250,
                    "sns_0": {
                        "type": "water",
                        "value": 230
                    }
                }
            }
        }
        await self.sut._parse_device_info(message)
        assert self.sut.devices["123456"].data == message["equipment"]["123456"]

    async def test_update_request_unauthorized(self) -> None:
        # Does not apply to AWS IOT SDK
        # Once connected all updates happen over the persistent MQTT connection
        pass

    async def test_update_service_exception(self) -> None:
        # Does not apply to AWS IOT SDK
        # Once connected all updates happen over the persistent MQTT connection
        pass
