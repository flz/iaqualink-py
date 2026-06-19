"""Shared WebSocket framing for Zodiac robot cleaners.

Used by cyclobat (and cyclonext/vortrax/vr in the stack) to publish
StateController frames. The wss transport lives on
``AqualinkClient.send_ws_frame``; this module only builds robot frames and
forwards them to that shared endpoint.
"""

from __future__ import annotations

__all__ = [
    "ACTION_SET_CLEANER_STATE",
    "ACTION_SET_CLEANING_MODE",
    "ACTION_SET_REMOTE_STEERING",
    "ACTION_SUBSCRIBE",
    "EVENT_STATE_REPORTED",
    "NAMESPACE_AUTHORIZATION",
    "SERVICE_AUTHORIZATION",
    "SERVICE_STATE_CONTROLLER",
    "SERVICE_STATE_STREAMER",
    "RobotStateSubscription",
    "build_set_state_frame",
    "build_subscribe_frame",
    "client_token",
    "deep_merge",
    "send_robot_frame",
]

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_WS_URL
from iaqualink.system import SystemStatus

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient
    from iaqualink.device import AqualinkDevice

LOGGER = logging.getLogger("iaqualink.shared.robots")

SERVICE_STATE_CONTROLLER = "StateController"
ACTION_SET_CLEANER_STATE = "setCleanerState"
ACTION_SET_CLEANING_MODE = "setCleaningMode"
ACTION_SET_REMOTE_STEERING = "setRemoteSteeringControl"

# Receive side: the cloud pushes state on the StateStreamer service as
# StateReported events after an Authorization subscribe.
ACTION_SUBSCRIBE = "subscribe"
NAMESPACE_AUTHORIZATION = "authorization"
SERVICE_AUTHORIZATION = "Authorization"
SERVICE_STATE_STREAMER = "StateStreamer"
EVENT_STATE_REPORTED = "StateReported"


def deep_merge(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `delta` into a copy of `base` (delta wins)."""
    out = dict(base)
    for key, value in delta.items():
        existing = out.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            out[key] = deep_merge(existing, value)
        else:
            out[key] = value
    return out


def client_token(client: AqualinkClient) -> str:
    """Build the WS clientToken.

    Three-part ``{user_id}|{auth_token}|{app_client_id}`` when Cognito's
    appClientId is available (vr/vortrax/cyclobat); two-part
    ``{user_id}|<random-uuid-hex>`` fallback for cyclonext.
    """
    if client.app_client_id:
        return (
            f"{client.user_id}"
            f"|{client.authentication_token}"
            f"|{client.app_client_id}"
        )
    return f"{client.user_id}|{uuid.uuid4().hex}"


def build_set_state_frame(
    *,
    namespace: str,
    target: str,
    equipment_state: dict[str, Any],
    token: str,
    action: str = ACTION_SET_CLEANER_STATE,
) -> dict[str, Any]:
    """Build the JSON shape posted on the StateController WS channel."""
    return {
        "version": 1,
        "action": action,
        "namespace": namespace,
        "service": SERVICE_STATE_CONTROLLER,
        "target": target,
        "payload": {
            "clientToken": token,
            "state": {"desired": {"equipment": equipment_state}},
        },
    }


def build_subscribe_frame(
    *,
    user_id: str | int,
    target: str,
) -> dict[str, Any]:
    """Build the Authorization subscribe frame sent on connect.

    Generic across robot systems (and tcx): it opens the StateStreamer push
    stream for the account. ``userId`` is numeric on the wire.
    """
    try:
        uid: str | int = int(user_id)
    except (TypeError, ValueError):
        uid = user_id
    return {
        "action": ACTION_SUBSCRIBE,
        "version": 1,
        "namespace": NAMESPACE_AUTHORIZATION,
        "service": SERVICE_AUTHORIZATION,
        "payload": {"userId": uid},
        "target": target,
    }


async def send_robot_frame(
    client: AqualinkClient,
    frame: dict[str, Any],
) -> None:
    """Send a pre-built robot frame over the shared wss endpoint."""
    await client.send_ws_frame(AQUALINK_WS_URL, frame)


class RobotStateSubscription(ABC):
    """Mixin: persistent WebSocket state stream for robot systems.

    The vendor app keeps a wss connection open and applies pushed state
    instead of polling. On connect it sends an Authorization ``subscribe``
    frame; the cloud replies with the full reported state, then streams
    ``StateStreamer``/``StateReported`` deltas (``desired`` frames are command
    echoes, ignored). A system's ``_refresh`` should skip the REST poll while
    ``_ws_state_fresh()`` is true, so the socket dropping degrades to polling.

    Mix in before ``AqualinkSystem`` so the cooperative ``__init__`` and engine
    methods take MRO precedence. Concrete systems implement the three hooks for
    their own payload shape; the frame dispatch and lifecycle are shared.
    """

    # Max age of the last WS-pushed state before _refresh falls back to a REST
    # poll. Only consulted while the WS subscription is connected.
    WS_STATE_FRESH_SECS: float = 120.0

    # WS keepalive ping interval. Detects a silently dropped socket (the cloud
    # LB can half-open the connection) so the loop raises instead of blocking,
    # well inside WS_STATE_FRESH_SECS.
    WS_KEEPALIVE_SECS: float = 30.0

    if TYPE_CHECKING:
        # Provided by AqualinkSystem in the concrete MRO.
        aqualink: AqualinkClient
        serial: str
        status: SystemStatus
        devices: dict[str, AqualinkDevice]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # WebSocket state subscription (reduce polling). When the consumer
        # calls start_ws_subscription(), pushed state keeps _ws_last_update
        # fresh and _refresh skips the REST poll. Set False to force REST-only.
        self._ws_enabled: bool = True
        self._ws_task: asyncio.Task[None] | None = None
        self._ws_last_update: float | None = None
        self._ws_connected: bool = False
        super().__init__(*args, **kwargs)

    # --- system-specific hooks --------------------------------------------

    @abstractmethod
    def _extract_robot(self, reported: dict[str, Any]) -> dict[str, Any] | None:
        """Find the robot object in a `reported` payload (REST or WS shape)."""

    @abstractmethod
    def _apply_reported_state(self, reported: dict[str, Any]) -> None:
        """Apply a FULL `state.reported` payload and (re)build devices."""

    @abstractmethod
    def _apply_robot_delta(self, delta: dict[str, Any]) -> None:
        """Merge a partial robot dict (WS delta) and re-derive devices."""

    # --- shared subscription engine ---------------------------------------

    def _ws_state_fresh(self, max_age_secs: float | None = None) -> bool:
        """True if the WS is connected and delivered state within `max_age`.

        Requires a live connection: once the socket drops (hard or via missed
        keepalive ping), staleness is immediate so `_refresh` resumes REST.
        """
        if max_age_secs is None:
            max_age_secs = self.WS_STATE_FRESH_SECS
        if not self._ws_connected or self._ws_last_update is None:
            return False
        return (time.time() - self._ws_last_update) < max_age_secs

    def _ws_subscribe_frame(self) -> dict[str, Any]:
        """Authorization subscribe frame that opens the StateStreamer stream."""
        return build_subscribe_frame(
            user_id=self.aqualink.user_id, target=self.serial
        )

    def _apply_ws_frame(self, frame: dict[str, Any]) -> bool:
        """Apply a pushed WS frame. Returns True if device state changed.

        Handles the Authorization full-state ack and StateStreamer reported
        deltas; ignores `desired` command echoes, keepalives, and acks without
        usable robot state.
        """
        payload = frame.get("payload") or {}

        # Authorization ack carries the full reported state on connect.
        if frame.get("service") == SERVICE_AUTHORIZATION:
            reported = ((payload.get("robot") or {}).get("state") or {}).get(
                "reported"
            )
            if isinstance(reported, dict) and (
                self._extract_robot(reported) is not None
            ):
                self._apply_reported_state(reported)
                return True
            return False

        # StateStreamer pushes reported deltas (desired frames are echoes).
        if frame.get("event") == EVENT_STATE_REPORTED:
            reported = (payload.get("state") or {}).get("reported")
            if not isinstance(reported, dict):
                return False
            delta = self._extract_robot(reported)
            if delta is None:
                return False
            self._apply_robot_delta(delta)
            return True

        return False

    async def _ws_receive_loop(self) -> None:
        """Subscribe, then apply pushed frames until the connection drops.

        Keepalive pings surface a silently dropped socket; on any exit the
        connection is marked down so `_refresh` resumes REST polling.
        TODO(reduce-polling): auto-reconnect with backoff + a push callback so
        consumers (HA) can update on change instead of on poll.
        """
        async with self.aqualink.ws_connect(
            AQUALINK_WS_URL,
            keepalive_ping_interval_seconds=self.WS_KEEPALIVE_SECS,
        ) as ws:
            self._ws_connected = True
            try:
                await ws.send_text(json.dumps(self._ws_subscribe_frame()))
                while True:
                    raw = await ws.receive_text()
                    try:
                        frame = json.loads(raw)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue  # keepalive / non-JSON
                    if not isinstance(frame, dict):
                        continue
                    if self._apply_ws_frame(frame):
                        self._ws_last_update = time.time()
                        self.status = SystemStatus.ONLINE
            finally:
                self._ws_connected = False

    async def start_ws_subscription(self) -> None:
        """Start the background WS state subscription (no-op unless enabled)."""
        if not self._ws_enabled:
            return
        if self._ws_task is not None and not self._ws_task.done():
            return
        self._ws_task = asyncio.create_task(self._ws_receive_loop())
        self._ws_task.add_done_callback(self._on_ws_task_done)

    @staticmethod
    def _on_ws_task_done(task: asyncio.Task[None]) -> None:
        # Retrieve the exception so asyncio doesn't warn; the loop dropping is
        # non-fatal — _refresh resumes REST polling and restarts it.
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            LOGGER.debug("robot WS loop ended: %r", exc)

    async def stop_ws_subscription(self) -> None:
        """Cancel the background WS subscription, if running."""
        task = self._ws_task
        self._ws_task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
