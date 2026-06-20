"""Test harness for zs500's MQTT shadow transport.

The conformance suite (tests/conformance/*) mocks httpx via respx and assumes
every system command/refresh goes over HTTP. zs500 goes over MQTT instead, so
none of its factories participate there (see factories.py) — this harness is
the bespoke substitute, faking the awsiotsdk shadow client directly.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Future as CFuture
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from awsiot import iotshadow

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem
from iaqualink.systems.zs500.system import Zs500System

ZS500_SYSTEM_DATA: dict[str, Any] = {
    "id": 1,
    "serial_number": "SN123456",
    "device_type": "zs500",
    "name": "Pool Heat Pump",
}


def _done_future(result: Any) -> CFuture:
    f: CFuture = CFuture()
    f.set_result(result)
    return f


def _failing_future(exc: BaseException) -> CFuture:
    f: CFuture = CFuture()
    f.set_exception(exc)
    return f


class FakeShadowClient:
    """Stand-in for awsiot.iotshadow.IotShadowClient.

    Records every publish and auto-replies on the matching accepted/rejected
    topic using whichever client_token the caller sent, mirroring how AWS IoT
    correlates shadow operations in practice.
    """

    def __init__(self) -> None:
        self.published_gets: list[str | None] = []
        self.published_updates: list[dict[str, Any]] = []
        self._get_accept: Any = None
        self._get_reject: Any = None
        self._update_accept: Any = None
        self._update_reject: Any = None
        self._push: Any = None

        self.get_response: dict[str, Any] = {}
        self.get_reject_code: int | None = None
        self.update_reject_code: int | None = None
        # When set, publish_get_shadow/publish_update_shadow accept the
        # publish but never call either the accept or reject callback —
        # simulates an operation that times out waiting for a response.
        self.silent: bool = False
        # When set, the first subscribe_to_* call fails — simulates a
        # subscribe failure right after a successful connect.
        self.subscribe_fails: bool = False

    # -- subscribe_to_* (returns (Future, topic), per awsiotsdk convention) --

    def subscribe_to_get_shadow_accepted(
        self, *, request: Any, qos: Any, callback: Any
    ) -> Any:
        self._get_accept = callback
        if self.subscribe_fails:
            return (
                _failing_future(RuntimeError("simulated subscribe failure")),
                "get/accepted",
            )
        return _done_future(0), "get/accepted"

    def subscribe_to_get_shadow_rejected(
        self, *, request: Any, qos: Any, callback: Any
    ) -> Any:
        self._get_reject = callback
        return _done_future(0), "get/rejected"

    def subscribe_to_update_shadow_accepted(
        self, *, request: Any, qos: Any, callback: Any
    ) -> Any:
        self._update_accept = callback
        return _done_future(0), "update/accepted"

    def subscribe_to_update_shadow_rejected(
        self, *, request: Any, qos: Any, callback: Any
    ) -> Any:
        self._update_reject = callback
        return _done_future(0), "update/rejected"

    def subscribe_to_shadow_updated_events(
        self, *, request: Any, qos: Any, callback: Any
    ) -> Any:
        self._push = callback
        return _done_future(0), "update/documents"

    # -- publish_* (returns just a Future, per awsiotsdk convention) --

    def publish_get_shadow(self, *, request: Any, qos: Any) -> Any:
        self.published_gets.append(request.client_token)
        if self.silent:
            return _done_future(None)
        loop = asyncio.get_running_loop()
        if self.get_reject_code is not None:
            response = iotshadow.ErrorResponse(
                client_token=request.client_token,
                code=self.get_reject_code,
                message="rejected",
            )
            loop.call_soon(self._get_reject, response)
        else:
            response = iotshadow.GetShadowResponse(
                client_token=request.client_token,
                state=iotshadow.ShadowState(reported=self.get_response),
            )
            loop.call_soon(self._get_accept, response)
        return _done_future(None)

    def publish_update_shadow(self, *, request: Any, qos: Any) -> Any:
        self.published_updates.append(request.state.desired)
        if self.silent:
            return _done_future(None)
        loop = asyncio.get_running_loop()
        if self.update_reject_code is not None:
            response = iotshadow.ErrorResponse(
                client_token=request.client_token,
                code=self.update_reject_code,
                message="rejected",
            )
            loop.call_soon(self._update_reject, response)
        else:
            response = iotshadow.UpdateShadowResponse(
                client_token=request.client_token
            )
            loop.call_soon(self._update_accept, response)
        return _done_future(None)

    # -- test helper: simulate a device-initiated (or anyone-initiated) push --

    def push(self, reported: dict[str, Any]) -> None:
        event = iotshadow.ShadowUpdatedEvent(
            current=iotshadow.ShadowUpdatedSnapshot(
                state=iotshadow.ShadowState(reported=reported)
            )
        )
        assert self._push is not None, "not subscribed yet"
        self._push(event)


class ConnectControl:
    """Mutable connect-outcome knob, read fresh on every connect attempt —
    lets a test flip `connect_succeeds` between calls to exercise both a
    failed first connect and a successful reconnect."""

    def __init__(self) -> None:
        self.connect_succeeds = True


def _make_builder(mqtt_mock: MagicMock, control: ConnectControl) -> Any:
    def _builder(**kwargs: Any) -> MagicMock:
        on_stopped = kwargs.get("on_lifecycle_stopped")

        def _stop(*_args: Any, **_kwargs: Any) -> None:
            if on_stopped is not None:
                asyncio.get_running_loop().call_soon(on_stopped, MagicMock())

        mqtt_mock.stop.side_effect = _stop

        if control.connect_succeeds:
            kwargs["on_lifecycle_connection_success"](MagicMock())
        else:
            failure = MagicMock(
                exception=AssertionError("simulated connect failure")
            )
            kwargs["on_lifecycle_connection_failure"](failure)
        return mqtt_mock

    return _builder


@dataclass
class Zs500Harness:
    """Bundles a Zs500System with its faked MQTT transport for assertions."""

    system: Zs500System
    shadow: FakeShadowClient
    mqtt: MagicMock
    connect_control: ConnectControl


@pytest.fixture
def zs500_harness(monkeypatch: pytest.MonkeyPatch) -> Zs500Harness:
    client = AqualinkClient("foo", "bar")
    client.iot_credentials = {
        "AccessKeyId": "AKIDEXAMPLE",
        "SecretKey": "SECRETEXAMPLE",
        "SessionToken": "TOKENEXAMPLE",
    }
    system = AqualinkSystem.from_data(client, data=ZS500_SYSTEM_DATA)
    assert isinstance(system, Zs500System)

    mqtt_mock = MagicMock()
    fake_shadow = FakeShadowClient()
    connect_control = ConnectControl()

    monkeypatch.setattr(
        "iaqualink.systems.zs500.system.mqtt5_client_builder.websockets_with_default_aws_signing",
        _make_builder(mqtt_mock, connect_control),
    )
    monkeypatch.setattr(
        "iaqualink.systems.zs500.system.iotshadow.IotShadowClient",
        lambda _mqtt: fake_shadow,
    )

    return Zs500Harness(
        system=system,
        shadow=fake_shadow,
        mqtt=mqtt_mock,
        connect_control=connect_control,
    )
