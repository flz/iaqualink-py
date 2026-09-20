"""Tests for cyclonext WS write commands."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import MagicMock

from iaqualink.systems.cyclonext.ws import (
    CYCLONEXT_NAMESPACE,
    build_desired_state_frame,
    build_set_mode_frame,
    send_set_cycle,
    send_set_mode,
    send_set_remote_state,
    send_set_stepper,
)


class TestBuildDesiredStateFrame(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = build_desired_state_frame("SN42", {"mode": 1}, "tok")

    def test_namespace(self) -> None:
        self.assertEqual(self.frame["namespace"], CYCLONEXT_NAMESPACE)
        self.assertEqual(self.frame["namespace"], "cyclonext")

    def test_target(self) -> None:
        self.assertEqual(self.frame["target"], "SN42")

    def test_action(self) -> None:
        self.assertEqual(self.frame["action"], "setCleanerState")

    def test_client_token(self) -> None:
        self.assertEqual(self.frame["payload"]["clientToken"], "tok")

    def test_equipment_state(self) -> None:
        self.assertEqual(
            self.frame["payload"]["state"]["desired"]["equipment"],
            {"robot.1": {"mode": 1}},
        )


class TestBuildSetModeFrame(unittest.TestCase):
    def test_equipment_state(self) -> None:
        frame = build_set_mode_frame("SN42", 1, "tok")
        self.assertEqual(
            frame["payload"]["state"]["desired"]["equipment"],
            {"robot.1": {"mode": 1}},
        )


def _make_client() -> MagicMock:
    client = MagicMock()
    client.user_id = "42"
    client.authentication_token = "tok"
    client.app_client_id = "abc"
    return client


class TestSendSetMode(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_mode_calls_send_robot_frame_with_correct_args(
        self,
    ) -> None:
        import iaqualink.systems.cyclonext.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_set_mode(client, "SN42", 1)
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
            {"robot.1": {"mode": 1}},
        )


class TestSendSetCycle(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_cycle_equipment(self) -> None:
        import iaqualink.systems.cyclonext.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_set_cycle(client, "SN42", 3)
        finally:
            ws_mod.send_robot_frame = original

        self.assertEqual(len(captured), 1)
        _, recorded_frame = captured[0]
        self.assertEqual(
            recorded_frame["payload"]["state"]["desired"]["equipment"],
            {"robot.1": {"cycle": 3}},
        )


class TestSendSetStepper(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_stepper_equipment(self) -> None:
        import iaqualink.systems.cyclonext.ws as ws_mod

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
            {"robot.1": {"stepper": 30}},
        )


class TestSendSetRemoteState(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_remote_state_equipment(self) -> None:
        import iaqualink.systems.cyclonext.ws as ws_mod

        client = _make_client()
        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_robot_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_robot_frame
        try:
            ws_mod.send_robot_frame = cast(Any, fake_send_robot_frame)
            await send_set_remote_state(client, "SN42", 2, 1)
        finally:
            ws_mod.send_robot_frame = original

        self.assertEqual(len(captured), 1)
        _, recorded_frame = captured[0]
        self.assertEqual(
            recorded_frame["payload"]["state"]["desired"]["equipment"],
            {"robot.1": {"mode": 2, "direction": 1}},
        )


if __name__ == "__main__":
    unittest.main()
