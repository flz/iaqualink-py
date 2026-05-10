from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

import pytest

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.i2d_robot.const import (
    I2D_REQUEST_RETURN_TO_BASE,
    I2D_REQUEST_START,
    I2D_REQUEST_STATUS,
    I2D_REQUEST_STOP,
)
from iaqualink.systems.i2d_robot.system import I2dRobotSystem


def _make_status_hex() -> str:
    body = (
        b"\xff\xff"
        + bytes(
            [
                0x04,  # state: actively_cleaning
                0x00,  # error: none
                0x03,  # mode: deep clean (no canister)
                30,  # time remaining
            ]
        )
        + (60).to_bytes(3, "little")  # uptime
        + (5).to_bytes(3, "little")  # total hours
        + b"\xaa\xbb\xcc"  # hardware id
        + b"\xdd\xee\xff"  # firmware id
    )
    return body.hex()


def _system() -> I2dRobotSystem:
    aqualink = MagicMock()
    aqualink.user_id = "u-1"
    aqualink.id_token = "tok"
    sys = AqualinkSystem.from_data(
        aqualink,
        {
            "id": 444,
            "serial_number": "I2D-1",
            "device_type": "i2d_robot",
            "name": "polaris",
        },
    )
    assert isinstance(sys, I2dRobotSystem)
    return sys


class TestI2dRegistration(unittest.TestCase):
    def test_from_data_dispatches(self) -> None:
        _ = _system()


class TestI2dParse(unittest.TestCase):
    def test_parse_status_response_populates_devices(self) -> None:
        sys = _system()
        sys._parse_status_response(
            {
                "command": {
                    "request": I2D_REQUEST_STATUS,
                    "response": _make_status_hex(),
                }
            }
        )
        assert sys.devices["state"].state == "actively_cleaning"
        assert sys.devices["mode_code"].state == "3"
        assert sys.devices["error"].state == "no_error"
        assert sys.devices["time_remaining_min"].state == "30"
        assert sys.devices["uptime_minutes"].state == "60"
        assert sys.devices["total_hours"].state == "5"
        assert sys.devices["model_number"].state == "444"
        assert sys.devices["running"].state == "1"
        assert sys.devices["canister_full"].state == "0"

    def test_parse_invalid_request_raises_offline(self) -> None:
        sys = _system()
        with pytest.raises(AqualinkSystemOfflineException):
            sys._parse_status_response(
                {"command": {"request": "WRONG", "response": ""}}
            )

    def test_parse_bad_hex_raises_offline(self) -> None:
        sys = _system()
        with pytest.raises(AqualinkSystemOfflineException):
            sys._parse_status_response(
                {"command": {"request": I2D_REQUEST_STATUS, "response": "AB"}}
            )


class TestI2dControl(unittest.IsolatedAsyncioTestCase):
    async def test_start_posts_start_request(self) -> None:
        sys = _system()
        sys._post_command = AsyncMock(return_value={})
        await sys.start_cleaning()
        sys._post_command.assert_awaited_once_with(I2D_REQUEST_START)

    async def test_stop_posts_stop_request(self) -> None:
        sys = _system()
        sys._post_command = AsyncMock(return_value={})
        await sys.stop_cleaning()
        sys._post_command.assert_awaited_once_with(I2D_REQUEST_STOP)

    async def test_return_posts_return_request(self) -> None:
        sys = _system()
        sys._post_command = AsyncMock(return_value={})
        await sys.return_to_base()
        sys._post_command.assert_awaited_once_with(I2D_REQUEST_RETURN_TO_BASE)

    async def test_update_throttled_re_raises_without_clearing_online(
        self,
    ) -> None:
        sys = _system()
        sys.online = True
        sys._post_command = AsyncMock(
            side_effect=AqualinkServiceThrottledException
        )
        with pytest.raises(AqualinkServiceThrottledException):
            await sys.update()
        assert sys.online is True

    async def test_update_service_error_clears_online(self) -> None:
        sys = _system()
        sys._post_command = AsyncMock(side_effect=AqualinkServiceException)
        with pytest.raises(AqualinkServiceException):
            await sys.update()
        assert sys.online is None

    async def test_update_offline_sets_offline(self) -> None:
        sys = _system()
        sys._post_command = AsyncMock(
            return_value={"command": {"request": "WRONG"}}
        )
        with pytest.raises(AqualinkSystemOfflineException):
            await sys.update()
        assert sys.online is False
