"""Tests for VR WS write commands."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import MagicMock

from iaqualink.shared.robots import (
    ACTION_SET_CLEANER_STATE,
    ACTION_SET_REMOTE_STEERING,
)
from iaqualink.systems.vr.ws import (
    VR_NAMESPACE,
    build_robot_state_frame,
    send_remote_steering,
    send_set_cycle,
    send_set_state,
    send_set_stepper,
)


class TestBuildRobotStateFrameDefaults(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = build_robot_state_frame("SN42", {"state": 1}, "tok")

    def test_namespace_default(self) -> None:
        self.assertEqual(self.frame["namespace"], VR_NAMESPACE)
        self.assertEqual(self.frame["namespace"], "vr")

    def test_action_default(self) -> None:
        self.assertEqual(self.frame["action"], ACTION_SET_CLEANER_STATE)
        self.assertEqual(self.frame["action"], "setCleanerState")

    def test_target(self) -> None:
        self.assertEqual(self.frame["target"], "SN42")

    def test_client_token(self) -> None:
        self.assertEqual(self.frame["payload"]["clientToken"], "tok")

    def test_equipment_state(self) -> None:
        self.assertEqual(
            self.frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"state": 1}},
        )


class TestBuildRobotStateFrameNamespaceOverride(unittest.TestCase):
    def test_namespace_vortrax(self) -> None:
        frame = build_robot_state_frame(
            "SN42", {"state": 1}, "tok", namespace="vortrax"
        )
        self.assertEqual(frame["namespace"], "vortrax")

    def test_action_and_equipment_unchanged(self) -> None:
        frame = build_robot_state_frame(
            "SN42", {"state": 1}, "tok", namespace="vortrax"
        )
        self.assertEqual(frame["action"], "setCleanerState")
        self.assertEqual(
            frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"state": 1}},
        )


class TestBuildRobotStateFrameActionOverride(unittest.TestCase):
    def test_action_set_remote_steering(self) -> None:
        frame = build_robot_state_frame(
            "SN42", {"rmt_ctrl": 1}, "tok", action="setRemoteSteeringControl"
        )
        self.assertEqual(frame["action"], ACTION_SET_REMOTE_STEERING)
        self.assertEqual(frame["action"], "setRemoteSteeringControl")

    def test_equipment_preserved(self) -> None:
        frame = build_robot_state_frame(
            "SN42", {"rmt_ctrl": 1}, "tok", action="setRemoteSteeringControl"
        )
        self.assertEqual(
            frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"rmt_ctrl": 1}},
        )


def _make_client() -> MagicMock:
    client = MagicMock()
    client.user_id = "42"
    client.authentication_token = "tok"
    client.app_client_id = "abc"
    # client_token uses id_token for WS auth header, but clientToken
    # is built from user_id|authentication_token|app_client_id.
    return client


class TestSendSetState(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_state_correct_args(self) -> None:
        import iaqualink.systems.vr.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_set_state(client, "SN42", 1)
        finally:
            ws_mod.send_robot_frame = original

        self.assertEqual(len(captured), 1)
        recorded_client, recorded_frame = captured[0]
        self.assertIs(recorded_client, client)
        self.assertEqual(
            recorded_frame["payload"]["clientToken"],
            "42|tok|abc",
        )
        self.assertEqual(
            recorded_frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"state": 1}},
        )
        self.assertEqual(recorded_frame["action"], "setCleanerState")
        self.assertEqual(recorded_frame["namespace"], "vr")

    async def test_send_set_state_namespace_vortrax(self) -> None:
        import iaqualink.systems.vr.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_set_state(client, "SN42", 1, namespace="vortrax")
        finally:
            ws_mod.send_robot_frame = original

        self.assertEqual(len(captured), 1)
        _, recorded_frame = captured[0]
        self.assertEqual(recorded_frame["namespace"], "vortrax")


class TestSendSetCycle(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_cycle_equipment(self) -> None:
        import iaqualink.systems.vr.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_set_cycle(client, "SN42", 2)
        finally:
            ws_mod.send_robot_frame = original

        self.assertEqual(len(captured), 1)
        _, recorded_frame = captured[0]
        self.assertEqual(
            recorded_frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"prCyc": 2}},
        )


class TestSendSetStepper(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_stepper_equipment(self) -> None:
        import iaqualink.systems.vr.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_set_stepper(client, "SN42", 30)
        finally:
            ws_mod.send_robot_frame = original

        self.assertEqual(len(captured), 1)
        _, recorded_frame = captured[0]
        self.assertEqual(
            recorded_frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"stepper": 30}},
        )


class TestSendRemoteSteering(unittest.IsolatedAsyncioTestCase):
    async def test_send_remote_steering_equipment_and_action(self) -> None:
        import iaqualink.systems.vr.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_remote_steering(client, "SN42", 1)
        finally:
            ws_mod.send_robot_frame = original

        self.assertEqual(len(captured), 1)
        _, recorded_frame = captured[0]
        self.assertEqual(
            recorded_frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"rmt_ctrl": 1}},
        )
        self.assertEqual(
            recorded_frame["action"],
            ACTION_SET_REMOTE_STEERING,
        )
        self.assertEqual(recorded_frame["action"], "setRemoteSteeringControl")


if __name__ == "__main__":
    unittest.main()
