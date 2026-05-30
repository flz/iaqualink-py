"""Tests for shared robot WebSocket helper."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from iaqualink.systems import _robot_ws
from iaqualink.systems._robot_ws import (
    ACTION_SET_CLEANER_STATE,
    ROBOT_WS_URL,
    RobotWebsocketDependencyError,
    build_set_state_frame,
    client_token,
    send_frame,
)


def test_client_token_3_part_when_app_client_id_set():
    client = MagicMock()
    client.user_id = "42"
    client.authentication_token = "tok"
    client.app_client_id = "abc"
    assert client_token(client) == "42|tok|abc"


def test_client_token_2_part_when_app_client_id_blank():
    client = MagicMock()
    client.user_id = "42"
    client.authentication_token = "tok"
    client.app_client_id = ""
    token = client_token(client)
    assert token.startswith("42|")
    assert token.count("|") == 1


def test_build_set_state_frame_shape():
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


class TestSendFrameRaisesWhenWebsocketsMissing(
    unittest.IsolatedAsyncioTestCase
):
    async def test_raises_when_websockets_missing(self):
        original = _robot_ws.ws_connect
        try:
            _robot_ws.ws_connect = None
            client = MagicMock()
            with self.assertRaises(RobotWebsocketDependencyError):
                await send_frame(client, {"any": "frame"})
        finally:
            _robot_ws.ws_connect = original


class TestSendFrameAckTimeout(unittest.IsolatedAsyncioTestCase):
    async def test_send_frame_sends_and_swallows_ack_timeout(self):
        conn = AsyncMock()
        conn.send = AsyncMock()
        conn.recv = AsyncMock(side_effect=TimeoutError())

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)

        fake_connect = MagicMock(return_value=cm)

        original = _robot_ws.ws_connect
        try:
            _robot_ws.ws_connect = fake_connect

            client = MagicMock()
            client.id_token = "tok"

            frame = {"version": 1, "action": "setCleanerState"}
            await send_frame(client, frame)

            fake_connect.assert_called_once()
            args, kwargs = fake_connect.call_args
            assert args[0] == ROBOT_WS_URL
            assert kwargs["additional_headers"] == {"Authorization": "tok"}
            conn.send.assert_awaited_once_with(json.dumps(frame))
        finally:
            _robot_ws.ws_connect = original
