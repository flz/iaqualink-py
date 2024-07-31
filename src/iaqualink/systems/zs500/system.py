from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from awscrt import auth, mqtt5
from awsiot import iotshadow, mqtt5_client_builder

from iaqualink.const import (
    AQUALINK_AWS_IOT_ENDPOINT,
    AQUALINK_AWS_IOT_REGION,
    MIN_SECS_TO_REFRESH,
)
from iaqualink.exception import (
    AqualinkDeviceNotSupported,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.zs500.device import Zs500Device

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

LOGGER = logging.getLogger("iaqualink")

def create_callback(coro):
    loop = asyncio.get_running_loop()

    def callback(data):
        asyncio.run_coroutine_threadsafe(coro(data), loop)

    return callback

class Zs500System(AqualinkSystem):
    NAME = "zs500"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)

        self._updates = {}
        self._started = False
        self.temp_unit = 'C'

        self._shadow = None

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f'{self.__class__.__name__}({" ".join(attrs)})'

    async def _connect(self) -> None:
        credentials = auth.AwsCredentialsProvider.new_static(
            self.aqualink._iot_credentials["AccessKeyId"],
            self.aqualink._iot_credentials["SecretKey"],
            self.aqualink._iot_credentials["SessionToken"],
        )

        connected = asyncio.Future()
        async def on_connected(_):
            connected.set_result(True)

        async def on_failure(data):
            connected.set_exception(data)

        async def on_stopped(_):
            self._started = False

        mqtt = mqtt5_client_builder.websockets_with_default_aws_signing(
            region=AQUALINK_AWS_IOT_REGION,
            endpoint=AQUALINK_AWS_IOT_ENDPOINT,
            credentials_provider=credentials,
            on_lifecycle_stopped=create_callback(on_stopped),
            on_lifecycle_connection_success=create_callback(on_connected),
            on_lifecycle_connection_failure=create_callback(on_failure),
        )
        mqtt.start()

        await asyncio.wait_for(connected, timeout=5)

        self._shadow = iotshadow.IotShadowClient(mqtt)
        await self._attach_shadow_handlers()

        self._started = True

    async def _attach_shadow_handlers(self) -> None:

        async def on_reject(response: Any):
            if response.client_token in self._updates:
                self._updates[response.client_token].set_exception(response)

        async def on_accept(response: Any):
            if response.client_token in self._updates:
                self._updates[response.client_token].set_result(response)

        # Get Shadow
        ##########################
        accept_future, _ = self._shadow.subscribe_to_get_shadow_accepted(
            request=iotshadow.GetShadowSubscriptionRequest(thing_name=self.serial),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=create_callback(on_accept))

        reject_future, _ = self._shadow.subscribe_to_get_shadow_rejected(
            request=iotshadow.GetShadowSubscriptionRequest(thing_name=self.serial),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=create_callback(on_reject))

        # On shadow updates
        ##########################
        async def on_shadow_updated(response: iotshadow.ShadowUpdatedEvent):
            await self._parse_device_info(response.current)

        update_future, _ = self._shadow.subscribe_to_shadow_updated_events(
            request=iotshadow.ShadowUpdatedSubscriptionRequest(thing_name=self.serial),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=create_callback(on_shadow_updated),
        )

        # Update Shadow
        ##########################
        update_accept_future, _ = self._shadow.subscribe_to_update_shadow_accepted(
            request=iotshadow.UpdateShadowSubscriptionRequest(thing_name=self.serial),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=create_callback(on_accept),
        )

        reject_accept_future, _ = self._shadow.subscribe_to_update_shadow_rejected(
            request=iotshadow.UpdateShadowSubscriptionRequest(thing_name=self.serial),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
            callback=create_callback(on_reject),
        )

        await asyncio.gather(
            asyncio.wrap_future(accept_future),
            asyncio.wrap_future(reject_future),

            asyncio.wrap_future(update_future),

            asyncio.wrap_future(update_accept_future),
            asyncio.wrap_future(reject_accept_future),
        )

    async def set_device_property(self, device: Zs500Device, value: Any, *path) -> None:
        for k, dev in self.devices.items():
            if dev == device:
                await self.set_shadow_single(value, "equipment", k, *path)
                return
        raise AqualinkDeviceNotSupported

    async def set_shadow_single(self, value: Any, *keys) -> None:
        desired = {}

        target = desired
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = value

        await self.set_shadow(desired)

    async def set_shadow(self, desired: dict[str, dict]) -> None:
        token = str(uuid4)
        ready = asyncio.Future()
        self._updates[token] = ready

        publish = self._shadow.publish_update_shadow(
            request=iotshadow.UpdateShadowRequest(
                client_token=token,
                state=iotshadow.ShadowState(desired=desired),
                thing_name=self.serial,
            ),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
        )

        try:
            await asyncio.wrap_future(publish)
            await asyncio.wait_for(ready, timeout=10)
        finally:
            del self._updates[token]


    async def _parse_device_info(self, data: Any) -> None:
        report = data.state.reported
        equipment = report["equipment"]

        if report["aws"]["status"] != "connected":
            LOGGER.warning(f"Status for system {self.serial} is Offline.")
            raise AqualinkSystemOfflineException

        for k, v in equipment.items():
            if k in self.devices:
                self.devices[k].data = v
            else:
                self.devices[k] = Zs500Device.from_data(self, v)

    async def update(self) -> None:
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < MIN_SECS_TO_REFRESH:
            LOGGER.debug(f"Only {delta}s since last refresh.")
            return

        if not self._started:
            await self._connect()

        token = str(uuid4())
        ready = asyncio.Future()

        self._updates[token] = ready

        get_request = self._shadow.publish_get_shadow(
            request=iotshadow.GetShadowRequest(
                thing_name=self.serial,
                client_token=token
            ),
            qos=mqtt5.QoS.AT_LEAST_ONCE,
        )

        try:
            await asyncio.wrap_future(get_request)
            response = await asyncio.wait_for(ready, timeout=10)
            await self._parse_device_info(response)
        finally:
            del self._updates[token]

        self.online = True
        self.last_refresh = int(time.time())
