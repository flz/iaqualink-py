"""Shared WebSocket framing for Zodiac robot cleaners.

Used by cyclobat (and cyclonext/vortrax/vr in the stack) to publish
StateController frames. The wss transport lives on
``AqualinkClient.send_ws_frame``; this module builds robot frames/state
handling on top of the generic engine in ``iaqualink.utils.websockets``.
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

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from iaqualink.system import SystemStatus
from iaqualink.utils.websockets import (
    ACTION_SUBSCRIBE,
    NAMESPACE_AUTHORIZATION,
    SERVICE_AUTHORIZATION,
    SERVICE_STATE_CONTROLLER,
    WsStateSubscription,
    build_subscribe_frame,
    client_token,
    deep_merge,
    send_ws_command_frame,
)

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

SERVICE_STATE_STREAMER = "StateStreamer"
EVENT_STATE_REPORTED = "StateReported"

ACTION_SET_CLEANER_STATE = "setCleanerState"
ACTION_SET_CLEANING_MODE = "setCleaningMode"
ACTION_SET_REMOTE_STEERING = "setRemoteSteeringControl"


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


async def send_robot_frame(
    client: AqualinkClient,
    frame: dict[str, Any],
) -> None:
    """Send a pre-built robot frame over the shared wss endpoint."""
    await send_ws_command_frame(client, frame)


class RobotStateSubscription(WsStateSubscription):
    """Mixin: persistent WebSocket state stream for robot systems.

    Concrete systems implement the three hooks below for their own robot
    payload shape; frame dispatch and lifecycle come from the shared
    `WsStateSubscription` engine.
    """

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

    # --- WsStateSubscription hook implementations --------------------------

    def _ws_full_state_from_frame(
        self, frame: dict[str, Any]
    ) -> dict[str, Any] | None:
        payload = frame.get("payload") or {}
        reported = ((payload.get("robot") or {}).get("state") or {}).get(
            "reported"
        )
        if isinstance(reported, dict) and (
            self._extract_robot(reported) is not None
        ):
            return reported
        return None

    def _ws_delta_from_frame(
        self, frame: dict[str, Any]
    ) -> dict[str, Any] | None:
        if frame.get("event") != EVENT_STATE_REPORTED:
            return None
        payload = frame.get("payload") or {}
        reported = (payload.get("state") or {}).get("reported")
        if not isinstance(reported, dict):
            return None
        return self._extract_robot(reported)

    def _apply_full_state(self, reported: dict[str, Any]) -> None:
        # Robots have no richer status derivation of their own — a
        # successful WS apply means the socket is live, so mark ONLINE here
        # (unlike tcx, which derives status itself from the reported tree).
        self.status = SystemStatus.ONLINE
        self._apply_reported_state(reported)

    def _apply_state_delta(self, delta: dict[str, Any]) -> None:
        self.status = SystemStatus.ONLINE
        self._apply_robot_delta(delta)
