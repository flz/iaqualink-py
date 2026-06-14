"""Tests for cyclobat WS write commands."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import MagicMock

from iaqualink.systems.cyclobat.ws import (
    CYCLOBAT_NAMESPACE,
    build_cyclobat_main_ctrl_frame,
    send_set_ctrl,
)


class TestBuildCyclobatMainCtrlFrame(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = build_cyclobat_main_ctrl_frame("SN42", 1, "tok")

    def test_namespace(self) -> None:
        self.assertEqual(self.frame["namespace"], CYCLOBAT_NAMESPACE)
        self.assertEqual(self.frame["namespace"], "cyclobat")

    def test_target(self) -> None:
        self.assertEqual(self.frame["target"], "SN42")

    def test_action(self) -> None:
        self.assertEqual(self.frame["action"], "setCleaningMode")

    def test_client_token(self) -> None:
        self.assertEqual(self.frame["payload"]["clientToken"], "tok")

    def test_equipment_state(self) -> None:
        self.assertEqual(
            self.frame["payload"]["state"]["desired"]["equipment"],
            {"robot": {"main": {"ctrl": 1}}},
        )


class TestSendSetCtrl(unittest.IsolatedAsyncioTestCase):
    async def test_send_set_ctrl_calls_send_frame_with_correct_args(
        self,
    ) -> None:
        import iaqualink.systems.cyclobat.ws as ws_mod

        client = MagicMock()
        client.user_id = "42"
        client.authentication_token = "tok"
        client.app_client_id = "abc"

        captured: list[tuple[object, dict[str, Any]]] = []

        async def fake_send_frame(c: object, f: dict[str, Any]) -> None:
            captured.append((c, f))

        original = ws_mod.send_frame
        try:
            ws_mod.send_frame = cast(Any, fake_send_frame)
            await send_set_ctrl(client, "SN42", 1)
        finally:
            ws_mod.send_frame = original

        self.assertEqual(len(captured), 1)
        recorded_client, recorded_frame = captured[0]
        self.assertIs(recorded_client, client)
        self.assertEqual(
            recorded_frame["payload"]["clientToken"],
            "42|tok|abc",
        )
        self.assertEqual(
            recorded_frame["payload"]["state"]["desired"]["equipment"]["robot"][
                "main"
            ]["ctrl"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
