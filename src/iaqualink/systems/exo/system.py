from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from iaqualink.const import MIN_SECS_TO_REFRESH
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.exo.device import ExoDevice

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

EXO_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"


LOGGER = logging.getLogger("iaqualink")


class ExoSystem(AqualinkSystem):
    NAME = "exo"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)
        # This lives in the parent class but mypy complains.
        self.last_refresh: int = 0

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f'{self.__class__.__name__}({" ".join(attrs)})'

    async def send_devices_request(self, **kwargs: Any) -> httpx.Response:
        url = f"{EXO_DEVICES_URL}/{self.serial}/shadow"
        headers = {"Authorization": self.aqualink.id_token}

        try:
            r = await self.aqualink.send_request(url, headers=headers, **kwargs)
        except AqualinkServiceUnauthorizedException:
            # token expired so refresh the token and try again
            await self.aqualink.login()
            headers = {"Authorization": self.aqualink.id_token}
            r = await self.aqualink.send_request(url, headers=headers, **kwargs)

        return r

    async def send_reported_state_request(self) -> httpx.Response:
        return await self.send_devices_request()

    async def send_desired_state_request(
        self, state: dict[str, Any]
    ) -> httpx.Response:
        return await self.send_devices_request(
            method="post", json={"state": {"desired": state}}
        )

    async def update(self) -> None:
        # Be nice to Aqualink servers since we rely on polling.
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < MIN_SECS_TO_REFRESH:
            LOGGER.debug(f"Only {delta}s since last refresh.")
            return

        try:
            r = await self.send_reported_state_request()
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

        LOGGER.debug(f"Shadow response: {data}")

        devices = {}

        # Process the chlorinator attributes[equipmen]
        # Make the data a bit flatter.
        root = data["state"]["reported"]["equipment"]["swc_0"]
        for name, state in root.items():
            attrs = {"name": name}
            if isinstance(state, dict):
                attrs.update(state)
            else:
                attrs.update({"state": state})
            devices.update({name: attrs})

        # Remove those values, they're not handled properly.
        devices.pop("boost_time", None)
        devices.pop("vsp_speed", None)

        # Process the heating control attributes
        if "heating" in data["state"]["reported"]:
            name = "heating"
            attrs = {"name": name}
            attrs.update(data["state"]["reported"]["heating"])
            devices.update({name: attrs})

        LOGGER.debug(f"devices: {devices}")

        for k, v in devices.items():
            if k in self.devices:
                for dk, dv in v.items():
                    self.devices[k].data[dk] = dv
            else:
                self.devices[k] = ExoDevice.from_data(self, v)

    async def set_heating(self, name: str, state: int) -> None:
        r = await self.send_desired_state_request({"heating": {name: state}})
        r.raise_for_status()

    async def set_aux(self, aux: str, state: int) -> None:
        r = await self.send_desired_state_request(
            {"equipment": {"swc_0": {aux: {"state": state}}}}
        )
        r.raise_for_status()

    async def set_toggle(self, name: str, state: int) -> None:
        r = await self.send_desired_state_request(
            {"equipment": {"swc_0": {name: state}}}
        )
        r.raise_for_status()
