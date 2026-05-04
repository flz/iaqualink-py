from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.cyclonext.const import (
    CYCLE_DURATION_KEY,
    DIRECTION_BACKWARD,
    DIRECTION_FORWARD,
    DIRECTION_LIFT_EJECT,
    DIRECTION_LIFT_ROTATE_LEFT,
    DIRECTION_LIFT_ROTATE_RIGHT,
    DIRECTION_ROTATE_LEFT,
    DIRECTION_ROTATE_RIGHT,
    DIRECTION_STOP,
    MODE_LIFT,
    MODE_PAUSE,
    MODE_REMOTE,
    MODE_START,
    MODE_STOP,
    RUNTIME_EXTENSION_STEP_MIN,
)
from iaqualink.systems.cyclonext.device import CyclonextDevice
from iaqualink.typing import Payload

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient

CYCLONEXT_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"

LOGGER = logging.getLogger("iaqualink")


class CyclonextSystem(AqualinkSystem):
    NAME = "cyclonext"
    # Mirror eXO; both use prod.zodiac-io.com and exhibit similar throttling.
    MIN_SECS_TO_REFRESH: ClassVar[int] = 50

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
            url = f"{CYCLONEXT_DEVICES_URL}/{self.serial}/shadow"
            headers = {"Authorization": self.aqualink.id_token}
            return await self.aqualink.send_request(
                url,
                headers=headers,
                **kwargs,
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
            # V7: re-raise without flipping online; throttling != offline.
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

    def _compute_time_remaining_seconds(
        self, robot: dict[str, Any]
    ) -> int | None:
        if robot.get("mode", MODE_STOP) == MODE_STOP:
            return 0
        cycle = robot.get("cycle")
        start = robot.get("cycleStartTime")
        durations = robot.get("durations") or {}
        if cycle is None or start is None:
            return None
        key = CYCLE_DURATION_KEY.get(int(cycle))
        if key is None or key not in durations:
            return None
        total_min = durations[key]
        end = int(start) + int(total_min) * 60
        now = int(time.time())
        return max(0, end - now)

    def _parse_shadow_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug("Shadow response: %s", data)

        reported = data["state"]["reported"]
        # Robot payload lives at index 1; index 0 is always null.
        robot_list = reported.get("equipment", {}).get("robot", [])
        robot = next((r for r in robot_list if isinstance(r, dict)), None)
        if robot is None:
            raise AqualinkSystemOfflineException

        # Cache for derived computations (e.g. time_remaining_seconds).
        self._robot_state = robot

        ebox = reported.get("eboxData", {})

        devices: dict[str, dict[str, Any]] = {}

        # Scalar robot attributes -> attribute sensors.
        for key, value in robot.items():
            if isinstance(value, (dict, list)):
                continue
            devices[key] = {"name": key, "state": value}

        # Surface error code as a dedicated sensor.
        err = robot.get("errors") or {}
        if "code" in err:
            devices["error_code"] = {
                "name": "error_code",
                "state": err["code"],
            }

        # Hardware identifiers from eboxData.
        for key, value in ebox.items():
            devices[f"ebox_{key}"] = {
                "name": f"ebox_{key}",
                "state": value,
            }

        # System-level firmware (control box) lives at reported.vr.
        if "vr" in reported:
            devices["control_box_vr"] = {
                "name": "control_box_vr",
                "state": reported["vr"],
            }

        # Vendor app's "Model Number" maps to devices.json `id`.
        model_number = self.data.get("id")
        if model_number is not None:
            devices["model_number"] = {
                "name": "model_number",
                "state": model_number,
            }

        # Running binary sensor: mode 0 = stopped, anything else = active.
        mode = robot.get("mode")
        if mode is not None:
            devices["running"] = {
                "name": "running",
                "state": 0 if mode == 0 else 1,
            }

        # Derived: cycle time remaining (seconds). None when unknown.
        remaining = self._compute_time_remaining_seconds(robot)
        if remaining is not None:
            devices["time_remaining_sec"] = {
                "name": "time_remaining_sec",
                "state": remaining,
            }

        for k, v in devices.items():
            if k in self.devices:
                self.devices[k].data.update(v)
            else:
                self.devices[k] = CyclonextDevice.from_data(self, v)

    async def set_cycle(self, cycle: int) -> None:
        from iaqualink.systems.cyclonext.ws import send_set_cycle

        await send_set_cycle(self.aqualink, self.serial, cycle=cycle)

    async def start_cleaning(self, cycle: int | None = None) -> None:
        from iaqualink.systems.cyclonext.ws import (
            send_set_cycle,
            send_set_mode,
        )

        if cycle is not None:
            await send_set_cycle(self.aqualink, self.serial, cycle=cycle)
        await send_set_mode(self.aqualink, self.serial, mode=MODE_START)

    async def stop_cleaning(self) -> None:
        # Single canonical exit: stops a cycle and also exits Remote /
        # Lift mode -- the vendor app emits the same frame in all three
        # places.
        from iaqualink.systems.cyclonext.ws import send_set_mode

        await send_set_mode(self.aqualink, self.serial, mode=MODE_STOP)

    async def pause_cleaning(self) -> None:
        from iaqualink.systems.cyclonext.ws import send_set_mode

        await send_set_mode(self.aqualink, self.serial, mode=MODE_PAUSE)

    async def set_runtime_extension(self, minutes: int) -> None:
        if minutes < 0:
            msg = f"Runtime extension cannot be negative (got {minutes})."
            raise AqualinkInvalidParameterException(msg)
        if minutes % RUNTIME_EXTENSION_STEP_MIN != 0:
            msg = (
                f"Runtime extension must be a multiple of "
                f"{RUNTIME_EXTENSION_STEP_MIN} min (got {minutes})."
            )
            raise AqualinkInvalidParameterException(msg)
        from iaqualink.systems.cyclonext.ws import send_set_stepper

        await send_set_stepper(self.aqualink, self.serial, minutes=minutes)

    async def adjust_runtime(self, delta_minutes: int) -> int:
        # Returns new absolute extension. Reads cached `stepper` from the
        # most recent shadow update; clamps at 0 like the vendor app.
        if delta_minutes % RUNTIME_EXTENSION_STEP_MIN != 0:
            msg = (
                f"Runtime delta must be a multiple of "
                f"{RUNTIME_EXTENSION_STEP_MIN} min (got {delta_minutes})."
            )
            raise AqualinkInvalidParameterException(msg)
        current = int(self._robot_state.get("stepper", 0))
        new_value = max(0, current + delta_minutes)
        await self.set_runtime_extension(new_value)
        return new_value

    # --- Remote / Lift System (RE 2026-04-27) -----------------------------

    async def _send_remote_state(self, mode: int, direction: int) -> None:
        from iaqualink.systems.cyclonext.ws import send_set_remote_state

        await send_set_remote_state(
            self.aqualink, self.serial, mode=mode, direction=direction
        )

    # Remote Control (mode=2).
    async def remote_forward(self) -> None:
        await self._send_remote_state(MODE_REMOTE, DIRECTION_FORWARD)

    async def remote_backward(self) -> None:
        await self._send_remote_state(MODE_REMOTE, DIRECTION_BACKWARD)

    async def remote_rotate_left(self) -> None:
        await self._send_remote_state(MODE_REMOTE, DIRECTION_ROTATE_LEFT)

    async def remote_rotate_right(self) -> None:
        await self._send_remote_state(MODE_REMOTE, DIRECTION_ROTATE_RIGHT)

    async def remote_stop(self) -> None:
        await self._send_remote_state(MODE_REMOTE, DIRECTION_STOP)

    # Lift System (mode=3).
    async def lift_eject(self) -> None:
        await self._send_remote_state(MODE_LIFT, DIRECTION_LIFT_EJECT)

    async def lift_rotate_left(self) -> None:
        await self._send_remote_state(MODE_LIFT, DIRECTION_LIFT_ROTATE_LEFT)

    async def lift_rotate_right(self) -> None:
        await self._send_remote_state(MODE_LIFT, DIRECTION_LIFT_ROTATE_RIGHT)

    async def lift_stop(self) -> None:
        await self._send_remote_state(MODE_LIFT, DIRECTION_STOP)
