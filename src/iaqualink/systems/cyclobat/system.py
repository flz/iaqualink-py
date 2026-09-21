"""Cyclobat — battery-powered Zodiac robot cleaner."""

from __future__ import annotations

__all__ = ["CYCLOBAT_DEVICES_URL", "CyclobatSystem"]

import logging
import time
from typing import TYPE_CHECKING, Any

from iaqualink.exception import _AqualinkOfflineSignal
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclobat.const import (
    CYCLE_DURATION_KEY,
    CYCLOBAT_CTRL_RETURN,
    CYCLOBAT_CTRL_START,
    CYCLOBAT_CTRL_STOP,
    CYCLOBAT_STATE_CLEANING,
    CYCLOBAT_STATE_RETURNING,
)
from iaqualink.systems.cyclobat.device import CyclobatDevice
from iaqualink.systems.cyclobat.ws import send_set_ctrl, send_set_mode
from iaqualink.utils.redact import mask_serial
from iaqualink.utils.robots import RobotStateSubscription, deep_merge

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

CYCLOBAT_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"

LOGGER = logging.getLogger("iaqualink.systems.cyclobat")


class CyclobatSystem(RobotStateSubscription, AqualinkSystem):
    NAME = "cyclobat"

    def __init__(self, aqualink: AqualinkClient, data: Payload) -> None:
        super().__init__(aqualink, data)
        self._robot_state: dict[str, Any] = {}

    async def send_shadow_request(self, **kwargs: Any) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{CYCLOBAT_DEVICES_URL}/{self.serial}/shadow"
            headers = {"Authorization": self.aqualink.id_token}
            return await self.aqualink.send_request(
                url, headers=headers, **kwargs
            )

        return await self._send_with_reauth_retry(do_request)

    async def _refresh(self) -> None:
        # Auto-starts the WS subscription (idempotent) and skips the REST
        # poll while it's delivering fresh state.
        if await self._ws_refresh_gate():
            # refresh() resets self.status to IN_PROGRESS before calling
            # _refresh(); restore it here too so the "must set status before
            # returning" contract holds on the skip path.
            self.status = SystemStatus.ONLINE
            return
        r = await self.send_shadow_request()
        self._parse_shadow_response(r)
        self.status = SystemStatus.ONLINE

    def _parse_shadow_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("Shadow parsed serial=%s", mask_serial(self.serial))

        try:
            reported = data["state"]["reported"]
        except (KeyError, TypeError) as exc:
            raise _AqualinkOfflineSignal from exc

        self._apply_reported_state(reported)

    def _extract_robot(self, reported: dict[str, Any]) -> dict[str, Any] | None:
        """Find the robot object in a `reported` payload.

        The REST shadow nests it as a dict under ``equipment.robot``; the WS
        Authorization/StateStreamer payloads use the dot-keyed
        ``equipment["robot.1"]`` dict.
        """
        equipment = reported.get("equipment") or {}
        dotted = equipment.get("robot.1")
        if isinstance(dotted, dict):
            return dotted
        robot = equipment.get("robot")
        if isinstance(robot, dict):
            return robot
        return None

    def _apply_reported_state(self, reported: dict[str, Any]) -> None:
        """Apply a FULL `state.reported` payload (REST shadow or WS auth ack).

        Caches the robot state and (re)builds the device registry. WS
        StateStreamer deltas go through `_apply_robot_delta` instead.
        """
        robot = self._extract_robot(reported)
        if robot is None:
            raise _AqualinkOfflineSignal
        self._robot_state = robot
        self._rebuild_robot_devices()

    def _apply_robot_delta(self, delta: dict[str, Any]) -> None:
        """Merge a partial robot dict (WS StateStreamer) and re-derive."""
        self._robot_state = deep_merge(self._robot_state, delta)
        self._rebuild_robot_devices()

    def _rebuild_robot_devices(self) -> None:
        """(Re)derive all devices from the cached `_robot_state`."""
        robot = self._robot_state

        main = robot.get("main") or {}
        battery = robot.get("battery") or {}
        stats = robot.get("stats") or {}
        last_cycle = robot.get("lastCycle") or {}
        cycles = robot.get("cycles") or {}

        devices: dict[str, dict[str, Any]] = {}

        # Main runtime fields.
        for key in ("state", "ctrl", "mode", "error", "cycleStartTime"):
            if key in main and not isinstance(main[key], (dict, list)):
                devices[f"main_{key}"] = {
                    "name": f"main_{key}",
                    "state": main[key],
                }

        # Battery.
        for src_key, target_key in (
            ("vr", "battery_version"),
            ("state", "battery_state"),
            ("userChargePerc", "battery_percentage"),
            ("userChargeState", "battery_charge_state"),
            ("cycles", "battery_cycles"),
        ):
            if src_key in battery and not isinstance(
                battery[src_key], (dict, list)
            ):
                devices[target_key] = {
                    "name": target_key,
                    "state": battery[src_key],
                }
        warn = (battery.get("warning") or {}).get("code")
        if warn is not None:
            devices["battery_warning_code"] = {
                "name": "battery_warning_code",
                "state": warn,
            }

        # Stats.
        for src_key, target_key in (
            ("totRunTime", "total_runtime"),
            ("diagnostic", "diagnostic_code"),
            ("tmp", "temperature"),
        ):
            if src_key in stats and not isinstance(
                stats[src_key], (dict, list)
            ):
                devices[target_key] = {
                    "name": target_key,
                    "state": stats[src_key],
                }
        last_err = stats.get("lastError") or {}
        if "code" in last_err:
            devices["last_error_code"] = {
                "name": "last_error_code",
                "state": last_err["code"],
            }
        if "cycleNb" in last_err:
            devices["last_error_cycle"] = {
                "name": "last_error_cycle",
                "state": last_err["cycleNb"],
            }

        # Last cycle.
        for src_key, target_key in (
            ("cycleNb", "last_cycle_number"),
            ("duration", "last_cycle_duration"),
            ("mode", "last_cycle_mode"),
            ("endCycleType", "cycle"),
            ("errorCode", "last_cycle_error"),
        ):
            if src_key in last_cycle and not isinstance(
                last_cycle[src_key], (dict, list)
            ):
                devices[target_key] = {
                    "name": target_key,
                    "state": last_cycle[src_key],
                }

        # Cycle durations + housekeeping flags.
        for src_key, target_key in (
            ("floorTim", "floor_duration"),
            ("floorWallsTim", "floor_walls_duration"),
            ("smartTim", "smart_duration"),
            ("waterlineTim", "waterline_duration"),
        ):
            duration = (cycles.get(src_key) or {}).get("duration")
            if duration is not None:
                devices[target_key] = {"name": target_key, "state": duration}
        if "firstSmartDone" in cycles:
            devices["first_smart_done"] = {
                "name": "first_smart_done",
                "state": cycles["firstSmartDone"],
            }
        if "liftPatternTim" in cycles:
            devices["lift_pattern_time"] = {
                "name": "lift_pattern_time",
                "state": cycles["liftPatternTim"],
            }

        # Top-level robot identifiers.
        for key in ("vr", "sn"):
            if key in robot and not isinstance(robot[key], (dict, list)):
                devices[key] = {"name": key, "state": robot[key]}

        # Model number from devices.json `id`.
        model_number = self.data.get("id")
        if model_number is not None:
            devices["model_number"] = {
                "name": "model_number",
                "state": model_number,
            }

        # Binary sensors derived from main.state.
        state_value = main.get("state")
        if state_value is not None:
            devices["running"] = {
                "name": "running",
                "state": int(state_value == CYCLOBAT_STATE_CLEANING),
            }
            devices["returning"] = {
                "name": "returning",
                "state": int(state_value == CYCLOBAT_STATE_RETURNING),
            }

        # HA-vacuum-style robot device. Reads live runtime off _robot_state;
        # the snapshot here just carries raw main.state for repr/eq.
        devices["robot"] = {
            "name": "robot",
            "state": state_value if state_value is not None else 0,
        }

        # Time remaining.
        remaining = self._compute_time_remaining_seconds(
            main, cycles, last_cycle
        )
        if remaining is not None:
            devices["time_remaining_sec"] = {
                "name": "time_remaining_sec",
                "state": remaining,
            }

        self._ingest_devices(devices)

    def _ingest_devices(self, devices: dict[str, dict[str, Any]]) -> None:
        for k, v in devices.items():
            if k in self.devices:
                self.devices[k].data.update(v)
            else:
                self.devices[k] = CyclobatDevice.from_data(self, v)

    def _compute_time_remaining_seconds(
        self,
        main: dict[str, Any],
        cycles: dict[str, Any],
        last_cycle: dict[str, Any],
    ) -> int | None:
        state_value = main.get("state", CYCLOBAT_CTRL_STOP)
        if state_value not in (
            CYCLOBAT_STATE_CLEANING,
            CYCLOBAT_STATE_RETURNING,
        ):
            return 0
        start = main.get("cycleStartTime")
        cycle_id = last_cycle.get("endCycleType")
        if start is None or cycle_id is None:
            return None
        key = CYCLE_DURATION_KEY.get(int(cycle_id))
        if key is None:
            return None
        duration = (cycles.get(key) or {}).get("duration")
        if duration is None:
            return None
        end = int(start) + int(duration) * 60
        return max(0, end - int(time.time()))

    async def start_cleaning(self) -> None:
        await send_set_ctrl(self.aqualink, self.serial, CYCLOBAT_CTRL_START)

    async def stop_cleaning(self) -> None:
        await send_set_ctrl(self.aqualink, self.serial, CYCLOBAT_CTRL_STOP)

    async def return_to_base(self) -> None:
        await send_set_ctrl(self.aqualink, self.serial, CYCLOBAT_CTRL_RETURN)

    async def set_cleaning_mode(self, mode: int) -> None:
        await send_set_mode(self.aqualink, self.serial, mode)
