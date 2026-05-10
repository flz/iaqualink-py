from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pytest

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.cyclonext.device import (
    CyclonextAttributeSensor,
    CyclonextBinarySensor,
    CyclonextErrorSensor,
)
from iaqualink.systems.cyclonext.system import CyclonextSystem

from ...common import async_noop, async_raises

SAMPLE_DATA = {
    "deviceId": "KL0000000000",
    "ts": 1777276817,
    "state": {
        "reported": {
            "aws": {
                "session_id": "abc",
                "status": "connected",
                "timestamp": 1777274387538,
            },
            "dt": "cyc",
            "eboxData": {
                "completeCleanerPn": "WR000000",
                "completeCleanerSn": "ALCA00000000000000",
                "controlBoxPn": "00000000",
                "controlBoxSn": "ONA0000000",
                "motorBlockSn": "EPA0000000",
                "powerSupplySn": "AP00000000",
            },
            "equipment": {
                "robot": [
                    None,
                    {
                        "canister": 0,
                        "cycle": 1,
                        "cycleStartTime": 1777273633,
                        "direction": 0,
                        "equipmentId": "ND00000000",
                        "errors": {"code": 0, "timestamp": 0},
                        "mode": 1,
                        "totRunTime": 15041,
                        "vr": "V21E27",
                    },
                ],
            },
            "jobId": "cyclonext_TEST_FIXTURE",
            "payloadVer": 2,
            "sn": "KL0000000000",
            "vr": "V21C27",
        },
    },
}


def _system() -> CyclonextSystem:
    aqualink = MagicMock()
    data = {
        "id": 1,
        "serial_number": "KL0000000000",
        "device_type": "cyclonext",
    }
    sys = AqualinkSystem.from_data(aqualink, data)
    assert isinstance(sys, CyclonextSystem)
    return sys


class TestCyclonextSystem(unittest.IsolatedAsyncioTestCase):
    def test_from_data_dispatches_to_subclass(self) -> None:
        # V4: NAME registry; V5: import wired in client.py.
        _ = _system()

    async def test_update_success(self) -> None:
        sys = _system()
        sys.send_reported_state_request = async_noop
        sys._parse_shadow_response = MagicMock()
        await sys.update()
        assert sys.online is True

    async def test_update_service_exception(self) -> None:
        sys = _system()
        sys.send_reported_state_request = async_raises(AqualinkServiceException)
        with pytest.raises(AqualinkServiceException):
            await sys.update()
        assert sys.online is None

    async def test_update_throttled_does_not_flip_online(self) -> None:
        # V7: throttle re-raise BEFORE broader handler; online stays unchanged.
        sys = _system()
        sys.online = True
        sys.send_reported_state_request = async_raises(
            AqualinkServiceThrottledException
        )
        with pytest.raises(AqualinkServiceThrottledException):
            await sys.update()
        assert sys.online is True

    async def test_update_offline(self) -> None:
        sys = _system()
        sys.send_reported_state_request = async_noop
        sys._parse_shadow_response = MagicMock(
            side_effect=AqualinkSystemOfflineException
        )
        with pytest.raises(AqualinkSystemOfflineException):
            await sys.update()
        assert sys.online is False

    def test_parse_shadow_populates_devices(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        sys._parse_shadow_response(response)

        # Robot scalar attributes surfaced as attribute sensors.
        for key in ("mode", "cycle", "totRunTime", "vr", "equipmentId"):
            assert key in sys.devices
            assert isinstance(sys.devices[key], CyclonextAttributeSensor)

        # Error code surfaced as dedicated sensor.
        assert "error_code" in sys.devices
        assert isinstance(sys.devices["error_code"], CyclonextErrorSensor)
        assert sys.devices["error_code"].state == "0"

        # eboxData fields prefixed.
        assert "ebox_completeCleanerSn" in sys.devices
        assert (
            sys.devices["ebox_completeCleanerSn"].state == "ALCA00000000000000"
        )
        assert "ebox_controlBoxSn" in sys.devices

        # System-level firmware.
        assert "control_box_vr" in sys.devices
        assert sys.devices["control_box_vr"].state == "V21C27"

        # Running binary sensor reflects mode.
        assert "running" in sys.devices
        running = sys.devices["running"]
        assert isinstance(running, CyclonextBinarySensor)
        assert running.is_on is True

    def test_parse_shadow_running_false_when_mode_zero(self) -> None:
        sys = _system()
        payload = SAMPLE_DATA.copy()
        # Deep enough copy for the field we mutate.
        reported = payload["state"]["reported"]
        robot_dict = reported["equipment"]["robot"][1].copy()
        robot_dict["mode"] = 0
        new_reported = {
            **reported,
            "equipment": {"robot": [None, robot_dict]},
        }
        payload = {
            **payload,
            "state": {"reported": new_reported},
        }
        response = MagicMock()
        response.json.return_value = payload
        sys._parse_shadow_response(response)
        assert sys.devices["running"].is_on is False

    def test_parse_shadow_time_remaining_floor_cycle(self) -> None:
        # Floor cycle (id=1) maps to durations.quickTim (90 min observed).
        # Patch time.time so result is deterministic.
        sys = _system()
        from unittest.mock import patch

        payload = {
            "state": {
                "reported": {
                    "equipment": {
                        "robot": [
                            None,
                            {
                                "mode": 1,
                                "cycle": 1,
                                "cycleStartTime": 1_000_000,
                                "durations": {"quickTim": 90},
                            },
                        ]
                    }
                }
            }
        }
        response = MagicMock()
        response.json.return_value = payload
        # 30 min into the cycle => 60 min remaining = 3600 sec.
        with patch(
            "iaqualink.systems.cyclonext.system.time.time",
            return_value=1_000_000 + 30 * 60,
        ):
            sys._parse_shadow_response(response)
        assert sys.devices["time_remaining_sec"].state == "3600"

    def test_parse_shadow_time_remaining_zero_when_stopped(self) -> None:
        sys = _system()
        payload = {
            "state": {
                "reported": {
                    "equipment": {
                        "robot": [
                            None,
                            {
                                "mode": 0,
                                "cycle": 1,
                                "cycleStartTime": 1_000_000,
                                "durations": {"quickTim": 90},
                            },
                        ]
                    }
                }
            }
        }
        response = MagicMock()
        response.json.return_value = payload
        sys._parse_shadow_response(response)
        assert sys.devices["time_remaining_sec"].state == "0"

    def test_parse_shadow_time_remaining_absent_for_unknown_cycle(
        self,
    ) -> None:
        sys = _system()
        payload = {
            "state": {
                "reported": {
                    "equipment": {
                        "robot": [
                            None,
                            {
                                "mode": 1,
                                "cycle": 99,  # unmapped
                                "cycleStartTime": 1_000_000,
                                "durations": {"quickTim": 90},
                            },
                        ]
                    }
                }
            }
        }
        response = MagicMock()
        response.json.return_value = payload
        sys._parse_shadow_response(response)
        assert "time_remaining_sec" not in sys.devices

    def test_parse_shadow_surfaces_model_number_from_data(self) -> None:
        # Model Number = devices.json `id`. Confirmed live: 100000 for Alpha.
        sys = _system()
        sys.data["id"] = 100000
        response = MagicMock()
        response.json.return_value = SAMPLE_DATA
        sys._parse_shadow_response(response)
        assert sys.devices["model_number"].state == "100000"

    def test_parse_shadow_no_robot_raises_offline(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = {
            "state": {"reported": {"equipment": {"robot": [None]}}}
        }
        with pytest.raises(AqualinkSystemOfflineException):
            sys._parse_shadow_response(response)
