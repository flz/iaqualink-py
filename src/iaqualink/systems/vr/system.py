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
from iaqualink.systems.vr.const import (
    CYCLE_LABELS,
    REMOTE_BACKWARD,
    REMOTE_FORWARD,
    REMOTE_ROTATE_LEFT,
    REMOTE_ROTATE_RIGHT,
    REMOTE_STOP,
    RUNTIME_EXTENSION_STEP_MIN,
    VR_STATE_CLEANING,
    VR_STATE_PAUSED,
    VR_STATE_RETURNING,
    VR_STATE_STOPPED,
)
from iaqualink.systems.vr.device import VrDevice
from iaqualink.typing import Payload

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient

VR_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"
VR_NAMESPACE = "vr"

LOGGER = logging.getLogger("iaqualink")


class VrSystem(AqualinkSystem):
    NAME = "vr"
    MIN_SECS_TO_REFRESH: ClassVar[int] = 30

    # Subclasses (e.g. VortraxSystem) override the namespace used in WS
    # frames; the shadow shape and default values are otherwise identical.
    namespace: ClassVar[str] = VR_NAMESPACE

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)
        self.last_refresh: int = 0
        self._robot_state: dict[str, Any] = {}
        self._remote_control_active = False

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def send_shadow_request(self, **kwargs: Any) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{VR_DEVICES_URL}/{self.serial}/shadow"
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

        devices: dict[str, dict[str, Any]] = {}

        # Scalar robot attributes -> attribute sensors.
        for key, value in robot.items():
            if isinstance(value, (dict, list)):
                continue
            devices[key] = {"name": key, "state": value}

        # Optional water-temp sensor (sns_1).
        sensors = robot.get("sensors") or {}
        sns_1 = sensors.get("sns_1") or {}
        temp = sns_1.get("val", sns_1.get("state"))
        if temp is not None:
            devices["temperature"] = {"name": "temperature", "state": temp}

        # Surface model number from devices.json `id`.
        model_number = self.data.get("id")
        if model_number is not None:
            devices["model_number"] = {
                "name": "model_number",
                "state": model_number,
            }

        # Running / returning binary sensors derived from `state`.
        robot_state = robot.get("state")
        if robot_state is not None:
            devices["running"] = {
                "name": "running",
                "state": int(robot_state == VR_STATE_CLEANING),
            }
            devices["returning"] = {
                "name": "returning",
                "state": int(robot_state == VR_STATE_RETURNING),
            }

        # Time remaining (seconds): cycleStartTime + durations[prCyc] +
        # stepper minutes - now. Returns None if data missing.
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
                self.devices[k] = VrDevice.from_data(self, v)

    def _compute_time_remaining_seconds(
        self, robot: dict[str, Any]
    ) -> int | None:
        state = robot.get("state", VR_STATE_STOPPED)
        if state not in (VR_STATE_CLEANING, VR_STATE_RETURNING):
            return 0
        cycle = robot.get("prCyc")
        start = robot.get("cycleStartTime")
        durations = robot.get("durations") or {}
        if cycle is None or start is None or not durations:
            return None
        # Galletn picks duration by ordinal index of prCyc into ordered
        # `durations` dict; replicate that here.
        try:
            duration_min = list(durations.values())[int(cycle)]
        except (IndexError, ValueError):
            return None
        stepper = int(robot.get("stepper") or 0)
        end = int(start) + (int(duration_min) + stepper) * 60
        return max(0, end - int(time.time()))

    # --- write commands ---------------------------------------------------

    async def _send_state(self, state: int) -> None:
        from iaqualink.systems.vr.ws import send_set_state

        await send_set_state(
            self.aqualink,
            self.serial,
            state,
            namespace=self.namespace,
        )

    async def start_cleaning(self, cycle: int | None = None) -> None:
        if cycle is not None:
            await self.set_cycle(cycle)
        await self._send_state(VR_STATE_CLEANING)

    async def stop_cleaning(self) -> None:
        await self._send_state(VR_STATE_STOPPED)

    async def pause_cleaning(self) -> None:
        await self._send_state(VR_STATE_PAUSED)

    async def return_to_base(self) -> None:
        await self._send_state(VR_STATE_RETURNING)

    async def set_cycle(self, cycle: int) -> None:
        if cycle not in CYCLE_LABELS:
            msg = f"Unknown VR cycle id {cycle}. Valid: {sorted(CYCLE_LABELS)}."
            raise AqualinkInvalidParameterException(msg)
        from iaqualink.systems.vr.ws import send_set_cycle

        await send_set_cycle(
            self.aqualink,
            self.serial,
            cycle,
            namespace=self.namespace,
        )

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
        from iaqualink.systems.vr.ws import send_set_stepper

        await send_set_stepper(
            self.aqualink,
            self.serial,
            minutes,
            namespace=self.namespace,
        )

    async def adjust_runtime(self, delta_minutes: int) -> int:
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

    # --- remote control (forward/back/rotate) -----------------------------

    async def _send_remote(self, rmt_ctrl: int) -> None:
        from iaqualink.systems.vr.ws import send_remote_steering

        await send_remote_steering(
            self.aqualink,
            self.serial,
            rmt_ctrl,
            namespace=self.namespace,
        )

    async def _enter_remote_mode(self) -> None:
        if not self._remote_control_active:
            await self._send_state(VR_STATE_PAUSED)
            self._remote_control_active = True

    async def _exit_remote_mode(self) -> None:
        if self._remote_control_active:
            await self._send_state(VR_STATE_STOPPED)
            self._remote_control_active = False

    async def remote_forward(self) -> None:
        await self._enter_remote_mode()
        await self._send_remote(REMOTE_FORWARD)

    async def remote_backward(self) -> None:
        await self._enter_remote_mode()
        await self._send_remote(REMOTE_BACKWARD)

    async def remote_rotate_left(self) -> None:
        await self._enter_remote_mode()
        await self._send_remote(REMOTE_ROTATE_LEFT)

    async def remote_rotate_right(self) -> None:
        await self._enter_remote_mode()
        await self._send_remote(REMOTE_ROTATE_RIGHT)

    async def remote_stop(self) -> None:
        await self._send_remote(REMOTE_STOP)
        await self._exit_remote_mode()
