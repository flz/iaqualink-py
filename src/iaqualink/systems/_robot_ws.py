from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from iaqualink.exception import AqualinkException

_ws_connect: Any | None
try:
    from websockets.asyncio.client import connect as _ws_connect_impl

    _ws_connect = _ws_connect_impl
except ImportError:  # robot extra not installed
    _ws_connect = None

# Public alias preserved for back-compat with tests that patch
# `iaqualink.systems._robot_ws.ws_connect`.
ws_connect = _ws_connect

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

ROBOT_WS_URL = "wss://prod-socket.zodiac-io.com/devices"
SERVICE_STATE_CONTROLLER = "StateController"
ACTION_SET_CLEANER_STATE = "setCleanerState"
ACTION_SET_CLEANING_MODE = "setCleaningMode"
ACTION_SET_REMOTE_STEERING = "setRemoteSteeringControl"

LOGGER = logging.getLogger("iaqualink")

# Vendor sometimes acks via a dedicated frame and sometimes goes silent;
# never block waiting for a response.
_ACK_TIMEOUT_SECS = 2.0


class RobotWebsocketDependencyError(AqualinkException):
    pass


def client_token(client: AqualinkClient) -> str:
    # 3-part {userId}|{authToken}|{appClientId} when appClientId is
    # available (vr/vortrax/cyclobat); fall back to {userId}|<random>
    # which cyclonext accepts.
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
    if ws_connect is None:
        msg = (
            "websockets package required for robot WebSocket commands; "
            "install with `pip install iaqualink[robot]`."
        )
        raise RobotWebsocketDependencyError(msg)

    headers = {"Authorization": client.id_token}

    LOGGER.debug("Sending robot frame: %s", frame)
    async with ws_connect(
        ROBOT_WS_URL,
        additional_headers=headers,
    ) as conn:
        await conn.send(json.dumps(frame))
        try:
            ack = await asyncio.wait_for(conn.recv(), _ACK_TIMEOUT_SECS)
        except Exception:  # noqa: BLE001 - ack best-effort
            LOGGER.debug(
                "No ack from robot WS within %.1fs",
                _ACK_TIMEOUT_SECS,
                exc_info=True,
            )
        else:
            LOGGER.debug("Robot WS ack: %s", ack)
