from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.i2d.device import IQPumpDevice, IQPumpOpMode

if TYPE_CHECKING:
    import httpx


I2D_CONTROL_URL = "https://r-api.iaqualink.net/v2/devices"

LOGGER = logging.getLogger("iaqualink")


class I2DSystem(AqualinkSystem):
    NAME = "iQPump"

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def _send_command(
        self, command: str, params: str = "", **kwargs: Any
    ) -> httpx.Response:
        url = f"{I2D_CONTROL_URL}/{self.serial}/control.json"
        headers = {
            "Authorization": f"Bearer {self.aqualink.id_token}",
            "api_key": AQUALINK_API_KEY,
        }
        body = {
            "api_key": AQUALINK_API_KEY,
            "authentication_token": self.aqualink._token,
            "user_id": self.aqualink._user_id,
            "command": command,
            "params": params,
        }
        return await self.aqualink.send_request(
            url, method="post", headers=headers, json=body, **kwargs
        )

    async def send_devices_request(self, **kwargs: Any) -> httpx.Response:
        return await self._send_command("/alldata/read", **kwargs)

    async def send_control_command(
        self, command: str, params: str = "", **kwargs: Any
    ) -> httpx.Response:
        return await self._send_command(command, params=params, **kwargs)

    async def update(self) -> None:
        try:
            r = await self.send_devices_request()
        except AqualinkServiceThrottledException:
            raise
        except AqualinkServiceException:
            self.online = None
            raise

        try:
            self._parse_alldata_response(r)
        except AqualinkSystemOfflineException:
            self.online = False
            raise

        self.online = True

    def _parse_alldata_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug(f"Alldata response: {data}")

        # API returns HTTP 200 even for offline devices; detect via body status.
        if data.get("status") == "500":
            msg = data.get("error", {}).get("message", "Device offline.")
            LOGGER.warning(f"System {self.serial} error: {msg}")
            raise AqualinkSystemOfflineException(msg)

        alldata: dict[str, Any] = data["alldata"]
        # Flatten motordata into the top-level dict for cleaner device access.
        motordata = alldata.get("motordata", {})
        device_data = {"name": self.serial, **alldata, **motordata}

        if self.serial in self.devices:
            self.devices[self.serial].data.update(device_data)
        else:
            self.devices[self.serial] = IQPumpDevice(self, device_data)

    # --- Control methods ---

    async def set_opmode(self, mode: IQPumpOpMode) -> None:
        """Set the pump operation mode."""
        if not isinstance(mode, IQPumpOpMode):
            try:
                mode = IQPumpOpMode(mode)
            except ValueError:
                valid = ", ".join(f"{m.value}={m.name}" for m in IQPumpOpMode)
                raise AqualinkInvalidParameterException(
                    f"{mode!r} is not a valid operation mode. Valid: {valid}"
                )
        r = await self.send_control_command(
            "/opmode/write", f"value={mode.value}"
        )
        r.raise_for_status()

    async def set_custom_speed(self, rpm: int) -> None:
        r = await self.send_control_command(
            "/customspeedrpm/write", f"value={rpm}"
        )
        r.raise_for_status()

    async def set_freeze_protect(self, enable: bool) -> None:
        r = await self.send_control_command(
            "/freezeprotectenable/write", f"value={int(enable)}"
        )
        r.raise_for_status()

    async def set_freeze_protect_rpm(self, rpm: int) -> None:
        r = await self.send_control_command(
            "/freezeprotectrpm/write", f"value={rpm}"
        )
        r.raise_for_status()
