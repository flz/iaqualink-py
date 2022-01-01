from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Dict

import httpx

from iaqualink.const import MIN_SECS_TO_REFRESH
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.exo.device import ExoDevice
from iaqualink.typing import Payload

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

EXO_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"


LOGGER = logging.getLogger("iaqualink")


class ExoSystem(AqualinkSystem):
    NAME = "exo"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return f'{self.__class__.__name__}({" ".join(attrs)})'

    async def send_devices_request(self, **kwargs: Any) -> httpx.Response:
        url = f"{EXO_DEVICES_URL}/{self.serial}/shadow"
        headers = {"Authorization": self.aqualink.id_token}
        return await self.aqualink.send_request(url, headers=headers, **kwargs)

    async def send_reported_state_request(self) -> httpx.Response:
        return await self.send_devices_request()

    async def send_desired_state_request(
        self, state: Dict[str, Any]
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

        if "vsp_speed" in devices:
            del devices["vsp_speed"]  # temp remove until can handle dictionary

        # Process the heating control attributes
        if "heating" in data["state"]["reported"]:
            name = "heating"
            attrs = {"name": name}
            attrs.update(data["state"]["reported"]["heating"])
            devices.update({name: attrs})

        LOGGER.debug(f"devices: {devices}")
        print(devices)

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
