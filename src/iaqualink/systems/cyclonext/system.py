"""Cyclonext — wired Zodiac robot cleaner with cycle scheduling and Remote/Lift modes."""

from __future__ import annotations

__all__ = ["CYCLONEXT_DEVICES_URL", "CyclonextSystem"]

import logging
import time
from typing import TYPE_CHECKING, Any

from iaqualink.exception import (
    AqualinkInvalidParameterException,
    _AqualinkOfflineSignal,
)
from iaqualink.shared.robots import RobotStateSubscription, deep_merge
from iaqualink.system import AqualinkSystem, SystemStatus
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
from iaqualink.systems.cyclonext.ws import (
    send_set_cycle,
    send_set_mode,
    send_set_remote_state,
    send_set_stepper,
)
from iaqualink.utils.redact import mask_serial

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

CYCLONEXT_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"

LOGGER = logging.getLogger("iaqualink.systems.cyclonext")


class CyclonextSystem(RobotStateSubscription, AqualinkSystem):
    NAME = "cyclonext"

    def __init__(self, aqualink: AqualinkClient, data: Payload) -> None:
        super().__init__(aqualink, data)
        self._robot_state: dict[str, Any] = {}

    async def send_shadow_request(self, **kwargs: Any) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{CYCLONEXT_DEVICES_URL}/{self.serial}/shadow"
            headers = {"Authorization": self.aqualink.id_token}
            return await self.aqualink.send_request(
                url, headers=headers, **kwargs
            )

        return await self._send_with_reauth_retry(do_request)

    async def _refresh(self) -> None:
        # Reduce polling: when the WS subscription (started by the consumer via
        # start_ws_subscription) has delivered state recently, skip the REST
        # shadow poll. With no live WS, this always falls through to REST.
        if self._ws_enabled and self._ws_state_fresh():
            return
        r = await self.send_shadow_request()
        self._parse_shadow_response(r)
        self.status = SystemStatus.ONLINE

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
        return max(0, end - int(time.time()))

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

        The REST shadow nests it as a list under ``equipment.robot``; the WS
        Authorization/StateStreamer payloads use the dot-keyed
        ``equipment["robot.1"]`` dict.
        """
        equipment = reported.get("equipment") or {}
        dotted = equipment.get("robot.1")
        if isinstance(dotted, dict):
            return dotted
        robot_list = equipment.get("robot")
        if isinstance(robot_list, list):
            return next((r for r in robot_list if isinstance(r, dict)), None)
        if isinstance(robot_list, dict):
            return robot_list
        return None

    def _apply_reported_state(self, reported: dict[str, Any]) -> None:
        """Apply a FULL `state.reported` payload (REST shadow or WS auth ack).

        Caches the robot state and (re)builds the full device registry. WS
        StateStreamer deltas go through `_apply_robot_delta` instead.
        """
        robot = self._extract_robot(reported)
        if robot is None:
            raise _AqualinkOfflineSignal

        # Cache for derived computations (e.g. adjust_runtime) and delta merge.
        self._robot_state = robot

        devices: dict[str, dict[str, Any]] = {}

        # Hardware identifiers from eboxData.
        for key, value in (reported.get("eboxData") or {}).items():
            devices[f"ebox_{key}"] = {"name": f"ebox_{key}", "state": value}

        # System-level firmware (control box) lives at reported.vr.
        if "vr" in reported:
            devices["control_box_vr"] = {
                "name": "control_box_vr",
                "state": reported["vr"],
            }

        self._ingest_devices(devices)
        self._rebuild_robot_devices()

    def _rebuild_robot_devices(self) -> None:
        """(Re)derive robot-sourced devices from the cached `_robot_state`."""
        robot = self._robot_state
        devices: dict[str, dict[str, Any]] = {}

        # Scalar robot attributes → attribute sensors.
        for key, value in robot.items():
            if isinstance(value, (dict, list)):
                continue
            devices[key] = {"name": key, "state": value}

        # Surface error code as a dedicated sensor.
        err = robot.get("errors") or {}
        if "code" in err:
            devices["error_code"] = {"name": "error_code", "state": err["code"]}

        # Vendor app "Model Number" maps to devices.json `id`.
        model_number = self.data.get("id")
        if model_number is not None:
            devices["model_number"] = {
                "name": "model_number",
                "state": model_number,
            }

        # Running binary: mode 0 = stopped, anything else = active.
        mode = robot.get("mode")
        if mode is not None:
            devices["running"] = {
                "name": "running",
                "state": 0 if mode == 0 else 1,
            }

        # HA-vacuum-style robot device; reads live runtime off _robot_state.
        devices["robot"] = {
            "name": "robot",
            "state": mode if mode is not None else 0,
        }

        # Derived: cycle time remaining (seconds). None when unknown.
        remaining = self._compute_time_remaining_seconds(robot)
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
                self.devices[k] = CyclonextDevice.from_data(self, v)

    def _apply_robot_delta(self, delta: dict[str, Any]) -> None:
        """Merge a partial robot dict (WS StateStreamer) and re-derive devices."""
        self._robot_state = deep_merge(self._robot_state, delta)
        self._rebuild_robot_devices()

    # --- write commands ---------------------------------------------------

    async def set_cycle(self, cycle: int) -> None:
        await send_set_cycle(self.aqualink, self.serial, cycle=cycle)

    async def start_cleaning(self, cycle: int | None = None) -> None:
        if cycle is not None:
            await send_set_cycle(self.aqualink, self.serial, cycle=cycle)
        await send_set_mode(self.aqualink, self.serial, mode=MODE_START)

    async def stop_cleaning(self) -> None:
        # Single canonical exit: stops a cycle and also exits Remote / Lift
        # mode — vendor app emits the same frame in all three places.
        await send_set_mode(self.aqualink, self.serial, mode=MODE_STOP)

    async def pause_cleaning(self) -> None:
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
        await send_set_stepper(self.aqualink, self.serial, minutes=minutes)

    async def adjust_runtime(self, delta_minutes: int) -> int:
        """Adjust runtime extension by delta. Returns new absolute extension."""
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

    # --- Remote / Lift System --------------------------------------------

    async def _send_remote_state(self, mode: int, direction: int) -> None:
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
