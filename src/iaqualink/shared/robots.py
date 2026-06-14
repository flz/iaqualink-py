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
    "SERVICE_STATE_CONTROLLER",
    "build_set_state_frame",
    "client_token",
    "send_robot_frame",
]

import uuid
from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_WS_URL

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

SERVICE_STATE_CONTROLLER = "StateController"
ACTION_SET_CLEANER_STATE = "setCleanerState"
ACTION_SET_CLEANING_MODE = "setCleaningMode"
ACTION_SET_REMOTE_STEERING = "setRemoteSteeringControl"


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


async def send_robot_frame(
    client: AqualinkClient,
    frame: dict[str, Any],
) -> None:
    """Send a pre-built robot frame over the shared wss endpoint."""
    await client.send_ws_frame(AQUALINK_WS_URL, frame)
