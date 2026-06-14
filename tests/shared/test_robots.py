"""Tests for shared robot WebSocket framing."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from iaqualink.const import AQUALINK_WS_URL
from iaqualink.shared.robots import (
    ACTION_SET_CLEANER_STATE,
    build_set_state_frame,
    client_token,
    send_robot_frame,
)


def test_client_token_3_part_when_app_client_id_set() -> None:
    client = MagicMock()
    client.user_id = "42"
    client.authentication_token = "tok"
    client.app_client_id = "abc"
    assert client_token(client) == "42|tok|abc"


def test_client_token_2_part_when_app_client_id_blank() -> None:
    client = MagicMock()
    client.user_id = "42"
    client.authentication_token = "tok"
    client.app_client_id = ""
    token = client_token(client)
    assert token.startswith("42|")
    assert token.count("|") == 1


def test_build_set_state_frame_shape() -> None:
    frame = build_set_state_frame(
        namespace="cyclobat",
        target="SN123",
        equipment_state={"robot": {"main": {"ctrl": 1}}},
        token="42|tok|abc",
    )
    assert frame == {
        "version": 1,
        "action": ACTION_SET_CLEANER_STATE,
        "namespace": "cyclobat",
        "service": "StateController",
        "target": "SN123",
        "payload": {
            "clientToken": "42|tok|abc",
            "state": {
                "desired": {"equipment": {"robot": {"main": {"ctrl": 1}}}}
            },
        },
    }


class TestSendRobotFrame(unittest.IsolatedAsyncioTestCase):
    async def test_delegates_to_client_send_ws_frame(self) -> None:
        client = MagicMock()
        client.send_ws_frame = AsyncMock()
        frame = {"version": 1, "action": "setCleanerState"}
        await send_robot_frame(client, frame)
        client.send_ws_frame.assert_awaited_once_with(AQUALINK_WS_URL, frame)
