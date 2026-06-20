from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from awscrt import auth, mqtt5
from awsiot import iotshadow, mqtt5_client_builder

from iaqualink.const import AQUALINK_AWS_IOT_ENDPOINT, AQUALINK_AWS_IOT_REGION
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.zs500.device import Zs500Device
from iaqualink.utils.redact import mask_serial, redact_value

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

LOGGER = logging.getLogger("iaqualink.systems.zs500")

T = TypeVar("T")

# aws.status wire values for ZS500 were not independently confirmed in the
# reference source (see docs/reference/systems/zs500.md). Reusing eXO's
# mapping table since both device types share the same shadow "aws" block —
# see "Deltas vs Protocol Reference" in the implementation notes.
_ZS500_STATUS_MAP: dict[str, SystemStatus] = {
    "connected": SystemStatus.CONNECTED,
    "online": SystemStatus.ONLINE,
    "offline": SystemStatus.OFFLINE,
    "disconnected": SystemStatus.DISCONNECTED,
    "unknown": SystemStatus.UNKNOWN,
    "service": SystemStatus.SERVICE,
    "firmware_update": SystemStatus.FIRMWARE_UPDATE,
}

_CONNECT_TIMEOUT = 10.0
_SUBSCRIBE_TIMEOUT = 10.0
_OPERATION_TIMEOUT = 10.0
_DISCONNECT_TIMEOUT = 5.0

# MQTT connection parameters, taken from the reference app's own AWS IoT
# client configuration (decomp-confirmed, see docs/reference/systems/zs500.md).
_KEEPALIVE_INTERVAL_SEC = 60
_MIN_RECONNECT_DELAY_MS = 1000
_MAX_RECONNECT_DELAY_MS = 30000
_MIN_CONNECTED_TIME_TO_RESET_RECONNECT_DELAY_MS = 20000


def _error_for_rejected(response: Any) -> AqualinkServiceException:
    code = getattr(response, "code", None)
    message = getattr(response, "message", None) or "Shadow operation rejected"
    if code == 401:
        return AqualinkServiceUnauthorizedException(message)
    if code == 429:
        return AqualinkServiceThrottledException(message)
    return AqualinkServiceException(f"{message} (code={code})")


class Zs500System(AqualinkSystem):
    NAME = "zs500"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)
        self.temp_unit = "C"

        self._mqtt: mqtt5.Client | None = None
        self._shadow: iotshadow.IotShadowClient | None = None
        self._stopped: asyncio.Future[None] | None = None
        self._connect_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[Any]] = {}

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    # -- connection lifecycle -------------------------------------------------

    async def _ensure_connected(self) -> iotshadow.IotShadowClient:
        async with self._connect_lock:
            if self._shadow is not None:
                return self._shadow

            credentials = self.aqualink.iot_credentials
            if not credentials:
                raise AqualinkServiceUnauthorizedException(
                    "No AWS IoT credentials available; login or refresh first."
                )

            loop = asyncio.get_running_loop()
            connected: asyncio.Future[None] = loop.create_future()
            stopped: asyncio.Future[None] = loop.create_future()

            credentials_provider = auth.AwsCredentialsProvider.new_static(
                credentials["AccessKeyId"],
                credentials["SecretKey"],
                credentials.get("SessionToken"),
            )

            def _on_success(_data: Any) -> None:
                loop.call_soon_threadsafe(_resolve, connected, None, None)

            def _on_failure(data: Any) -> None:
                exc = getattr(data, "exception", None)
                if not isinstance(exc, BaseException):
                    exc = AqualinkServiceException("MQTT connection failed")
                loop.call_soon_threadsafe(_resolve, connected, None, exc)

            def _on_stopped(_data: Any) -> None:
                loop.call_soon_threadsafe(_resolve, stopped, None, None)

            mqtt = mqtt5_client_builder.websockets_with_default_aws_signing(
                endpoint=AQUALINK_AWS_IOT_ENDPOINT,
                region=AQUALINK_AWS_IOT_REGION,
                credentials_provider=credentials_provider,
                client_id=str(uuid.uuid4()),
                keep_alive_interval_sec=_KEEPALIVE_INTERVAL_SEC,
                min_reconnect_delay_ms=_MIN_RECONNECT_DELAY_MS,
                max_reconnect_delay_ms=_MAX_RECONNECT_DELAY_MS,
                min_connected_time_to_reset_reconnect_delay_ms=_MIN_CONNECTED_TIME_TO_RESET_RECONNECT_DELAY_MS,
                on_lifecycle_connection_success=_on_success,
                on_lifecycle_connection_failure=_on_failure,
                on_lifecycle_stopped=_on_stopped,
            )
            mqtt.start()

            try:
                await asyncio.wait_for(connected, timeout=_CONNECT_TIMEOUT)
            except Exception as e:
                mqtt.stop()
                raise AqualinkServiceException(
                    f"MQTT connection failed: {e}"
                ) from e

            shadow = iotshadow.IotShadowClient(mqtt)
            try:
                await self._subscribe_all(shadow)
            except Exception as e:
                mqtt.stop()
                raise AqualinkServiceException(
                    f"MQTT subscribe failed: {e}"
                ) from e

            self._mqtt = mqtt
            self._shadow = shadow
            self._stopped = stopped
            return shadow

    async def _subscribe_all(self, shadow: iotshadow.IotShadowClient) -> None:
        loop = asyncio.get_running_loop()

        def _on_accept(response: Any) -> None:
            loop.call_soon_threadsafe(
                self._resolve_pending, response.client_token, response, None
            )

        def _on_reject(response: Any) -> None:
            loop.call_soon_threadsafe(
                self._resolve_pending,
                response.client_token,
                None,
                _error_for_rejected(response),
            )

        def _on_push(event: iotshadow.ShadowUpdatedEvent) -> None:
            current = event.current
            state = current.state if current is not None else None
            reported = state.reported if state is not None else None
            loop.call_soon_threadsafe(
                self._apply_reported_state, reported or {}
            )

        subscriptions = [
            shadow.subscribe_to_get_shadow_accepted(
                request=iotshadow.GetShadowSubscriptionRequest(
                    thing_name=self.serial
                ),
                qos=mqtt5.QoS.AT_LEAST_ONCE,
                callback=_on_accept,
            ),
            shadow.subscribe_to_get_shadow_rejected(
                request=iotshadow.GetShadowSubscriptionRequest(
                    thing_name=self.serial
                ),
                qos=mqtt5.QoS.AT_LEAST_ONCE,
                callback=_on_reject,
            ),
            shadow.subscribe_to_update_shadow_accepted(
                request=iotshadow.UpdateShadowSubscriptionRequest(
                    thing_name=self.serial
                ),
                qos=mqtt5.QoS.AT_LEAST_ONCE,
                callback=_on_accept,
            ),
            shadow.subscribe_to_update_shadow_rejected(
                request=iotshadow.UpdateShadowSubscriptionRequest(
                    thing_name=self.serial
                ),
                qos=mqtt5.QoS.AT_LEAST_ONCE,
                callback=_on_reject,
            ),
            shadow.subscribe_to_shadow_updated_events(
                request=iotshadow.ShadowUpdatedSubscriptionRequest(
                    thing_name=self.serial
                ),
                qos=mqtt5.QoS.AT_LEAST_ONCE,
                callback=_on_push,
            ),
        ]
        await asyncio.wait_for(
            asyncio.gather(
                *(
                    asyncio.wrap_future(future)
                    for future, _topic in subscriptions
                )
            ),
            timeout=_SUBSCRIBE_TIMEOUT,
        )

    async def _disconnect(self) -> None:
        async with self._connect_lock:
            mqtt = self._mqtt
            stopped = self._stopped
            self._mqtt = None
            self._shadow = None
            self._stopped = None

            if mqtt is None:
                return

            mqtt.stop()
            if stopped is not None:
                try:
                    await asyncio.wait_for(stopped, timeout=_DISCONNECT_TIMEOUT)
                except Exception:
                    LOGGER.debug(
                        "MQTT client for %s did not confirm stop within %ss",
                        mask_serial(self.serial),
                        _DISCONNECT_TIMEOUT,
                    )

    async def aclose(self) -> None:
        await self._disconnect()

    # -- request/response correlation -----------------------------------------

    def _resolve_pending(
        self, token: str | None, result: Any, exc: BaseException | None
    ) -> None:
        fut = self._pending.get(token) if token else None
        if fut is None or fut.done():
            return
        if exc is not None:
            fut.set_exception(exc)
        else:
            fut.set_result(result)

    async def _call_with_reauth_retry(
        self, operation: Callable[[], Awaitable[T]]
    ) -> T:
        try:
            return await operation()
        except AqualinkServiceUnauthorizedException:
            await self._disconnect()
            self.aqualink._logged = False  # noqa: SLF001
            await self.aqualink._refresh_auth()  # noqa: SLF001
            return await operation()

    # -- shadow get/update -----------------------------------------------------

    async def _refresh(self) -> None:
        await self._call_with_reauth_retry(self._shadow_get)

    async def _shadow_get(self) -> None:
        shadow = await self._ensure_connected()

        token = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[token] = fut
        try:
            try:
                publish_future = shadow.publish_get_shadow(
                    request=iotshadow.GetShadowRequest(
                        thing_name=self.serial, client_token=token
                    ),
                    qos=mqtt5.QoS.AT_LEAST_ONCE,
                )
                await asyncio.wrap_future(publish_future)
                response = await asyncio.wait_for(
                    fut, timeout=_OPERATION_TIMEOUT
                )
            except AqualinkServiceException:
                raise
            except Exception as e:
                # Most likely a concurrent aclose()/reconnect tore down the
                # connection out from under this in-flight operation.
                raise AqualinkServiceException(
                    f"zs500 shadow get failed: {e}"
                ) from e
        finally:
            self._pending.pop(token, None)

        reported = response.state.reported if response.state else None
        self._apply_reported_state(reported or {})

    async def set_desired(self, hp_0_delta: Payload) -> None:
        """Publish a desired-state delta for the `equipment.hp_0` object.

        Only the changed fields need to be included.
        """
        await self._call_with_reauth_retry(
            lambda: self._shadow_update(hp_0_delta)
        )

    async def _shadow_update(self, hp_0_delta: dict[str, Any]) -> None:
        shadow = await self._ensure_connected()

        token = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[token] = fut
        try:
            try:
                publish_future = shadow.publish_update_shadow(
                    request=iotshadow.UpdateShadowRequest(
                        thing_name=self.serial,
                        client_token=token,
                        state=iotshadow.ShadowState(
                            desired={"equipment": {"hp_0": hp_0_delta}}
                        ),
                    ),
                    qos=mqtt5.QoS.AT_LEAST_ONCE,
                )
                await asyncio.wrap_future(publish_future)
                await asyncio.wait_for(fut, timeout=_OPERATION_TIMEOUT)
            except AqualinkServiceException:
                raise
            except Exception as e:
                raise AqualinkServiceException(
                    f"zs500 shadow update failed: {e}"
                ) from e
        finally:
            self._pending.pop(token, None)

    # -- parsing -----------------------------------------------------------

    def _apply_reported_state(self, reported: dict[str, Any]) -> None:
        LOGGER.debug("Shadow reported: %s", redact_value(reported))

        # reported["aws"] can be missing, an explicit null, or a dict on the
        # wire — `or {}` collapses all three to a safe default before .get().
        raw_status: Any = (reported.get("aws") or {}).get("status")
        if raw_status in (None, ""):
            self.status = SystemStatus.UNKNOWN
        else:
            mapped = _ZS500_STATUS_MAP.get(raw_status)
            if mapped is None:
                LOGGER.warning(
                    "Unknown aws.status %r for system %s (%s); treating as Unknown.",
                    raw_status,
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

        hp_0: Any = (reported.get("equipment") or {}).get("hp_0")
        if not hp_0:
            return

        devices: dict[str, dict[str, Any]] = {
            "climate": {
                "name": "climate",
                "state": hp_0.get("state", 0),
                "tsp": hp_0.get("tsp", 0),
            },
            "mode": {"name": "mode", "st": hp_0.get("st", 0)},
            "cooling": {"name": "cooling", "cl": hp_0.get("cl", 0)},
            "heating_priority": {
                "name": "heating_priority",
                "hp": hp_0.get("hp", 0),
            },
            "compressor_speed": {
                "name": "compressor_speed",
                "cmprSpd": hp_0.get("cmprSpd", 0),
            },
            "standby_reason": {
                "name": "standby_reason",
                "reason": hp_0.get("reason", 0),
            },
            "error": {
                "name": "error",
                "errorCode": hp_0.get("errorCode") or "0",
                "errorTime": hp_0.get("errorTime"),
            },
        }
        if "sns_1" in hp_0:
            devices["water_temp"] = {"name": "water_temp", **hp_0["sns_1"]}
        if "sns_2" in hp_0:
            devices["air_temp"] = {"name": "air_temp", **hp_0["sns_2"]}

        for key, value in devices.items():
            if key in self.devices:
                self.devices[key].data = value
            else:
                self.devices[key] = Zs500Device.from_data(self, value)


def _resolve(
    fut: asyncio.Future[Any], result: Any, exc: BaseException | None
) -> None:
    if fut.done():
        return
    if exc is not None:
        fut.set_exception(exc)
    else:
        fut.set_result(result)
