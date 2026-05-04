from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iaqualink.systems.cyclonext.system import CyclonextSystem
from iaqualink.systems.cyclonext.ws import (
    CYCLONEXT_WS_URL,
    CyclonextWebsocketDependencyError,
    build_desired_state_frame,
    build_set_mode_frame,
    send_set_cycle,
    send_set_mode,
    send_set_remote_state,
    send_set_stepper,
)
from iaqualink.system import AqualinkSystem


def _aqualink() -> MagicMock:
    aqualink = MagicMock()
    aqualink.user_id = "user-1"
    aqualink.id_token = "id-token-xyz"
    aqualink.authentication_token = "auth-token-xyz"
    return aqualink


def _system() -> CyclonextSystem:
    aqualink = _aqualink()
    data = {
        "id": 1,
        "serial_number": "KL0000000000",
        "device_type": "cyclonext",
    }
    sys = AqualinkSystem.from_data(aqualink, data)
    assert isinstance(sys, CyclonextSystem)
    return sys


class TestBuildFrame(unittest.TestCase):
    def test_frame_shape_matches_vendor(self) -> None:
        frame = build_set_mode_frame("KL1", mode=1, client_token="user|abc")
        assert frame == {
            "version": 1,
            "action": "setCleanerState",
            "namespace": "cyclonext",
            "service": "StateController",
            "target": "KL1",
            "payload": {
                "clientToken": "user|abc",
                "state": {
                    "desired": {
                        "equipment": {"robot.1": {"mode": 1}},
                    },
                },
            },
        }


class _FakeWsConn:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.send = AsyncMock(side_effect=self._record)
        self.recv = AsyncMock(return_value='{"event":"StateReported"}')

    async def _record(self, payload: str) -> None:
        self.sent.append(payload)

    async def __aenter__(self) -> _FakeWsConn:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class TestSendSetMode(unittest.IsolatedAsyncioTestCase):
    async def test_send_uses_correct_url_headers_and_payload(self) -> None:
        aqualink = _aqualink()
        fake = _FakeWsConn()
        connect_mock = MagicMock(return_value=fake)
        with patch("iaqualink.systems._robot_ws.ws_connect", connect_mock):
            await send_set_mode(aqualink, "KL0000000000", mode=1)

        connect_mock.assert_called_once()
        args, kwargs = connect_mock.call_args
        assert args[0] == CYCLONEXT_WS_URL
        assert kwargs["additional_headers"] == {"Authorization": "id-token-xyz"}
        assert len(fake.sent) == 1
        sent = json.loads(fake.sent[0])
        assert sent["action"] == "setCleanerState"
        assert sent["namespace"] == "cyclonext"
        assert sent["target"] == "KL0000000000"
        assert (
            sent["payload"]["state"]["desired"]["equipment"]["robot.1"]["mode"]
            == 1
        )
        # clientToken format: {user_id}|<random>
        assert sent["payload"]["clientToken"].startswith("user-1|")

    async def test_missing_dependency_raises(self) -> None:
        with patch("iaqualink.systems._robot_ws.ws_connect", None):
            with pytest.raises(CyclonextWebsocketDependencyError):
                await send_set_mode(_aqualink(), "KL", mode=1)

    async def test_recv_failure_swallowed(self) -> None:
        aqualink = _aqualink()
        fake = _FakeWsConn()
        fake.recv = AsyncMock(side_effect=RuntimeError("boom"))
        connect_mock = MagicMock(return_value=fake)
        with patch("iaqualink.systems._robot_ws.ws_connect", connect_mock):
            # Should not raise even when ack fails.
            await send_set_mode(aqualink, "KL", mode=0)


class TestSendSetCycle(unittest.IsolatedAsyncioTestCase):
    async def test_cycle_frame_carries_cycle_field(self) -> None:
        aqualink = _aqualink()
        fake = _FakeWsConn()
        connect_mock = MagicMock(return_value=fake)
        with patch("iaqualink.systems._robot_ws.ws_connect", connect_mock):
            await send_set_cycle(aqualink, "KL", cycle=3)

        sent = json.loads(fake.sent[0])
        assert sent["payload"]["state"]["desired"]["equipment"]["robot.1"] == {
            "cycle": 3
        }


class TestSendSetStepper(unittest.IsolatedAsyncioTestCase):
    async def test_stepper_frame_carries_stepper_field(self) -> None:
        aqualink = _aqualink()
        fake = _FakeWsConn()
        connect_mock = MagicMock(return_value=fake)
        with patch("iaqualink.systems._robot_ws.ws_connect", connect_mock):
            await send_set_stepper(aqualink, "KL", minutes=30)

        sent = json.loads(fake.sent[0])
        assert sent["payload"]["state"]["desired"]["equipment"]["robot.1"] == {
            "stepper": 30
        }


class TestSendSetRemoteState(unittest.IsolatedAsyncioTestCase):
    async def test_remote_frame_carries_mode_and_direction(self) -> None:
        aqualink = _aqualink()
        fake = _FakeWsConn()
        connect_mock = MagicMock(return_value=fake)
        with patch("iaqualink.systems._robot_ws.ws_connect", connect_mock):
            await send_set_remote_state(aqualink, "KL", mode=2, direction=1)
        sent = json.loads(fake.sent[0])
        assert sent["payload"]["state"]["desired"]["equipment"]["robot.1"] == {
            "mode": 2,
            "direction": 1,
        }


class TestRemoteAndLiftMethods(unittest.IsolatedAsyncioTestCase):
    async def test_remote_methods_send_correct_direction(self) -> None:
        sys = _system()
        cases = [
            ("remote_forward", 2, 1),
            ("remote_backward", 2, 2),
            ("remote_rotate_right", 2, 3),
            ("remote_rotate_left", 2, 4),
            ("remote_stop", 2, 0),
        ]
        for method_name, expected_mode, expected_dir in cases:
            with patch(
                "iaqualink.systems.cyclonext.ws.send_set_remote_state",
                new_callable=AsyncMock,
            ) as send:
                await getattr(sys, method_name)()
                send.assert_awaited_once_with(
                    sys.aqualink,
                    sys.serial,
                    mode=expected_mode,
                    direction=expected_dir,
                )

    async def test_lift_methods_send_correct_direction(self) -> None:
        sys = _system()
        cases = [
            ("lift_eject", 3, 5),
            ("lift_rotate_left", 3, 6),
            ("lift_rotate_right", 3, 7),
            ("lift_stop", 3, 0),
        ]
        for method_name, expected_mode, expected_dir in cases:
            with patch(
                "iaqualink.systems.cyclonext.ws.send_set_remote_state",
                new_callable=AsyncMock,
            ) as send:
                await getattr(sys, method_name)()
                send.assert_awaited_once_with(
                    sys.aqualink,
                    sys.serial,
                    mode=expected_mode,
                    direction=expected_dir,
                )

    async def test_stop_cleaning_is_canonical_mode_zero(self) -> None:
        # `stop_cleaning` is the single canonical mode=0 emitter.
        # Same frame stops a cycle AND exits Remote / Lift mode.
        sys = _system()
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_mode",
            new_callable=AsyncMock,
        ) as send:
            await sys.stop_cleaning()
            send.assert_awaited_once_with(sys.aqualink, sys.serial, mode=0)


class TestBuildDesiredStateFrame(unittest.TestCase):
    def test_arbitrary_state_passes_through(self) -> None:
        frame = build_desired_state_frame("K", {"mode": 1, "cycle": 3}, "tok")
        assert frame["payload"]["state"]["desired"]["equipment"]["robot.1"] == {
            "mode": 1,
            "cycle": 3,
        }


class TestSystemControlMethods(unittest.IsolatedAsyncioTestCase):
    async def test_start_cleaning_sends_mode_1(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_mode",
            new_callable=AsyncMock,
        ) as send:
            await sys.start_cleaning()
            send.assert_awaited_once_with(sys.aqualink, sys.serial, mode=1)

    async def test_stop_cleaning_sends_mode_0(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_mode",
            new_callable=AsyncMock,
        ) as send:
            await sys.stop_cleaning()
            send.assert_awaited_once_with(sys.aqualink, sys.serial, mode=0)

    async def test_start_cleaning_with_cycle_sets_cycle_first(
        self,
    ) -> None:
        sys = _system()
        with (
            patch(
                "iaqualink.systems.cyclonext.ws.send_set_cycle",
                new_callable=AsyncMock,
            ) as send_cycle,
            patch(
                "iaqualink.systems.cyclonext.ws.send_set_mode",
                new_callable=AsyncMock,
            ) as send_mode,
        ):
            await sys.start_cleaning(cycle=3)
            send_cycle.assert_awaited_once_with(
                sys.aqualink, sys.serial, cycle=3
            )
            send_mode.assert_awaited_once_with(sys.aqualink, sys.serial, mode=1)

    async def test_start_cleaning_without_cycle_skips_cycle_call(
        self,
    ) -> None:
        sys = _system()
        with (
            patch(
                "iaqualink.systems.cyclonext.ws.send_set_cycle",
                new_callable=AsyncMock,
            ) as send_cycle,
            patch(
                "iaqualink.systems.cyclonext.ws.send_set_mode",
                new_callable=AsyncMock,
            ) as send_mode,
        ):
            await sys.start_cleaning()
            send_cycle.assert_not_awaited()
            send_mode.assert_awaited_once()

    async def test_set_runtime_extension_zero_ok(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_stepper",
            new_callable=AsyncMock,
        ) as send:
            await sys.set_runtime_extension(0)
            send.assert_awaited_once_with(sys.aqualink, sys.serial, minutes=0)

    async def test_set_runtime_extension_multiple_of_15(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_stepper",
            new_callable=AsyncMock,
        ) as send:
            await sys.set_runtime_extension(45)
            send.assert_awaited_once_with(sys.aqualink, sys.serial, minutes=45)

    async def test_set_runtime_extension_rejects_non_multiple(
        self,
    ) -> None:
        from iaqualink.exception import (
            AqualinkInvalidParameterException,
        )

        sys = _system()
        with pytest.raises(AqualinkInvalidParameterException):
            await sys.set_runtime_extension(7)

    async def test_set_runtime_extension_rejects_negative(self) -> None:
        from iaqualink.exception import (
            AqualinkInvalidParameterException,
        )

        sys = _system()
        with pytest.raises(AqualinkInvalidParameterException):
            await sys.set_runtime_extension(-15)

    async def test_adjust_runtime_adds_to_cached_stepper(self) -> None:
        sys = _system()
        sys._robot_state = {"stepper": 15}
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_stepper",
            new_callable=AsyncMock,
        ) as send:
            new_value = await sys.adjust_runtime(15)
            assert new_value == 30
            send.assert_awaited_once_with(sys.aqualink, sys.serial, minutes=30)

    async def test_adjust_runtime_clamps_at_zero(self) -> None:
        sys = _system()
        sys._robot_state = {"stepper": 0}
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_stepper",
            new_callable=AsyncMock,
        ) as send:
            new_value = await sys.adjust_runtime(-15)
            assert new_value == 0
            send.assert_awaited_once_with(sys.aqualink, sys.serial, minutes=0)

    async def test_set_cycle_calls_send_set_cycle(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_cycle",
            new_callable=AsyncMock,
        ) as send_cycle:
            await sys.set_cycle(1)
            send_cycle.assert_awaited_once_with(
                sys.aqualink, sys.serial, cycle=1
            )

    async def test_pause_cleaning_sends_mode_2(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclonext.ws.send_set_mode",
            new_callable=AsyncMock,
        ) as send:
            await sys.pause_cleaning()
            send.assert_awaited_once_with(sys.aqualink, sys.serial, mode=2)
