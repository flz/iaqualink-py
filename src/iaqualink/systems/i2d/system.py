from __future__ import annotations

import json
import logging
import os
from typing import Any, NamedTuple

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.i2d.device import (
    I2dNumber,
    I2dSensor,
    I2dSwitch,
    I2dPump,
    _RPM_HARDWARE_MIN_DEFAULT,
    _RPM_HARDWARE_MIN_SVRS,
    _RPM_HARDWARE_MAX,
)

import httpx


I2D_CONTROL_URL = "https://r-api.iaqualink.net/v2/devices"

_SVRS_PRODUCT_IDS: frozenset[str] = frozenset({"0F", "18"})

LOGGER = logging.getLogger("iaqualink")

# Values captured from a real iQPump device. Some period/timer fields (e.g.
# customspeedtimer=60, quickcleanperiod=8) fall outside the step-aligned ranges
# enforced on write — that is expected; read values reflect device state and are
# not required to satisfy write constraints.
_MOCK_ALLDATA = {
    "alldata": {
        "motordata": {
            "speed": "1500",
            "power": "180",
            "temperature": "110",
            "productid": "1A",
            "horsepower": "1.65",
            "horsepowercode": "0A",
            "updateprogress": "0",
        },
        "wifistatus": {"state": "connected", "ssid": "MyNetwork"},
        "opmode": "0",
        "runstate": "on",
        "fwversion": "1.5.2",
        "RS485fwversion": "1.0.0",
        "localtime": "12:34",
        "timezone": "America/Los_Angeles",
        "utctime": "1700000000",
        "hotspottimer": "5",
        "busstatus": "0",
        "updateprogress": "0",
        "updateflag": "0",
        "serialnumber": "ABC123",
        "rpmtarget": "1500",
        "globalrpmmin": "600",
        "globalrpmmax": "3450",
        "customspeedrpm": "1500",
        "customspeedtimer": "60",
        "quickcleanrpm": "3450",
        "quickcleanperiod": "8",
        "quickcleantimer": "0",
        "countdownrpm": "1500",
        "countdownperiod": "30",
        "countdowntimer": "0",
        "timeoutperiod": "10",
        "timeouttimer": "0",
        "primingrpm": "3450",
        "primingperiod": "3",
        "freezeprotectenable": "1",
        "freezeprotectrpm": "1000",
        "freezeprotectperiod": "30",
        "freezeprotectsetpointc": "4",
        "freezeprotectstatus": "0",
        "demandvisible": "0",
        "faultvisible": "0",
        "relayK1Rpm": "1500",
        "relayK2Rpm": "1200",
    },
    "requestID": "mock",
}


class NumberSpec(NamedTuple):
    key: str
    label: str
    min_value: float | None = None
    max_value: float | None = None
    min_key: str | None = None
    max_key: str | None = None
    step: float = 1.0
    unit: str = ""


# Exactly one of (min_value, min_key) and one of (max_value, max_key) must be set.
# step enforces must-be-multiple-of-step validation via AqualinkNumber.set_value.
_NUMBER_SPECS: list[NumberSpec] = [
    # Hardware RPM limits — _rpmhwmin injected at parse time from productid
    NumberSpec(
        "globalrpmmin",
        "Global RPM Min",
        min_key="_rpmhwmin",
        max_key="globalrpmmax",
        step=25,
        unit="RPM",
    ),
    NumberSpec(
        "globalrpmmax",
        "Global RPM Max",
        min_key="globalrpmmin",
        max_value=_RPM_HARDWARE_MAX,
        step=25,
        unit="RPM",
    ),
    # RPM settings — bounds read live from globalrpmmin/globalrpmmax
    NumberSpec(
        "customspeedrpm",
        "Custom Speed RPM",
        min_key="globalrpmmin",
        max_key="globalrpmmax",
        step=25,
        unit="RPM",
    ),
    NumberSpec(
        "primingrpm",
        "Priming RPM",
        min_key="globalrpmmin",
        max_key="globalrpmmax",
        step=25,
        unit="RPM",
    ),
    NumberSpec(
        "quickcleanrpm",
        "Quick Clean RPM",
        min_key="globalrpmmin",
        max_key="globalrpmmax",
        step=25,
        unit="RPM",
    ),
    NumberSpec(
        "freezeprotectrpm",
        "Freeze Protect RPM",
        min_key="globalrpmmin",
        max_key="globalrpmmax",
        step=25,
        unit="RPM",
    ),
    NumberSpec(
        "countdownrpm",
        "Countdown RPM",
        min_key="globalrpmmin",
        max_key="globalrpmmax",
        step=25,
        unit="RPM",
    ),
    # Temperature — API value is always °C (min=3, max=7, step=1).
    # The app displays in °F (min=37, max=45, step=2) and converts before writing.
    # If Fahrenheit support is added later, apply round(f_to_c(value)) before set_value.
    NumberSpec(
        "freezeprotectsetpointc",
        "Freeze Protect Setpoint",
        min_value=3,
        max_value=7,
        unit="°C",
    ),
    # Period / timer settings (values in seconds, step-aligned)
    NumberSpec(
        "customspeedtimer",
        "Custom Speed Timer",
        min_value=300,
        max_value=3600,
        step=300,
        unit="s",
    ),
    NumberSpec(
        "primingperiod",
        "Priming Period",
        min_value=0,
        max_value=300,
        step=60,
        unit="s",
    ),
    NumberSpec(
        "quickcleanperiod",
        "Quick Clean Period",
        min_value=300,
        max_value=3600,
        step=300,
        unit="s",
    ),
    NumberSpec(
        "freezeprotectperiod",
        "Freeze Protect Period",
        min_value=0,
        max_value=28800,
        step=1800,
        unit="s",
    ),
    NumberSpec(
        "countdownperiod",
        "Countdown Period",
        min_value=3600,
        max_value=86400,
        step=3600,
        unit="s",
    ),
    NumberSpec(
        "timeoutperiod",
        "Timeout Period",
        min_value=3600,
        max_value=86400,
        step=3600,
        unit="s",
    ),
]

_SWITCH_SPECS: list[tuple[str, str]] = [
    ("freezeprotectenable", "Freeze Protection"),
]

# (key, label, unit) — read-only telemetry from motordata (flattened into alldata)
_SENSOR_SPECS: list[tuple[str, str, str]] = [
    ("speed", "Motor Speed", "RPM"),
    ("power", "Motor Power", "W"),
    ("temperature", "Motor Temperature", "°F"),
    ("horsepower", "Horsepower", "HP"),
]


class I2dSystem(AqualinkSystem):
    NAME = "i2d"

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def send_control_command(
        self, command: str, params: str = "", **kwargs: Any
    ) -> httpx.Response:
        if os.environ.get("IAQUALINK_I2D_MOCK"):
            LOGGER.debug("i2d mock: returning canned response for %s", command)
            return httpx.Response(
                200, content=json.dumps(_MOCK_ALLDATA).encode()
            )

        async def do_request() -> httpx.Response:
            url = f"{I2D_CONTROL_URL}/{self.serial}/control.json"
            headers = {
                "Authorization": self.aqualink.id_token,
                "api_key": AQUALINK_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            body = {
                "user_id": self.aqualink.user_id,
                "command": command,
                "params": params,
            }
            LOGGER.debug("i2d request: POST %s body=%s", url, body)
            return await self.aqualink.send_request(
                url, method="post", headers=headers, json=body, **kwargs
            )

        return await self._send_with_reauth_retry(do_request)

    async def _refresh(self) -> None:
        r = await self.send_control_command("/alldata/read")
        self._parse_alldata_response(r)

    def _parse_alldata_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("Alldata response: %s", data)

        # API returns HTTP 200 even when device is unreachable; body carries status=500.
        if data.get("status") == "500":
            msg = data.get("error", {}).get("message", "Device offline.")
            LOGGER.warning("System %s error: %s", self.serial, msg)
            self.status = SystemStatus.DISCONNECTED
            return

        alldata: dict[str, Any] = data["alldata"]

        opmode = alldata.get("opmode")
        if opmode is not None:
            self.status = (
                SystemStatus.CONNECTED
                if int(opmode) <= 3
                else SystemStatus.SERVICE
            )
        else:
            updateprogress = alldata.get("updateprogress")
            if updateprogress is not None and updateprogress not in (
                "0",
                "0/0",
            ):
                self.status = SystemStatus.FIRMWARE_UPDATE
            else:
                self.status = SystemStatus.UNKNOWN
        # Flatten motordata into the top-level dict for cleaner device access.
        motordata = alldata.get("motordata", {})
        device_data = {"name": self.serial, **alldata, **motordata}
        # Inject hardware RPM floor so I2dNumber can use it as a live min_key.
        device_data["_rpmhwmin"] = str(
            _RPM_HARDWARE_MIN_SVRS
            if device_data.get("productid") in _SVRS_PRODUCT_IDS
            else _RPM_HARDWARE_MIN_DEFAULT
        )

        if self.serial in self.devices:
            self.devices[self.serial].data.update(device_data)
        else:
            self.devices[self.serial] = I2dPump(self, device_data)

        # All number and switch sub-devices share the pump's data dict so they
        # see live values after each update() without a separate parse step.
        shared_data = self.devices[self.serial].data

        for spec in _NUMBER_SPECS:
            if spec.key not in self.devices:
                self.devices[spec.key] = I2dNumber(
                    self,
                    shared_data,
                    key=spec.key,
                    label=spec.label,
                    min_value=spec.min_value,
                    max_value=spec.max_value,
                    min_key=spec.min_key,
                    max_key=spec.max_key,
                    step=spec.step,
                    unit=spec.unit,
                )

        for key, label in _SWITCH_SPECS:
            if key not in self.devices:
                self.devices[key] = I2dSwitch(
                    self, shared_data, key=key, label=label
                )

        for key, label, unit in _SENSOR_SPECS:
            if key not in self.devices:
                self.devices[key] = I2dSensor(
                    self, shared_data, key=key, label=label, unit=unit
                )
