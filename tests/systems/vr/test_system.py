from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.vr.const import (
    CYCLE_FLOOR_AND_WALLS,
    CYCLE_FLOOR_ONLY,
    REMOTE_BACKWARD,
    REMOTE_FORWARD,
    REMOTE_ROTATE_LEFT,
    REMOTE_ROTATE_RIGHT,
    REMOTE_STOP,
    VR_STATE_CLEANING,
    VR_STATE_PAUSED,
    VR_STATE_RETURNING,
    VR_STATE_STOPPED,
)
from iaqualink.systems.vr.system import VrSystem


SAMPLE_SHADOW = {
    "state": {
        "reported": {
            "equipment": {
                "robot": {
                    "state": 1,
                    "canister": 0.5,
                    "errorState": 0,
                    "totalHours": 42,
                    "prCyc": 1,
                    "stepper": 30,
                    "stepperAdjTime": 15,
                    "cycleStartTime": 1_000_000,
                    "durations": {
                        "wall": 60,
                        "floor": 90,
                        "smart": 120,
                        "deep": 150,
                    },
                    "sensors": {
                        "sns_1": {"val": 24, "state": 1},
                    },
                    "vr": "V42",
                }
            }
        }
    }
}


def _system() -> VrSystem:
    aqualink = MagicMock()
    aqualink.user_id = "user-1"
    aqualink.id_token = "tok"
    aqualink.authentication_token = "auth"
    aqualink.app_client_id = "app-id"
    data = {
        "id": 1,
        "serial_number": "VR-1",
        "device_type": "vr",
        "name": "splish",
    }
    sys = AqualinkSystem.from_data(aqualink, data)
    assert isinstance(sys, VrSystem)
    return sys


class TestVrSystemRegistration(unittest.TestCase):
    def test_from_data_dispatches_to_subclass(self) -> None:
        _ = _system()


class TestVrSystemUpdate(unittest.IsolatedAsyncioTestCase):
    async def test_update_throttled_does_not_flip_online(self) -> None:
        sys = _system()
        sys.online = True
        sys.send_reported_state_request = AsyncMock(
            side_effect=AqualinkServiceThrottledException
        )
        with pytest.raises(AqualinkServiceThrottledException):
            await sys.update()
        assert sys.online is True

    async def test_update_service_error_clears_online(self) -> None:
        sys = _system()
        sys.send_reported_state_request = AsyncMock(
            side_effect=AqualinkServiceException
        )
        with pytest.raises(AqualinkServiceException):
            await sys.update()
        assert sys.online is None

    async def test_update_offline_sets_offline(self) -> None:
        sys = _system()
        sys.send_reported_state_request = AsyncMock()
        sys._parse_shadow_response = MagicMock(
            side_effect=AqualinkSystemOfflineException
        )
        with pytest.raises(AqualinkSystemOfflineException):
            await sys.update()
        assert sys.online is False


class TestVrParseShadow(unittest.TestCase):
    def test_parse_populates_attribute_sensors(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = SAMPLE_SHADOW
        sys._parse_shadow_response(response)

        for key in (
            "state",
            "canister",
            "errorState",
            "totalHours",
            "prCyc",
            "stepper",
            "vr",
        ):
            assert key in sys.devices

        # Temperature surfaces from sensors.sns_1.val.
        assert sys.devices["temperature"].state == "24"
        # Running state derives from `state == 1`.
        assert sys.devices["running"].state == "1"
        assert sys.devices["returning"].state == "0"

    def test_parse_returning_sets_returning_true(self) -> None:
        sys = _system()
        payload = {
            "state": {
                "reported": {
                    "equipment": {
                        "robot": {
                            **SAMPLE_SHADOW["state"]["reported"]["equipment"][
                                "robot"
                            ],
                            "state": 3,
                        }
                    }
                }
            }
        }
        response = MagicMock()
        response.json.return_value = payload
        sys._parse_shadow_response(response)
        assert sys.devices["returning"].state == "1"
        assert sys.devices["running"].state == "0"

    def test_parse_no_robot_raises_offline(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = {"state": {"reported": {"equipment": {}}}}
        with pytest.raises(AqualinkSystemOfflineException):
            sys._parse_shadow_response(response)

    def test_time_remaining_uses_durations_index_and_stepper(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = SAMPLE_SHADOW
        with patch(
            "iaqualink.systems.vr.system.time.time",
            return_value=1_000_000 + 30 * 60,
        ):
            sys._parse_shadow_response(response)
        # prCyc=1 -> durations index 1 = 90 min; stepper=30 -> total 120
        # min; 30 min elapsed -> 90 min remaining = 5400 sec.
        assert sys.devices["time_remaining_sec"].state == "5400"


class TestVrControl(unittest.IsolatedAsyncioTestCase):
    async def test_start_sends_state_cleaning(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.vr.ws.send_set_state",
            new_callable=AsyncMock,
        ) as send:
            await sys.start_cleaning()
            send.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                VR_STATE_CLEANING,
                namespace="vr",
            )

    async def test_start_with_cycle_sets_cycle_first(self) -> None:
        sys = _system()
        with (
            patch(
                "iaqualink.systems.vr.ws.send_set_cycle",
                new_callable=AsyncMock,
            ) as send_cycle,
            patch(
                "iaqualink.systems.vr.ws.send_set_state",
                new_callable=AsyncMock,
            ) as send_state,
        ):
            await sys.start_cleaning(cycle=CYCLE_FLOOR_AND_WALLS)
            send_cycle.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                CYCLE_FLOOR_AND_WALLS,
                namespace="vr",
            )
            send_state.assert_awaited_once()

    async def test_set_cycle_invalid_raises(self) -> None:
        sys = _system()
        with pytest.raises(AqualinkInvalidParameterException):
            await sys.set_cycle(99)

    async def test_stop_sends_state_zero(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.vr.ws.send_set_state",
            new_callable=AsyncMock,
        ) as send:
            await sys.stop_cleaning()
            send.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                VR_STATE_STOPPED,
                namespace="vr",
            )

    async def test_pause_sends_state_two(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.vr.ws.send_set_state",
            new_callable=AsyncMock,
        ) as send:
            await sys.pause_cleaning()
            send.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                VR_STATE_PAUSED,
                namespace="vr",
            )

    async def test_return_to_base_sends_state_three(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.vr.ws.send_set_state",
            new_callable=AsyncMock,
        ) as send:
            await sys.return_to_base()
            send.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                VR_STATE_RETURNING,
                namespace="vr",
            )

    async def test_set_runtime_extension_validates(self) -> None:
        sys = _system()
        with pytest.raises(AqualinkInvalidParameterException):
            await sys.set_runtime_extension(7)
        with pytest.raises(AqualinkInvalidParameterException):
            await sys.set_runtime_extension(-15)

    async def test_set_runtime_extension_valid(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.vr.ws.send_set_stepper",
            new_callable=AsyncMock,
        ) as send:
            await sys.set_runtime_extension(45)
            send.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                45,
                namespace="vr",
            )

    async def test_adjust_runtime_clamps_at_zero(self) -> None:
        sys = _system()
        sys._robot_state = {"stepper": 0}
        with patch(
            "iaqualink.systems.vr.ws.send_set_stepper",
            new_callable=AsyncMock,
        ) as send:
            new_value = await sys.adjust_runtime(-15)
            assert new_value == 0
            send.assert_awaited_once_with(
                sys.aqualink, sys.serial, 0, namespace="vr"
            )


class TestVrRemoteControl(unittest.IsolatedAsyncioTestCase):
    async def test_remote_forward_enters_pause_then_sends_direction(
        self,
    ) -> None:
        sys = _system()
        with (
            patch(
                "iaqualink.systems.vr.ws.send_set_state",
                new_callable=AsyncMock,
            ) as send_state,
            patch(
                "iaqualink.systems.vr.ws.send_remote_steering",
                new_callable=AsyncMock,
            ) as send_remote,
        ):
            await sys.remote_forward()
            send_state.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                VR_STATE_PAUSED,
                namespace="vr",
            )
            send_remote.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                REMOTE_FORWARD,
                namespace="vr",
            )

    async def test_remote_subsequent_calls_skip_pause_entry(self) -> None:
        sys = _system()
        with (
            patch(
                "iaqualink.systems.vr.ws.send_set_state",
                new_callable=AsyncMock,
            ) as send_state,
            patch(
                "iaqualink.systems.vr.ws.send_remote_steering",
                new_callable=AsyncMock,
            ) as send_remote,
        ):
            await sys.remote_forward()
            await sys.remote_backward()
            await sys.remote_rotate_left()
            await sys.remote_rotate_right()
            assert send_state.await_count == 1  # only once on first call
            assert send_remote.await_count == 4
            calls = [c.args[2] for c in send_remote.await_args_list]
            assert calls == [
                REMOTE_FORWARD,
                REMOTE_BACKWARD,
                REMOTE_ROTATE_LEFT,
                REMOTE_ROTATE_RIGHT,
            ]

    async def test_remote_stop_exits_remote_mode(self) -> None:
        sys = _system()
        sys._remote_control_active = True
        with (
            patch(
                "iaqualink.systems.vr.ws.send_set_state",
                new_callable=AsyncMock,
            ) as send_state,
            patch(
                "iaqualink.systems.vr.ws.send_remote_steering",
                new_callable=AsyncMock,
            ) as send_remote,
        ):
            await sys.remote_stop()
            send_remote.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                REMOTE_STOP,
                namespace="vr",
            )
            send_state.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                VR_STATE_STOPPED,
                namespace="vr",
            )
            assert sys._remote_control_active is False


class TestVrFrameShape(unittest.TestCase):
    def test_state_frame_uses_robot_slot_and_namespace(self) -> None:
        from iaqualink.systems.vr.ws import build_robot_state_frame

        frame = build_robot_state_frame("VR-1", {"state": 1}, "tok")
        assert frame["namespace"] == "vr"
        assert frame["payload"]["state"]["desired"]["equipment"] == {
            "robot": {"state": 1}
        }

    def test_state_frame_namespace_overridable(self) -> None:
        from iaqualink.systems.vr.ws import build_robot_state_frame

        frame = build_robot_state_frame(
            "T-1", {"state": 1}, "tok", namespace="vortrax"
        )
        assert frame["namespace"] == "vortrax"

    def test_remote_frame_uses_setRemoteSteering_action(self) -> None:
        from iaqualink.systems.vr.ws import build_robot_state_frame

        frame = build_robot_state_frame(
            "VR-1",
            {"rmt_ctrl": REMOTE_FORWARD},
            "tok",
            action="setRemoteSteeringControl",
        )
        assert frame["action"] == "setRemoteSteeringControl"


class TestUnusedConsts(unittest.TestCase):
    """Reference imports so unused-import lint stays quiet without
    over-engineering: ensures all constants are exported from the public
    module surface."""

    def test_cycle_floor_only_is_one(self) -> None:
        assert CYCLE_FLOOR_ONLY == 1
