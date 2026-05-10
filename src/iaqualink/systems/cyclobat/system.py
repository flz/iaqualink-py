from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.cyclobat.const import (
    CYCLE_DURATION_KEY,
    CYCLOBAT_CTRL_RETURN,
    CYCLOBAT_CTRL_START,
    CYCLOBAT_CTRL_STOP,
    CYCLOBAT_STATE_CLEANING,
    CYCLOBAT_STATE_RETURNING,
)
from iaqualink.systems.cyclobat.device import CyclobatDevice
from iaqualink.typing import Payload

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient

CYCLOBAT_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"

LOGGER = logging.getLogger("iaqualink")


class CyclobatSystem(AqualinkSystem):
    NAME = "cyclobat"
    MIN_SECS_TO_REFRESH: ClassVar[int] = 30

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)
        self.last_refresh: int = 0
        self._robot_state: dict[str, Any] = {}

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def send_shadow_request(self, **kwargs: Any) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{CYCLOBAT_DEVICES_URL}/{self.serial}/shadow"
            headers = {"Authorization": self.aqualink.id_token}
            return await self.aqualink.send_request(
                url, headers=headers, **kwargs
            )

        return await self._send_with_reauth_retry(do_request)

    async def send_reported_state_request(self) -> httpx.Response:
        return await self.send_shadow_request()

    async def update(self) -> None:
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < self.MIN_SECS_TO_REFRESH:
            LOGGER.debug("Only %ds since last refresh.", delta)
            return

        try:
            r = await self.send_reported_state_request()
        except AqualinkServiceThrottledException:
            raise
        except AqualinkServiceException:
            self.online = None
            raise

        try:
            self._parse_shadow_response(r)
        except AqualinkSystemOfflineException:
            self.online = False
            raise

        self.online = True
        self.last_refresh = int(time.time())

    def _parse_shadow_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("Shadow response: %s", data)

        try:
            reported = data["state"]["reported"]
        except (KeyError, TypeError) as exc:
            raise AqualinkSystemOfflineException from exc

        robot = (reported.get("equipment") or {}).get("robot")
        if not isinstance(robot, dict):
            raise AqualinkSystemOfflineException

        self._robot_state = robot

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

        # Battery sensors.
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
            ("totRunTime", "total_hours"),
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
                devices[target_key] = {
                    "name": target_key,
                    "state": duration,
                }
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

        # Running / returning binary sensors.
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

        # Time remaining derived from cycles[<cycle_key>].duration +
        # main.cycleStartTime - now.
        remaining = self._compute_time_remaining_seconds(
            main, cycles, last_cycle
        )
        if remaining is not None:
            devices["time_remaining_sec"] = {
                "name": "time_remaining_sec",
                "state": remaining,
            }

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

    # --- write commands ---------------------------------------------------

    async def _send_ctrl(self, ctrl: int) -> None:
        from iaqualink.systems.cyclobat.ws import send_set_ctrl

        await send_set_ctrl(self.aqualink, self.serial, ctrl)

    async def start_cleaning(self) -> None:
        await self._send_ctrl(CYCLOBAT_CTRL_START)

    async def stop_cleaning(self) -> None:
        await self._send_ctrl(CYCLOBAT_CTRL_STOP)

    async def return_to_base(self) -> None:
        await self._send_ctrl(CYCLOBAT_CTRL_RETURN)
