from __future__ import annotations

import logging
from enum import IntEnum, unique
from typing import TYPE_CHECKING, cast

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkClimate,
    AqualinkDevice,
    AqualinkSelect,
    AqualinkSensor,
    AqualinkSwitch,
)

if TYPE_CHECKING:
    from iaqualink.systems.hpm.system import HpmSystem
    from iaqualink.typing import DeviceData

LOGGER = logging.getLogger("iaqualink.systems.hpm")

# The API reports no set-point bounds for this system type, unlike exo's
# sp_min/sp_max. These are a permissive placeholder, not a device limit.
HPM_TEMP_CELSIUS_LOW = 15
HPM_TEMP_CELSIUS_HIGH = 40


@unique
class HpmOperatingState(IntEnum):
    """Values of the `status` field."""

    OFF = 0
    STANDBY = 1
    HEATING = 2
    COOLING = 3


@unique
class HpmStandbyReason(IntEnum):
    """Values of the `reason` field, which qualifies `status`.

    Only NONE, NO_FLOW, TEMP_BUFFER and CYCLE_TRANSITION were observed on
    real hardware; the rest are documented but unverified. See the
    protocol reference for per-value confidence.
    """

    NONE = 0
    NO_FLOW = 1
    TEMP_OUT_OF_RANGE = 2
    TEMP_BUFFER = 3
    COOLING_DISABLED = 4
    DEFROSTING = 5
    CYCLE_TRANSITION = 6
    REMOTE_CONTACT_OPEN = 7
    COMPRESSOR_PROTECTION_DELAY = 8


@unique
class HpmPerformanceMode(IntEnum):
    """Values of the `st` field. SMART is unverified; see the reference."""

    BOOST = 0
    SILENT = 1
    SMART = 2


class HpmDevice(AqualinkDevice):
    def __init__(self, system: HpmSystem, data: DeviceData):
        super().__init__(system, data)

        # This silences mypy errors due to AqualinkDevice type annotations.
        self.system: HpmSystem = system

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def manufacturer(self) -> str:
        # Firmware OTA URLs observed on the wire are hosted under
        # /fluidra-ota-prod/hpm/ — Fluidra is Zodiac/Jandy's parent brand.
        return "Fluidra"

    @property
    def model(self) -> str:
        return "Heat Pump Module"

    @classmethod
    def from_data(cls, system: HpmSystem, data: DeviceData) -> HpmDevice:
        class_: type[HpmDevice]

        if data["name"] == "heatpump":
            class_ = HpmHeatPump
        elif data["name"] == "mode":
            class_ = HpmMode
        elif data["name"] == "cooling_priority":
            class_ = HpmCoolingPriority
        elif data["name"] == "status":
            class_ = HpmOperatingStatusSensor
        elif data["name"] == "reason":
            class_ = HpmStandbyReasonSensor
        elif data["name"] == "water_temp":
            class_ = HpmWaterTemperature
        elif data["name"] == "air_temp":
            class_ = HpmAirTemperature
        elif data["name"] == "water_flow":
            class_ = HpmWaterFlow
        else:
            class_ = HpmAttributeSensor

        return class_(system, data)


class HpmAttributeSensor(HpmDevice, AqualinkSensor):
    """Fallback for a device key with no dedicated class.

    `_parse_shadow_response` only ever builds the keys handled above, so
    this is unreachable through a refresh; it keeps `from_data` total for
    direct callers.
    """

    @property
    def value(self) -> str | None:
        val = self.data.get("state")
        return str(val) if val is not None else None


class HpmHeatPump(HpmDevice, AqualinkClimate):
    """The heat pump itself: on/off (`state`) plus set point (`tsp`).

    The finer-grained `status` (off/standby/heating/cooling) is a separate
    sensor rather than folded in here, since AqualinkClimate has no
    hvac-mode concept beyond is_on.
    """

    @property
    def is_on(self) -> bool:
        state = self.data.get("state")
        return state is not None and int(state) == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_state(1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_state(0)

    @property
    def temperature_unit(self) -> str:
        # No unit field exists in this system's payload; all observed
        # values were Celsius.
        return "C"

    @property
    def current_temperature(self) -> str | None:
        water = cast(
            "HpmProbeSensor | None", self.system.devices.get("water_temp")
        )
        if water is None or water.value is None:
            return None
        return str(water.value)

    @property
    def target_temperature(self) -> str | None:
        tsp = self.data.get("tsp")
        return str(tsp) if tsp is not None else None

    @property
    def min_temp(self) -> int:
        return HPM_TEMP_CELSIUS_LOW

    @property
    def max_temp(self) -> int:
        return HPM_TEMP_CELSIUS_HIGH

    async def _set_temperature(self, temperature: int) -> None:
        await self.system.set_setpoint(temperature)


class HpmMode(HpmDevice, AqualinkSelect):
    """Performance mode picker (`st`)."""

    @property
    def current_option(self) -> str | None:
        st = self.data.get("st")
        if st is None:
            return None
        try:
            return HpmPerformanceMode(int(st)).name.lower()
        except ValueError:
            return None

    @property
    def options(self) -> list[str]:
        return [m.name.lower() for m in HpmPerformanceMode]

    async def _select_option(self, option: str) -> None:
        await self.system.set_mode(HpmPerformanceMode[option.upper()].value)


class HpmCoolingPriority(HpmDevice, AqualinkSwitch):
    """Whether the unit is allowed to cool (`cl`).

    Shown as "Allow Cool Mode" in the manufacturer app.
    """

    @property
    def is_on(self) -> bool:
        cl = self.data.get("cl")
        return cl is not None and int(cl) == 1

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.system.set_cooling_priority(1)

    async def turn_off(self) -> None:
        if self.is_on:
            await self.system.set_cooling_priority(0)


# `hp` ("Heating Priority") is intentionally not modeled — it needs
# dry-contact hardware no test unit had, so it could not be verified.
# See the protocol reference.


class HpmOperatingStatusSensor(HpmDevice, AqualinkSensor):
    """Diagnostic sensor for the `status` field. See `HpmOperatingState`."""

    @property
    def entity_category(self) -> str | None:
        return "diagnostic"

    @property
    def value(self) -> int | None:
        status = self.data.get("status")
        return int(status) if status is not None else None

    @property
    def value_enum(self) -> type[IntEnum] | None:
        return HpmOperatingState


class HpmStandbyReasonSensor(HpmDevice, AqualinkSensor):
    """Diagnostic sensor for the `reason` field. See `HpmStandbyReason`."""

    @property
    def entity_category(self) -> str | None:
        return "diagnostic"

    @property
    def value(self) -> int | None:
        reason = self.data.get("reason")
        return int(reason) if reason is not None else None

    @property
    def value_enum(self) -> type[IntEnum] | None:
        return HpmStandbyReason


class HpmProbeSensor(HpmDevice, AqualinkSensor):
    """Base for the temperature probes nested in hp_0 (sns_1, sns_2).

    Each probe reports its own `state`, which tracks whether the probe
    itself is wired up — unrelated to the system's cloud connectivity.
    A probe that isn't connected reports no value.
    """

    @property
    def device_class(self) -> str | None:
        return "temperature"

    @property
    def state_class(self) -> str | None:
        return "measurement"

    @property
    def unit_of_measurement(self) -> str | None:
        return "°C"

    @property
    def value(self) -> float | None:
        if self.data.get("state") != "connected":
            return None
        value = self.data.get("value")
        return float(value) if value is not None else None


class HpmWaterTemperature(HpmProbeSensor):
    """Water temperature probe (`sns_1`)."""


class HpmAirTemperature(HpmProbeSensor):
    """Air temperature probe (`sns_2`)."""


class HpmWaterFlow(HpmDevice, AqualinkBinarySensor):
    """Whether the unit detects water flow (`wf`)."""

    @property
    def is_on(self) -> bool:
        wf = self.data.get("wf")
        return wf is not None and int(wf) == 1
