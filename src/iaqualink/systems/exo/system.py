from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.exo.device import ExoDevice

_EXO_STATUS_MAP: dict[str, SystemStatus] = {
    "connected": SystemStatus.CONNECTED,
    "online": SystemStatus.ONLINE,
    "offline": SystemStatus.OFFLINE,
    "disconnected": SystemStatus.DISCONNECTED,
    "unknown": SystemStatus.UNKNOWN,
    "service": SystemStatus.SERVICE,
    "firmware_update": SystemStatus.FIRMWARE_UPDATE,
    "in_progress": SystemStatus.IN_PROGRESS,
}

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
        self.temp_unit = "C"  # TODO: check if unit can be changed on panel?

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def send_devices_request(self, **kwargs: Any) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{EXO_DEVICES_URL}/{self.serial}/shadow"
            headers = {"Authorization": self.aqualink.id_token}
            return await self.aqualink.send_request(
                url,
                headers=headers,
                **kwargs,
            )

        return await self._send_with_reauth_retry(do_request)

    async def send_reported_state_request(self) -> httpx.Response:
        return await self.send_devices_request()

    async def send_desired_state_request(
        self, state: dict[str, Any]
    ) -> httpx.Response:
        return await self.send_devices_request(
            method="post", json={"state": {"desired": state}}
        )

    async def _refresh(self) -> None:
        r = await self.send_reported_state_request()
        self._parse_shadow_response(r)

    def _parse_shadow_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug("Shadow response: %s", data)

        raw_aws_status = (
            data.get("state", {})
            .get("reported", {})
            .get("aws", {})
            .get("status")
        )
        if raw_aws_status is None:
            self.status = SystemStatus.UNKNOWN
        elif raw_aws_status == "":
            self.status = SystemStatus.IN_PROGRESS
        else:
            mapped = _EXO_STATUS_MAP.get(raw_aws_status)
            if mapped is None:
                LOGGER.warning(
                    "Unknown aws.status %r for system %s; treating as Unknown.",
                    raw_aws_status,
                    self.serial,
                )
                self.status = SystemStatus.UNKNOWN
            else:
                self.status = mapped

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
        devices.pop("sn", None)
        devices.pop("vr", None)
        devices.pop("version", None)

        # Process the heating control attributes
        if "heating" in data["state"]["reported"]:
            name = "heating"
            attrs = {"name": name}
            attrs.update(data["state"]["reported"]["heating"])
            devices.update({name: attrs})
            # extract heater state into seperate device to maintain homeassistant API
            name = "heater"
            attrs = {"name": name}
            attrs.update(
                {"state": data["state"]["reported"]["heating"]["state"]}
            )
            devices.update({name: attrs})

        LOGGER.debug("devices: %s", devices)

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

    async def set_filter_pump(self, name: str, state: int) -> None:
        r = await self.send_desired_state_request(
            {"equipment": {"swc_0": {name: {"state": state}}}}
        )
        r.raise_for_status()
