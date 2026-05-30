"""Shared WebSocket helper for Zodiac robot cleaners.

Used by cyclobat, cyclonext, vortrax, vr system packages to publish
StateController setCleanerState frames. Imports `websockets` lazily so
the `robot` optional extra remains optional for non-robot installs.
"""

from __future__ import annotations

__all__ = [
    "ACTION_SET_CLEANER_STATE",
    "ACTION_SET_CLEANING_MODE",
    "ACTION_SET_REMOTE_STEERING",
    "ROBOT_WS_URL",
    "RobotWebsocketDependencyError",
    "build_set_state_frame",
    "client_token",
    "send_frame",
    "ws_connect",
]

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from iaqualink.exception import AqualinkException

try:
    from websockets.asyncio.client import connect as _ws_connect_callable

    ws_connect: Any | None = _ws_connect_callable
except ImportError:  # robot extra not installed
    ws_connect = None

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

ROBOT_WS_URL = "wss://prod-socket.zodiac-io.com/devices"
SERVICE_STATE_CONTROLLER = "StateController"
ACTION_SET_CLEANER_STATE = "setCleanerState"
ACTION_SET_CLEANING_MODE = "setCleaningMode"
ACTION_SET_REMOTE_STEERING = "setRemoteSteeringControl"

LOGGER = logging.getLogger("iaqualink.systems._robot_ws")

_ACK_TIMEOUT_SECS = 2.0


class RobotWebsocketDependencyError(AqualinkException):
    """Raised when robot WS commands are issued without `websockets` installed."""


def client_token(client: AqualinkClient) -> str:
    """Build the WS clientToken.

    Three-part `{user_id}|{auth_token}|{app_client_id}` when Cognito's
    appClientId is available (vr/vortrax/cyclobat); two-part
    `{user_id}|<random-uuid-hex>` fallback for cyclonext.
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


async def send_frame(
    client: AqualinkClient,
    frame: dict[str, Any],
) -> None:
    """Open a one-shot WS connection, send `frame`, best-effort wait for ack."""
    if ws_connect is None:
        msg = (
            "websockets package required for robot WebSocket commands; "
            "install with `pip install iaqualink[robot]`."
        )
        raise RobotWebsocketDependencyError(msg)

    headers = {"Authorization": client.id_token}

    LOGGER.debug(
        "Sending robot frame action=%s namespace=%s target=%s",
        frame.get("action"),
        frame.get("namespace"),
        frame.get("target"),
    )
    async with ws_connect(
        ROBOT_WS_URL,
        additional_headers=headers,
    ) as conn:
        await conn.send(json.dumps(frame))
        try:
            ack = await asyncio.wait_for(conn.recv(), _ACK_TIMEOUT_SECS)
        except (TimeoutError, Exception) as exc:  # noqa: BLE001 - best-effort
            LOGGER.debug(
                "No ack from robot WS within %.1fs: %r",
                _ACK_TIMEOUT_SECS,
                exc,
            )
        else:
            ack_len = len(ack) if isinstance(ack, (str, bytes)) else -1
            LOGGER.debug("Robot WS ack received (length=%d)", ack_len)
