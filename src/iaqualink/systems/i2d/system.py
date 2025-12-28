import httpx
import json
import logging
from typing import Optional, TYPE_CHECKING

from iaqualink.system import AqualinkSystem
from iaqualink.const import (
    AQUALINK_API_KEY,
)
from iaqualink.exception import (
    AqualinkSystemOfflineException,
    AqualinkServiceException,
)
from iaqualink.typing import Payload

from .device import AquaLinkIQPump


if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

AQUALINK_HTTP_HEADERS = {
    "user-agent": "okhttp/3.14.7",
    "content-type": "application/json",
}
IAQUA_DEVICE_URL = "https://r-api.iaqualink.net/v2/devices/"

LOGGER = logging.getLogger("iaqualink")


class I2DSystem(AqualinkSystem):
    NAME = "i2d"

    def __init__(self, aqualink: "AqualinkClient", data: Payload):
        super().__init__(aqualink, data)

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def update(self) -> None:
        resp = await self._send_device_request()
        data: dict = resp.json()
        LOGGER.debug(f"i2d response: {data}")

        if data["status"] == "500":
            if data["error"]["message"] == "Device offline.":
                LOGGER.warning(f"Status for system {self.serial} is Offline.")
                raise AqualinkSystemOfflineException
            else:
                raise AqualinkServiceException
        self.devices = {self.serial: AquaLinkIQPump(self, data["alldata"])}

    async def _send_device_request(
        self,
        params: Optional[Payload] = None,
    ) -> httpx.Response:
        if not params:
            params = {}

        r = await self.aqualink._send_login_request()
        id_token = r.json()["userPoolOAuth"]["IdToken"]

        url = f"{IAQUA_DEVICE_URL}{self.serial}/control.json"
        headers = {"api_key": AQUALINK_API_KEY, "Authorization": id_token}
        headers.update(**AQUALINK_HTTP_HEADERS)
        data = json.dumps(
            {"user_id": self.aqualink._user_id, "command": "/alldata/read"}
        )
        return await self.aqualink._client.post(url, headers=headers, data=data)
