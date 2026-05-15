from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.i2d.device import (
    I2dBinaryState,
    I2dNumber,
    I2dSensor,
    I2dSwitch,
    I2dPump,
    I2dOpMode,
    I2dRpmBoundNumber,
    _SETTABLE_OPMODE_SET,
)

import httpx

if TYPE_CHECKING:
    pass


I2D_CONTROL_URL = "https://r-api.iaqualink.net/v2/devices"

LOGGER = logging.getLogger("iaqualink")

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

# (key, label, min, max, min_key, max_key, step, unit)
# Exactly one of (min_value, min_key) and one of (max_value, max_key) must be set.
# step > 1 enforces must-be-multiple-of-step validation in I2dNumber.set_value.
_NUMBER_SPECS: list[
    tuple[
        str, str, float | None, float | None, str | None, str | None, float, str
    ]
] = [
    # RPM settings — bounds read live from globalrpmmin/globalrpmmax
    (
        "customspeedrpm",
        "Custom Speed RPM",
        None,
        None,
        "globalrpmmin",
        "globalrpmmax",
        25,
        "RPM",
    ),
    (
        "primingrpm",
        "Priming RPM",
        None,
        None,
        "globalrpmmin",
        "globalrpmmax",
        25,
        "RPM",
    ),
    (
        "quickcleanrpm",
        "Quick Clean RPM",
        None,
        None,
        "globalrpmmin",
        "globalrpmmax",
        25,
        "RPM",
    ),
    (
        "freezeprotectrpm",
        "Freeze Protect RPM",
        None,
        None,
        "globalrpmmin",
        "globalrpmmax",
        25,
        "RPM",
    ),
    (
        "countdownrpm",
        "Countdown RPM",
        None,
        None,
        "globalrpmmin",
        "globalrpmmax",
        25,
        "RPM",
    ),
    # Temperature
    (
        "freezeprotectsetpointc",
        "Freeze Protect Setpoint",
        0,
        15,
        None,
        None,
        1,
        "°C",
    ),
    # Period / timer settings (values in seconds, step-aligned)
    ("customspeedtimer", "Custom Speed Timer", 300, 3600, None, None, 300, "s"),
    ("primingperiod", "Priming Period", 0, 300, None, None, 60, "s"),
    ("quickcleanperiod", "Quick Clean Period", 300, 3600, None, None, 300, "s"),
    (
        "freezeprotectperiod",
        "Freeze Protect Period",
        0,
        28800,
        None,
        None,
        1800,
        "s",
    ),
    ("countdownperiod", "Countdown Period", 3600, 86400, None, None, 3600, "s"),
    ("timeoutperiod", "Timeout Period", 3600, 86400, None, None, 3600, "s"),
]

# globalrpmmin/globalrpmmax use hardware-specific bounds, multiples of 25, and
# enforce the invariant that min < max.
# (key, label, cross_key, value_lt_cross)
_RPM_BOUND_SPECS: list[tuple[str, str, str, bool]] = [
    ("globalrpmmin", "Global RPM Min", "globalrpmmax", True),
    ("globalrpmmax", "Global RPM Max", "globalrpmmin", False),
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

    async def _send_command(
        self, command: str, params: str = "", **kwargs: Any
    ) -> httpx.Response:
        if os.environ.get("IAQUALINK_I2D_MOCK"):
            LOGGER.debug("i2d mock: returning canned response for %s", command)
            return httpx.Response(
                200, content=json.dumps(_MOCK_ALLDATA).encode()
            )
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
        LOGGER.debug(
            "i2d request: POST %s headers=%s body=%s", url, headers, body
        )
        return await self.aqualink.send_request(
            url, method="post", headers=headers, json=body, **kwargs
        )

    async def send_control_command(
        self, command: str, params: str = "", **kwargs: Any
    ) -> httpx.Response:
        return await self._send_command(command, params=params, **kwargs)

    async def update(self) -> None:
        try:
            r = await self.send_control_command("/alldata/read")
        except AqualinkServiceThrottledException:
            raise
        except AqualinkServiceException as e:
            if e.response is not None:
                try:
                    self._parse_alldata_response(e.response)
                except AqualinkSystemOfflineException:
                    self.status = SystemStatus.OFFLINE
                    raise
            self.status = SystemStatus.UNKNOWN
            raise

        try:
            self._parse_alldata_response(r)
        except AqualinkSystemOfflineException:
            self.status = SystemStatus.OFFLINE
            raise

        self.status = SystemStatus.ONLINE

    def _parse_alldata_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("Alldata response: %s", data)

        # API returns HTTP 200 even for offline devices; detect via body status.
        if data.get("status") == "500":
            msg = data.get("error", {}).get("message", "Device offline.")
            LOGGER.warning("System %s error: %s", self.serial, msg)
            raise AqualinkSystemOfflineException(msg)

        alldata: dict[str, Any] = data["alldata"]
        # Flatten motordata into the top-level dict for cleaner device access.
        motordata = alldata.get("motordata", {})
        device_data = {"name": self.serial, **alldata, **motordata}

        if self.serial in self.devices:
            self.devices[self.serial].data.update(device_data)
        else:
            self.devices[self.serial] = I2dPump(self, device_data)

        # All number and switch sub-devices share the pump's data dict so they
        # see live values after each update() without a separate parse step.
        shared_data = self.devices[self.serial].data

        for key, label, mn, mx, mn_key, mx_key, step, unit in _NUMBER_SPECS:
            if key not in self.devices:
                self.devices[key] = I2dNumber(
                    self,
                    shared_data,
                    key=key,
                    label=label,
                    min_value=mn,
                    max_value=mx,
                    min_key=mn_key,
                    max_key=mx_key,
                    step=step,
                    unit=unit,
                )

        for key, label, cross_key, value_lt_cross in _RPM_BOUND_SPECS:
            if key not in self.devices:
                self.devices[key] = I2dRpmBoundNumber(
                    self,
                    shared_data,
                    key=key,
                    label=label,
                    cross_key=cross_key,
                    value_lt_cross=value_lt_cross,
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

    # --- Control methods ---

    async def set_opmode(self, mode: I2dOpMode) -> None:
        if not isinstance(mode, I2dOpMode):
            try:
                mode = I2dOpMode(mode)
            except ValueError:
                valid = ", ".join(
                    f"{m.value}={m.name}" for m in _SETTABLE_OPMODE_SET
                )
                raise AqualinkInvalidParameterException(
                    f"{mode!r} is not a valid operation mode. Valid: {valid}"
                )
        if mode not in _SETTABLE_OPMODE_SET:
            valid = ", ".join(m.name for m in _SETTABLE_OPMODE_SET)
            raise AqualinkInvalidParameterException(
                f"{mode.name} is not user-settable. Valid: {valid}"
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
        state = I2dBinaryState.ON if enable else I2dBinaryState.OFF
        r = await self.send_control_command(
            "/freezeprotectenable/write", f"value={state}"
        )
        r.raise_for_status()

    async def set_freeze_protect_rpm(self, rpm: int) -> None:
        r = await self.send_control_command(
            "/freezeprotectrpm/write", f"value={rpm}"
        )
        r.raise_for_status()
