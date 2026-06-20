from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import SystemStatus
from iaqualink.systems.zs500.device import Zs500Climate, Zs500TemperatureSensor

from .conftest import Zs500Harness

_REPORTED_CONNECTED: dict[str, Any] = {
    "aws": {"status": "connected"},
    "equipment": {
        "hp_0": {
            "cl": 1,
            "cmprSpd": 62,
            "errorCode": "0",
            "hp": 0,
            "reason": 0,
            "sns_1": {"value": 230},
            "sns_2": {"value": 187},
            "st": 2,
            "state": 2,
            "tsp": 250,
        }
    },
}


def _climate(harness: Zs500Harness) -> Zs500Climate:
    return cast(Zs500Climate, harness.system.devices["climate"])


def _water_temp(harness: Zs500Harness) -> Zs500TemperatureSensor:
    return cast(Zs500TemperatureSensor, harness.system.devices["water_temp"])


class TestZs500SystemRefresh:
    async def test_refresh_parses_devices(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = _REPORTED_CONNECTED
        await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.CONNECTED
        assert set(zs500_harness.system.devices) == {
            "climate",
            "mode",
            "cooling",
            "heating_priority",
            "compressor_speed",
            "standby_reason",
            "error",
            "water_temp",
            "air_temp",
        }
        assert _climate(zs500_harness).target_temperature == "25.0"

    async def test_refresh_missing_aws_status_is_unknown(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = {"equipment": {}}
        await zs500_harness.system.refresh()
        assert zs500_harness.system.status is SystemStatus.UNKNOWN

    async def test_refresh_unrecognized_status_is_unknown(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = {
            "aws": {"status": "something_new"},
            "equipment": {},
        }
        await zs500_harness.system.refresh()
        assert zs500_harness.system.status is SystemStatus.UNKNOWN

    async def test_refresh_no_equipment_keeps_devices_empty(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = {"aws": {"status": "connected"}}
        await zs500_harness.system.refresh()
        assert zs500_harness.system.devices == {}


class TestZs500SystemErrorMapping:
    async def test_get_rejected_401_triggers_reauth_then_succeeds(
        self, zs500_harness: Zs500Harness
    ) -> None:
        shadow = zs500_harness.shadow
        shadow.get_reject_code = 401
        shadow.get_response = _REPORTED_CONNECTED

        async def fake_refresh_auth() -> None:
            shadow.get_reject_code = None  # "new token" works on retry

        with patch.object(
            zs500_harness.system.aqualink,
            "_refresh_auth",
            new=AsyncMock(side_effect=fake_refresh_auth),
        ) as mock_refresh:
            await zs500_harness.system.refresh()
            mock_refresh.assert_awaited_once()

        assert zs500_harness.system.status is SystemStatus.CONNECTED

    async def test_get_rejected_401_twice_raises(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_reject_code = 401

        with (
            patch.object(
                zs500_harness.system.aqualink, "_refresh_auth", new=AsyncMock()
            ),
            pytest.raises(AqualinkServiceUnauthorizedException),
        ):
            await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.DISCONNECTED

    async def test_get_rejected_429_raises_throttled(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_reject_code = 429

        with pytest.raises(AqualinkServiceThrottledException):
            await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.UNKNOWN

    async def test_get_rejected_other_code_raises_service_exception(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_reject_code = 500

        with pytest.raises(AqualinkServiceException):
            await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.DISCONNECTED

    async def test_no_credentials_raises_unauthorized(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.system.aqualink.iot_credentials = None

        with (
            patch.object(
                zs500_harness.system.aqualink, "_refresh_auth", new=AsyncMock()
            ),
            pytest.raises(AqualinkServiceUnauthorizedException),
        ):
            await zs500_harness.system.refresh()


class TestZs500SystemPushUpdates:
    async def test_push_update_applies_without_refresh(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = _REPORTED_CONNECTED
        await zs500_harness.system.refresh()
        assert _climate(zs500_harness).target_temperature == "25.0"

        pushed: dict[str, Any] = {
            "aws": {"status": "connected"},
            "equipment": {
                "hp_0": {
                    "cl": 0,
                    "cmprSpd": 0,
                    "errorCode": "0",
                    "hp": 0,
                    "reason": 0,
                    "sns_1": {"value": 260},
                    "sns_2": {"value": 190},
                    "st": 1,
                    "state": 3,
                    "tsp": 280,
                }
            },
        }
        zs500_harness.shadow.push(pushed)
        await asyncio.sleep(0)

        assert _climate(zs500_harness).target_temperature == "28.0"
        assert _water_temp(zs500_harness).value == "26.0"


class TestZs500SystemSetDesired:
    async def test_set_desired_nests_under_equipment_hp_0(
        self, zs500_harness: Zs500Harness
    ) -> None:
        await zs500_harness.system.set_desired({"cl": 1})

        assert zs500_harness.shadow.published_updates[-1] == {
            "equipment": {"hp_0": {"cl": 1}}
        }


class TestZs500SystemLifecycle:
    async def test_aclose_stops_mqtt_and_clears_state(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = _REPORTED_CONNECTED
        await zs500_harness.system.refresh()
        assert zs500_harness.system._mqtt is not None  # noqa: SLF001

        await zs500_harness.system.aclose()

        assert zs500_harness.mqtt.stop.called
        assert zs500_harness.system._mqtt is None  # noqa: SLF001
        assert zs500_harness.system._shadow is None  # noqa: SLF001

    async def test_aclose_before_connect_is_a_noop(
        self, zs500_harness: Zs500Harness
    ) -> None:
        await zs500_harness.system.aclose()  # must not raise / hang

    async def test_reconnects_after_aclose(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = _REPORTED_CONNECTED
        await zs500_harness.system.refresh()
        await zs500_harness.system.aclose()

        # A fresh refresh after aclose() must reconnect rather than reuse
        # the torn-down connection.
        await zs500_harness.system.refresh()

        assert zs500_harness.system._mqtt is not None  # noqa: SLF001
        assert zs500_harness.system.status is SystemStatus.CONNECTED

    def test_repr(self, zs500_harness: Zs500Harness) -> None:
        r = repr(zs500_harness.system)
        assert zs500_harness.system.serial in r
        assert zs500_harness.system.name in r


class TestZs500SystemConnectionFailures:
    async def test_connect_failure_raises_service_exception(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.connect_control.connect_succeeds = False

        with pytest.raises(AqualinkServiceException):
            await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.DISCONNECTED
        assert zs500_harness.system._mqtt is None  # noqa: SLF001

    async def test_connect_succeeds_after_earlier_failure(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.connect_control.connect_succeeds = False
        with pytest.raises(AqualinkServiceException):
            await zs500_harness.system.refresh()

        zs500_harness.connect_control.connect_succeeds = True
        zs500_harness.shadow.get_response = _REPORTED_CONNECTED
        await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.CONNECTED

    async def test_subscribe_failure_raises_service_exception(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.subscribe_fails = True

        with pytest.raises(AqualinkServiceException):
            await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.DISCONNECTED
        assert zs500_harness.system._mqtt is None  # noqa: SLF001
        assert zs500_harness.mqtt.stop.called

    async def test_operation_timeout_raises_service_exception(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.silent = True  # accept/reject never arrives

        with (
            patch("iaqualink.systems.zs500.system._OPERATION_TIMEOUT", 0.05),
            pytest.raises(AqualinkServiceException),
        ):
            await zs500_harness.system.refresh()

        assert zs500_harness.system.status is SystemStatus.DISCONNECTED


class TestZs500SystemConcurrency:
    """Exercises the _connect_lock guard around _ensure_connected/_disconnect."""

    async def test_concurrent_refresh_calls_share_one_connection(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = _REPORTED_CONNECTED

        await asyncio.gather(
            zs500_harness.system.refresh(),
            zs500_harness.system.refresh(),
        )

        # mqtt5_client_builder is invoked once per connect; concurrent
        # callers must share the single connection rather than racing to
        # build two.
        assert zs500_harness.mqtt.start.call_count == 1

    async def test_aclose_during_in_flight_refresh_does_not_crash(
        self, zs500_harness: Zs500Harness
    ) -> None:
        zs500_harness.shadow.get_response = _REPORTED_CONNECTED

        results = await asyncio.gather(
            zs500_harness.system.refresh(),
            zs500_harness.system.aclose(),
            return_exceptions=True,
        )

        # Either outcome (refresh wins the race and completes, or aclose
        # tears the connection down first and refresh raises a proper
        # AqualinkServiceException) is acceptable — what must never happen
        # is an unguarded AttributeError from a None shadow/mqtt client.
        for result in results:
            if isinstance(result, BaseException):
                assert isinstance(result, AqualinkServiceException)
