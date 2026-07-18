"""Tests for the generic WS subscription engine."""

from __future__ import annotations

import json
import time
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from iaqualink.utils.websockets import (
    ACTION_SUBSCRIBE,
    SERVICE_AUTHORIZATION,
    WsStateSubscription,
    build_subscribe_frame,
    client_token,
    deep_merge,
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


def test_build_subscribe_frame_shape() -> None:
    frame = build_subscribe_frame(user_id="42", target="SN123")
    assert frame == {
        "action": ACTION_SUBSCRIBE,
        "version": 1,
        "namespace": "authorization",
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


class _StopLoop(Exception):
    """Sentinel to break the receive loop in tests."""


class _FakeWsSub(WsStateSubscription):
    """Minimal concrete subscription host for testing the shared engine."""

    def __init__(self, aqualink: Any) -> None:
        self.aqualink = aqualink
        self.serial = "SN1"
        self.status: Any = None
        self.devices: dict[str, Any] = {}
        self.full_state_calls: list[dict[str, Any]] = []
        self.delta_calls: list[dict[str, Any]] = []
        super().__init__()

    def _ws_full_state_from_frame(
        self, frame: dict[str, Any]
    ) -> dict[str, Any] | None:
        payload = frame.get("payload") or {}
        reported = ((payload.get("robot") or {}).get("state") or {}).get(
            "reported"
        )
        return reported if isinstance(reported, dict) else None

    def _ws_delta_from_frame(
        self, frame: dict[str, Any]
    ) -> dict[str, Any] | None:
        if frame.get("event") != "StateReported":
            return None
        payload = frame.get("payload") or {}
        reported = (payload.get("state") or {}).get("reported")
        return reported if isinstance(reported, dict) else None

    def _apply_full_state(self, reported: dict[str, Any]) -> None:
        self.full_state_calls.append(reported)

    def _apply_state_delta(self, delta: dict[str, Any]) -> None:
        self.delta_calls.append(delta)


def _make_sub() -> _FakeWsSub:
    aqualink = MagicMock()
    aqualink.user_id = "42"
    return _FakeWsSub(aqualink)


def test_subscription_subscribe_frame_uses_user_id_and_serial() -> None:
    sub = _make_sub()
    frame = sub._ws_subscribe_frame()
    assert frame["payload"]["userId"] == 42
    assert frame["target"] == "SN1"
    assert frame["action"] == ACTION_SUBSCRIBE


def test_apply_ws_frame_authorization_full_state() -> None:
    sub = _make_sub()
    reported = {"main": {"state": 1}}
    frame = {
        "service": SERVICE_AUTHORIZATION,
        "payload": {"robot": {"state": {"reported": reported}}},
    }
    assert sub._apply_ws_frame(frame) is True
    assert sub.full_state_calls == [reported]
    assert sub.delta_calls == []


def test_apply_ws_frame_authorization_missing_returns_false() -> None:
    sub = _make_sub()
    frame = {"service": SERVICE_AUTHORIZATION, "payload": {}}
    assert sub._apply_ws_frame(frame) is False
    assert sub.full_state_calls == []


def test_apply_ws_frame_delta() -> None:
    sub = _make_sub()
    delta = {"main": {"state": 2}}
    frame = {
        "service": "StateStreamer",
        "event": "StateReported",
        "payload": {"state": {"reported": delta}},
    }
    assert sub._apply_ws_frame(frame) is True
    assert sub.delta_calls == [delta]
    assert sub.full_state_calls == []


def test_apply_ws_frame_desired_echo_ignored() -> None:
    sub = _make_sub()
    frame = {
        "service": "StateStreamer",
        "payload": {"state": {"desired": {"x": 1}}},
    }
    assert sub._apply_ws_frame(frame) is False
    assert sub.delta_calls == []
    assert sub.full_state_calls == []


def test_ws_state_fresh_false_when_not_connected() -> None:
    sub = _make_sub()
    sub._ws_connected = False
    sub._ws_last_update = time.time()
    assert sub._ws_state_fresh() is False


def test_ws_state_fresh_true_when_connected_and_recent() -> None:
    sub = _make_sub()
    sub._ws_connected = True
    sub._ws_last_update = time.time()
    assert sub._ws_state_fresh() is True


def test_ws_state_fresh_false_when_stale() -> None:
    sub = _make_sub()
    sub._ws_connected = True
    sub._ws_last_update = time.time() - 10_000
    assert sub._ws_state_fresh() is False


def test_on_ws_task_done_cancelled_is_noop() -> None:
    task = MagicMock()
    task.cancelled.return_value = True
    WsStateSubscription._on_ws_task_done(task)
    task.exception.assert_not_called()


def test_on_ws_task_done_logs_exception() -> None:
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = RuntimeError("boom")
    # Must swallow the exception (loop drop is non-fatal).
    WsStateSubscription._on_ws_task_done(task)


def test_on_ws_task_done_no_exception() -> None:
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = None
    WsStateSubscription._on_ws_task_done(task)


def _ws_cm(ws: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=ws)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestSubscriptionReceiveLoop(unittest.IsolatedAsyncioTestCase):
    async def test_subscribes_then_applies_pushed_state(self) -> None:
        sub = _make_sub()
        reported = {"main": {"state": 1}}
        ack = json.dumps(
            {
                "service": SERVICE_AUTHORIZATION,
                "payload": {"robot": {"state": {"reported": reported}}},
            }
        )
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=[ack, _StopLoop()])
        sub.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await sub._ws_receive_loop()

        # Subscribe sent on connect.
        ws.send_text.assert_awaited_once_with(
            json.dumps(sub._ws_subscribe_frame())
        )
        # Pushed full state applied; freshness updated. Status derivation is
        # owned by the subclass (e.g. RobotStateSubscription sets ONLINE;
        # tcx derives a richer status) — not asserted at the generic-engine
        # level.
        assert sub.full_state_calls == [reported]
        assert sub._ws_last_update is not None
        # Connection marked down on exit.
        assert sub._ws_connected is False

    async def test_keepalive_passed_to_ws_connect(self) -> None:
        sub = _make_sub()
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=[_StopLoop()])
        sub.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await sub._ws_receive_loop()

        sub.aqualink.ws_connect.assert_called_once()
        kwargs = sub.aqualink.ws_connect.call_args.kwargs
        assert kwargs["keepalive_ping_interval_seconds"] == (
            sub.WS_KEEPALIVE_SECS
        )

    async def test_non_json_frame_skipped(self) -> None:
        sub = _make_sub()
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=["not json", _StopLoop()])
        sub.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await sub._ws_receive_loop()

        assert sub.full_state_calls == []
        assert sub._ws_last_update is None

    async def test_non_dict_json_frame_skipped(self) -> None:
        sub = _make_sub()
        ws = AsyncMock()
        # Valid JSON but not an object (e.g. a list) → skipped.
        ws.receive_text = AsyncMock(side_effect=["[]", _StopLoop()])
        sub.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await sub._ws_receive_loop()

        assert sub.full_state_calls == []
        assert sub._ws_last_update is None

    async def test_received_frame_is_logged_redacted(self) -> None:
        sub = _make_sub()
        reported = {"main": {"state": 1}}
        frame = {
            "service": SERVICE_AUTHORIZATION,
            "payload": {
                "robot": {"state": {"reported": reported}},
                "userId": 999,
            },
        }
        ws = AsyncMock()
        ws.receive_text = AsyncMock(
            side_effect=[json.dumps(frame), _StopLoop()]
        )
        sub.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with (
            self.assertLogs("iaqualink.utils.websockets", level="DEBUG") as cm,
            self.assertRaises(_StopLoop),
        ):
            await sub._ws_receive_loop()

        logged = "\n".join(cm.output)
        assert "<- WS frame" in logged
        assert "999" not in logged  # userId redacted


async def _never() -> str:
    import asyncio

    await asyncio.Event().wait()
    return ""


class TestSubscriptionLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_start_is_noop_when_disabled(self) -> None:
        sub = _make_sub()
        sub._ws_enabled = False
        await sub.start_ws_subscription()
        assert sub._ws_task is None

    async def test_stop_cancels_running_task(self) -> None:
        sub = _make_sub()
        ws = AsyncMock()
        # Block forever until cancelled.
        ws.receive_text = AsyncMock(side_effect=_never)
        sub.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        await sub.start_ws_subscription()
        assert sub._ws_task is not None
        await sub.stop_ws_subscription()
        assert sub._ws_task is None

    async def test_start_twice_is_noop(self) -> None:
        sub = _make_sub()
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=_never)
        sub.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        await sub.start_ws_subscription()
        first = sub._ws_task
        await sub.start_ws_subscription()
        assert sub._ws_task is first
        await sub.stop_ws_subscription()

    async def test_stop_is_noop_when_not_running(self) -> None:
        sub = _make_sub()
        await sub.stop_ws_subscription()
        assert sub._ws_task is None
