"""Tests for shared robot WebSocket framing."""

from __future__ import annotations

import json
import time
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from iaqualink.const import AQUALINK_WS_URL
from iaqualink.system import SystemStatus
from iaqualink.utils.robots import (
    ACTION_SET_CLEANER_STATE,
    ACTION_SUBSCRIBE,
    EVENT_STATE_REPORTED,
    NAMESPACE_AUTHORIZATION,
    SERVICE_AUTHORIZATION,
    SERVICE_STATE_STREAMER,
    RobotStateSubscription,
    build_set_state_frame,
    build_subscribe_frame,
    client_token,
    deep_merge,
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


def test_build_subscribe_frame_shape() -> None:
    frame = build_subscribe_frame(user_id="42", target="SN123")
    assert frame == {
        "action": ACTION_SUBSCRIBE,
        "version": 1,
        "namespace": NAMESPACE_AUTHORIZATION,
        "service": SERVICE_AUTHORIZATION,
        "payload": {"userId": 42},
        "target": "SN123",
    }


def test_build_subscribe_frame_coerces_numeric_user_id() -> None:
    frame = build_subscribe_frame(user_id="42", target="SN123")
    assert frame["payload"]["userId"] == 42


def test_build_subscribe_frame_keeps_non_numeric_user_id() -> None:
    frame = build_subscribe_frame(user_id="abc", target="SN123")
    assert frame["payload"]["userId"] == "abc"


def test_deep_merge_merges_nested_delta_wins() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    delta = {"a": {"y": 20, "z": 30}}
    assert deep_merge(base, delta) == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}


def test_deep_merge_non_dict_value_replaces() -> None:
    base = {"a": {"x": 1}}
    delta = {"a": 9}
    assert deep_merge(base, delta) == {"a": 9}


def test_deep_merge_does_not_mutate_base() -> None:
    base = {"a": {"x": 1}}
    deep_merge(base, {"a": {"y": 2}})
    assert base == {"a": {"x": 1}}


class TestSendRobotFrame(unittest.IsolatedAsyncioTestCase):
    async def test_delegates_to_client_send_ws_frame(self) -> None:
        client = MagicMock()
        client.send_ws_frame = AsyncMock()
        frame = {"version": 1, "action": "setCleanerState"}
        await send_robot_frame(client, frame)
        client.send_ws_frame.assert_awaited_once_with(AQUALINK_WS_URL, frame)


class _StopLoop(Exception):
    """Sentinel to break the receive loop in tests."""


class _FakeRobot(RobotStateSubscription):
    """Minimal concrete subscription host for testing the shared engine."""

    def __init__(self, aqualink: Any) -> None:
        self.aqualink = aqualink
        self.serial = "SN1"
        self.status: Any = None
        self.devices: dict[str, Any] = {}
        self.reported_calls: list[dict[str, Any]] = []
        self.delta_calls: list[dict[str, Any]] = []
        super().__init__()

    def _extract_robot(self, reported: dict[str, Any]) -> dict[str, Any] | None:
        robot = (reported.get("equipment") or {}).get("robot")
        return robot if isinstance(robot, dict) else None

    def _apply_reported_state(self, reported: dict[str, Any]) -> None:
        self.reported_calls.append(reported)

    def _apply_robot_delta(self, delta: dict[str, Any]) -> None:
        self.delta_calls.append(delta)


def _make_robot() -> _FakeRobot:
    aqualink = MagicMock()
    aqualink.user_id = "42"
    return _FakeRobot(aqualink)


def test_subscription_subscribe_frame_uses_user_id_and_serial() -> None:
    robot = _make_robot()
    frame = robot._ws_subscribe_frame()
    assert frame["payload"]["userId"] == 42
    assert frame["target"] == "SN1"
    assert frame["action"] == ACTION_SUBSCRIBE


def test_apply_ws_frame_authorization_full_state() -> None:
    robot = _make_robot()
    reported = {"equipment": {"robot": {"main": {"state": 1}}}}
    frame = {
        "service": SERVICE_AUTHORIZATION,
        "payload": {"robot": {"state": {"reported": reported}}},
    }
    assert robot._apply_ws_frame(frame) is True
    assert robot.reported_calls == [reported]
    assert robot.delta_calls == []


def test_apply_ws_frame_authorization_without_robot_returns_false() -> None:
    robot = _make_robot()
    frame = {
        "service": SERVICE_AUTHORIZATION,
        "payload": {"robot": {"state": {"reported": {"equipment": {}}}}},
    }
    assert robot._apply_ws_frame(frame) is False
    assert robot.reported_calls == []


def test_apply_ws_frame_state_reported_delta() -> None:
    robot = _make_robot()
    delta = {"main": {"state": 2}}
    frame = {
        "service": SERVICE_STATE_STREAMER,
        "event": EVENT_STATE_REPORTED,
        "payload": {"state": {"reported": {"equipment": {"robot": delta}}}},
    }
    assert robot._apply_ws_frame(frame) is True
    assert robot.delta_calls == [delta]
    assert robot.reported_calls == []


def test_apply_ws_frame_desired_echo_ignored() -> None:
    robot = _make_robot()
    frame = {
        "service": SERVICE_STATE_STREAMER,
        "payload": {"state": {"desired": {"equipment": {"robot": {"x": 1}}}}},
    }
    assert robot._apply_ws_frame(frame) is False
    assert robot.delta_calls == []
    assert robot.reported_calls == []


def test_ws_state_fresh_false_when_not_connected() -> None:
    robot = _make_robot()
    robot._ws_connected = False
    robot._ws_last_update = time.time()
    assert robot._ws_state_fresh() is False


def test_ws_state_fresh_true_when_connected_and_recent() -> None:
    robot = _make_robot()
    robot._ws_connected = True
    robot._ws_last_update = time.time()
    assert robot._ws_state_fresh() is True


def test_ws_state_fresh_false_when_stale() -> None:
    robot = _make_robot()
    robot._ws_connected = True
    robot._ws_last_update = time.time() - 10_000
    assert robot._ws_state_fresh() is False


def test_apply_ws_frame_state_reported_non_dict_returns_false() -> None:
    robot = _make_robot()
    frame = {
        "service": SERVICE_STATE_STREAMER,
        "event": EVENT_STATE_REPORTED,
        "payload": {"state": {"reported": "nope"}},
    }
    assert robot._apply_ws_frame(frame) is False
    assert robot.delta_calls == []


def test_apply_ws_frame_state_reported_without_robot_returns_false() -> None:
    robot = _make_robot()
    frame = {
        "service": SERVICE_STATE_STREAMER,
        "event": EVENT_STATE_REPORTED,
        "payload": {"state": {"reported": {"equipment": {}}}},
    }
    assert robot._apply_ws_frame(frame) is False
    assert robot.delta_calls == []


def test_on_ws_task_done_cancelled_is_noop() -> None:
    task = MagicMock()
    task.cancelled.return_value = True
    RobotStateSubscription._on_ws_task_done(task)
    task.exception.assert_not_called()


def test_on_ws_task_done_logs_exception() -> None:
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = RuntimeError("boom")
    # Must swallow the exception (loop drop is non-fatal).
    RobotStateSubscription._on_ws_task_done(task)


def test_on_ws_task_done_no_exception() -> None:
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = None
    RobotStateSubscription._on_ws_task_done(task)


def _ws_cm(ws: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=ws)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestSubscriptionReceiveLoop(unittest.IsolatedAsyncioTestCase):
    async def test_subscribes_then_applies_pushed_state(self) -> None:
        robot = _make_robot()
        reported = {"equipment": {"robot": {"main": {"state": 1}}}}
        ack = json.dumps(
            {
                "service": SERVICE_AUTHORIZATION,
                "payload": {"robot": {"state": {"reported": reported}}},
            }
        )
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=[ack, _StopLoop()])
        robot.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await robot._ws_receive_loop()

        # Subscribe sent on connect.
        ws.send_text.assert_awaited_once_with(
            json.dumps(robot._ws_subscribe_frame())
        )
        # Pushed full state applied; freshness + status updated.
        assert robot.reported_calls == [reported]
        assert robot._ws_last_update is not None
        assert robot.status is SystemStatus.ONLINE
        # Connection marked down on exit.
        assert robot._ws_connected is False

    async def test_keepalive_passed_to_ws_connect(self) -> None:
        robot = _make_robot()
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=[_StopLoop()])
        robot.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await robot._ws_receive_loop()

        robot.aqualink.ws_connect.assert_called_once()
        kwargs = robot.aqualink.ws_connect.call_args.kwargs
        assert kwargs["keepalive_ping_interval_seconds"] == (
            robot.WS_KEEPALIVE_SECS
        )

    async def test_non_json_frame_skipped(self) -> None:
        robot = _make_robot()
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=["not json", _StopLoop()])
        robot.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await robot._ws_receive_loop()

        assert robot.reported_calls == []
        assert robot._ws_last_update is None

    async def test_non_dict_json_frame_skipped(self) -> None:
        robot = _make_robot()
        ws = AsyncMock()
        # Valid JSON but not an object (e.g. a list) → skipped.
        ws.receive_text = AsyncMock(side_effect=["[]", _StopLoop()])
        robot.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await robot._ws_receive_loop()

        assert robot.reported_calls == []
        assert robot._ws_last_update is None


async def _never() -> str:
    import asyncio

    await asyncio.Event().wait()
    return ""


class TestSubscriptionLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_start_is_noop_when_disabled(self) -> None:
        robot = _make_robot()
        robot._ws_enabled = False
        await robot.start_ws_subscription()
        assert robot._ws_task is None

    async def test_stop_cancels_running_task(self) -> None:
        robot = _make_robot()
        ws = AsyncMock()
        # Block forever until cancelled.
        ws.receive_text = AsyncMock(side_effect=_never)
        robot.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        await robot.start_ws_subscription()
        assert robot._ws_task is not None
        await robot.stop_ws_subscription()
        assert robot._ws_task is None

    async def test_start_twice_is_noop(self) -> None:
        robot = _make_robot()
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=_never)
        robot.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        await robot.start_ws_subscription()
        first = robot._ws_task
        await robot.start_ws_subscription()
        assert robot._ws_task is first
        await robot.stop_ws_subscription()

    async def test_stop_is_noop_when_not_running(self) -> None:
        robot = _make_robot()
        await robot.stop_ws_subscription()
        assert robot._ws_task is None
