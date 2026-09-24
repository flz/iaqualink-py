from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.hpm.device import HpmDevice
from iaqualink.utils.redact import mask_serial, redact_value

_HPM_STATUS_MAP: dict[str, SystemStatus] = {
    "connected": SystemStatus.CONNECTED,
    "online": SystemStatus.ONLINE,
    "offline": SystemStatus.OFFLINE,
    "disconnected": SystemStatus.DISCONNECTED,
    "unknown": SystemStatus.UNKNOWN,
    "service": SystemStatus.SERVICE,
    "firmware_update": SystemStatus.FIRMWARE_UPDATE,
}

if TYPE_CHECKING:
    import httpx


HPM_DEVICES_URL = "https://prod.zodiac-io.com/devices/v1"

LOGGER = logging.getLogger("iaqualink.systems.hpm")


class HpmSystem(AqualinkSystem):
    """A standalone heat pump, with no pool controller attached.

    Not the HPM sub-device that pairs with an iQ20 (`iaqua`) controller:
    this is a heat pump WiFi module that owns its own shadow, using the
    same AWS IoT shadow REST mechanism as `exo`.

    Writes land in `state.desired` immediately, but the unit can take
    upwards of 15 seconds to apply one and report it back, so a refresh
    issued straight after a write will usually still read the old value.
    """

    NAME = "hpm"

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def send_devices_request(self, **kwargs: Any) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{HPM_DEVICES_URL}/{self.serial}/shadow"
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
        LOGGER.debug("Shadow body: %s", redact_value(data))

        raw_aws_status = (
            data.get("state", {})
            .get("reported", {})
            .get("aws", {})
            .get("status")
        )
        if raw_aws_status in (None, ""):
            self.status = SystemStatus.UNKNOWN
        else:
            mapped = _HPM_STATUS_MAP.get(raw_aws_status)
            if mapped is None:
                LOGGER.warning(
                    "Unknown aws.status %r for system %s (%s); treating as Unknown.",
                    raw_aws_status,
                    mask_serial(self.serial),
                    self.type,
                )
                self.status = SystemStatus.UNKNOWN
            else:
                self.status = mapped
        LOGGER.debug(
            "Shadow parsed: serial=%s status=%s",
            mask_serial(self.serial),
            self.status.name,
        )

        reported = data.get("state", {}).get("reported", {})

        # Everything lives under equipment.hp_0 (single heat pump unit,
        # index 0 — no evidence multi-unit hpm accounts exist).
        hp_zero: dict[str, Any] = reported.get("equipment", {}).get("hp_0", {})
        if not hp_zero:
            LOGGER.debug(
                "No hp_0 equipment block for system %s",
                mask_serial(self.serial),
            )
            return

        def pick(*keys: str) -> dict[str, Any]:
            return {k: hp_zero[k] for k in keys if k in hp_zero}

        # Each device carries only the hp_0 keys it reads. A device whose
        # keys are all absent is skipped rather than created empty, so a
        # field the unit doesn't report doesn't surface as a device stuck
        # at a default.
        candidates: dict[str, dict[str, Any]] = {
            "heatpump": pick("state", "tsp"),
            "mode": pick("st"),
            "cooling_priority": pick("cl"),
            "status": pick("status"),
            "reason": pick("reason"),
            "water_flow": pick("wf"),
        }

        for sns, name in (("sns_1", "water_temp"), ("sns_2", "air_temp")):
            probe = hp_zero.get(sns)
            if isinstance(probe, dict):
                candidates[name] = dict(probe)

        devices = {k: v for k, v in candidates.items() if v}

        LOGGER.debug(
            "HPM devices parsed: serial=%s count=%d",
            mask_serial(self.serial),
            len(devices),
        )

        for name, fields in devices.items():
            attrs = {**fields, "name": name}
            if name in self.devices:
                self.devices[name].data = attrs
            else:
                self.devices[name] = HpmDevice.from_data(self, attrs)

    async def set_state(self, state: int) -> None:
        r = await self.send_desired_state_request(
            {"equipment": {"hp_0": {"state": state}}}
        )
        r.raise_for_status()

    async def set_setpoint(self, temperature: float) -> None:
        r = await self.send_desired_state_request(
            {"equipment": {"hp_0": {"tsp": temperature}}}
        )
        r.raise_for_status()

    async def set_mode(self, mode: int) -> None:
        r = await self.send_desired_state_request(
            {"equipment": {"hp_0": {"st": mode}}}
        )
        r.raise_for_status()

    async def set_cooling_priority(self, enabled: int) -> None:
        r = await self.send_desired_state_request(
            {"equipment": {"hp_0": {"cl": enabled}}}
        )
        r.raise_for_status()

    # There is deliberately no set_heating_priority() for `hp_0.hp`; see
    # device.py.
