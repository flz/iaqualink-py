from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.i2d_robot.const import (
    I2D_CONTROL_URL,
    I2D_REQUEST_RETURN_TO_BASE,
    I2D_REQUEST_START,
    I2D_REQUEST_STATUS,
    I2D_REQUEST_STOP,
)
from iaqualink.systems.i2d_robot.device import I2dDevice
from iaqualink.systems.i2d_robot.protocol import parse_status_hex
from iaqualink.typing import Payload

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient

LOGGER = logging.getLogger("iaqualink")


_ACTIVE_STATE_CODES = {0x02, 0x04}  # cleaning_just_started, actively_cleaning


class I2dRobotSystem(AqualinkSystem):
    NAME = "i2d_robot"
    MIN_SECS_TO_REFRESH: ClassVar[int] = 30

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)
        self.last_refresh: int = 0

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    @property
    def _url(self) -> str:
        return I2D_CONTROL_URL.format(serial=self.serial)

    def _build_body(self, request: str) -> dict[str, Any]:
        return {
            "command": "/command",
            "params": f"request={request}",
            "user_id": self.aqualink.user_id,
        }

    async def _post_command(self, request: str) -> dict[str, Any]:
        async def do_request() -> httpx.Response:
            headers = {
                "Authorization": self.aqualink.id_token,
                "api_key": AQUALINK_API_KEY,
            }
            return await self.aqualink.send_request(
                self._url,
                method="post",
                headers=headers,
                json=self._build_body(request),
            )

        response = await self._send_with_reauth_retry(do_request)
        try:
            data = response.json()
        except ValueError as exc:
            msg = f"Invalid JSON response from i2d_robot: {exc}"
            raise AqualinkServiceException(msg) from exc
        if not isinstance(data, dict):
            msg = f"Unexpected i2d_robot response: {data!r}"
            raise AqualinkServiceException(msg)
        return data

    async def update(self) -> None:
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < self.MIN_SECS_TO_REFRESH:
            LOGGER.debug("Only %ds since last refresh.", delta)
            return

        try:
            payload = await self._post_command(I2D_REQUEST_STATUS)
        except AqualinkServiceThrottledException:
            raise
        except AqualinkServiceException:
            self.online = None
            raise

        try:
            self._parse_status_response(payload)
        except AqualinkSystemOfflineException:
            self.online = False
            raise

        self.online = True
        self.last_refresh = int(time.time())

    def _parse_status_response(self, payload: dict[str, Any]) -> None:
        command = payload.get("command") or {}
        if command.get("request") != I2D_REQUEST_STATUS:
            raise AqualinkSystemOfflineException

        hex_response = command.get("response", "")
        try:
            status = parse_status_hex(hex_response)
        except ValueError as exc:
            LOGGER.debug("Bad i2d_robot status hex: %s", exc)
            raise AqualinkSystemOfflineException from exc

        devices: dict[str, dict[str, Any]] = {
            "state_code": {"name": "state_code", "state": status.state_code},
            "state": {"name": "state", "state": status.state_label},
            "error_code": {"name": "error_code", "state": status.error_code},
            "error": {"name": "error", "state": status.error_label},
            "mode_code": {"name": "mode_code", "state": status.mode_code},
            "mode": {"name": "mode", "state": status.mode_label},
            "time_remaining_min": {
                "name": "time_remaining_min",
                "state": status.time_remaining_min,
            },
            "uptime_minutes": {
                "name": "uptime_minutes",
                "state": status.uptime_min,
            },
            "total_hours": {
                "name": "total_hours",
                "state": status.total_hours,
            },
            "hardware_id": {
                "name": "hardware_id",
                "state": status.hardware_id,
            },
            "firmware_id": {
                "name": "firmware_id",
                "state": status.firmware_id,
            },
            "canister_full": {
                "name": "canister_full",
                "state": int(status.canister_full),
            },
            "running": {
                "name": "running",
                "state": int(status.state_code in _ACTIVE_STATE_CODES),
            },
        }

        model_number = self.data.get("id")
        if model_number is not None:
            devices["model_number"] = {
                "name": "model_number",
                "state": model_number,
            }

        for k, v in devices.items():
            if k in self.devices:
                self.devices[k].data.update(v)
            else:
                self.devices[k] = I2dDevice.from_data(self, v)

    # --- write commands ---------------------------------------------------

    async def start_cleaning(self) -> None:
        await self._post_command(I2D_REQUEST_START)

    async def stop_cleaning(self) -> None:
        await self._post_command(I2D_REQUEST_STOP)

    async def return_to_base(self) -> None:
        await self._post_command(I2D_REQUEST_RETURN_TO_BASE)
