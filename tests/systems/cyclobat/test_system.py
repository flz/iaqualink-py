from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iaqualink.exception import AqualinkSystemOfflineException
from iaqualink.system import AqualinkSystem
from iaqualink.systems.cyclobat.const import (
    CYCLOBAT_CTRL_RETURN,
    CYCLOBAT_CTRL_START,
    CYCLOBAT_CTRL_STOP,
)
from iaqualink.systems.cyclobat.system import CyclobatSystem


SAMPLE_SHADOW = {
    "state": {
        "reported": {
            "equipment": {
                "robot": {
                    "vr": "B1",
                    "sn": "CB1",
                    "main": {
                        "state": 1,
                        "ctrl": 1,
                        "mode": 0,
                        "error": 0,
                        "cycleStartTime": 1_000_000,
                    },
                    "battery": {
                        "vr": "BV1",
                        "state": 1,
                        "userChargePerc": 80,
                        "userChargeState": "discharging",
                        "cycles": 12,
                        "warning": {"code": 0},
                    },
                    "stats": {
                        "totRunTime": 9999,
                        "diagnostic": 0,
                        "tmp": 23,
                        "lastError": {"code": 0, "cycleNb": 0},
                    },
                    "lastCycle": {
                        "cycleNb": 5,
                        "duration": 90,
                        "mode": 0,
                        "endCycleType": 0,
                        "errorCode": 0,
                    },
                    "cycles": {
                        "floorTim": {"duration": 90},
                        "floorWallsTim": {"duration": 150},
                        "smartTim": {"duration": 120},
                        "waterlineTim": {"duration": 60},
                        "firstSmartDone": False,
                        "liftPatternTim": 0,
                    },
                }
            }
        }
    }
}


def _system() -> CyclobatSystem:
    aqualink = MagicMock()
    aqualink.user_id = "u"
    aqualink.id_token = "tok"
    aqualink.authentication_token = "at"
    aqualink.app_client_id = "app"
    sys = AqualinkSystem.from_data(
        aqualink,
        {
            "id": 555,
            "serial_number": "CB-1",
            "device_type": "cyclobat",
            "name": "alpha-iq",
        },
    )
    assert isinstance(sys, CyclobatSystem)
    return sys


class TestCyclobatRegistration(unittest.TestCase):
    def test_from_data_dispatches(self) -> None:
        _ = _system()


class TestCyclobatParse(unittest.TestCase):
    def test_parse_battery_and_main_fields(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = SAMPLE_SHADOW
        sys._parse_shadow_response(response)

        assert sys.devices["battery_percentage"].state == "80"
        assert sys.devices["battery_charge_state"].state == "discharging"
        assert sys.devices["main_state"].state == "1"
        assert sys.devices["floor_duration"].state == "90"
        assert sys.devices["floor_walls_duration"].state == "150"
        assert sys.devices["model_number"].state == "555"
        assert sys.devices["cycle"].state == "0"
        assert sys.devices["running"].state == "1"
        assert sys.devices["returning"].state == "0"

    def test_parse_no_robot_raises_offline(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = {"state": {"reported": {"equipment": {}}}}
        with pytest.raises(AqualinkSystemOfflineException):
            sys._parse_shadow_response(response)

    def test_time_remaining_floor(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = SAMPLE_SHADOW
        with patch(
            "iaqualink.systems.cyclobat.system.time.time",
            return_value=1_000_000 + 30 * 60,
        ):
            sys._parse_shadow_response(response)
        # floorTim duration 90 min, 30 elapsed -> 3600 sec remaining
        assert sys.devices["time_remaining_sec"].state == "3600"


class TestCyclobatControl(unittest.IsolatedAsyncioTestCase):
    async def test_start_sends_ctrl_one(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclobat.ws.send_set_ctrl",
            new_callable=AsyncMock,
        ) as send:
            await sys.start_cleaning()
            send.assert_awaited_once_with(
                sys.aqualink, sys.serial, CYCLOBAT_CTRL_START
            )

    async def test_stop_sends_ctrl_zero(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclobat.ws.send_set_ctrl",
            new_callable=AsyncMock,
        ) as send:
            await sys.stop_cleaning()
            send.assert_awaited_once_with(
                sys.aqualink, sys.serial, CYCLOBAT_CTRL_STOP
            )

    async def test_return_sends_ctrl_three(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.cyclobat.ws.send_set_ctrl",
            new_callable=AsyncMock,
        ) as send:
            await sys.return_to_base()
            send.assert_awaited_once_with(
                sys.aqualink, sys.serial, CYCLOBAT_CTRL_RETURN
            )


class TestCyclobatFrameShape(unittest.TestCase):
    def test_frame_uses_setCleaningMode_action_and_main_ctrl(self) -> None:
        from iaqualink.systems.cyclobat.ws import (
            build_cyclobat_main_ctrl_frame,
        )

        frame = build_cyclobat_main_ctrl_frame("CB-1", 1, "tok")
        assert frame["action"] == "setCleaningMode"
        assert frame["namespace"] == "cyclobat"
        assert frame["payload"]["state"]["desired"]["equipment"] == {
            "robot": {"main": {"ctrl": 1}}
        }
