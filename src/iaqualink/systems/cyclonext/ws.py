"""Cyclonext write-side WebSocket commands."""

from __future__ import annotations

__all__ = [
    "CYCLONEXT_ACTION_SET_STATE",
    "CYCLONEXT_NAMESPACE",
    "CYCLONEXT_SERVICE",
    "CYCLONEXT_WS_URL",
    "build_desired_state_frame",
    "build_set_mode_frame",
    "send_set_cycle",
    "send_set_mode",
    "send_set_remote_state",
    "send_set_stepper",
]

from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_WS_URL
from iaqualink.shared.robots import (
    ACTION_SET_CLEANER_STATE,
    build_set_state_frame,
    client_token,
    send_robot_frame,
)

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

CYCLONEXT_WS_URL = AQUALINK_WS_URL
CYCLONEXT_NAMESPACE = "cyclonext"
CYCLONEXT_SERVICE = "StateController"
CYCLONEXT_ACTION_SET_STATE = ACTION_SET_CLEANER_STATE


def build_desired_state_frame(
    serial: str,
    robot_state: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    return build_set_state_frame(
        namespace=CYCLONEXT_NAMESPACE,
        target=serial,
        equipment_state={"robot.1": robot_state},
        token=token,
    )


def build_set_mode_frame(
    serial: str,
    mode: int,
    token: str,
) -> dict[str, Any]:
    return build_desired_state_frame(serial, {"mode": mode}, token)


async def send_set_mode(
    client: AqualinkClient,
    serial: str,
    mode: int,
) -> None:
    frame = build_set_mode_frame(serial, mode, client_token(client))
    await send_robot_frame(client, frame)


async def send_set_cycle(
    client: AqualinkClient,
    serial: str,
    cycle: int,
) -> None:
    frame = build_desired_state_frame(
        serial, {"cycle": cycle}, client_token(client)
    )
    await send_robot_frame(client, frame)


async def send_set_stepper(
    client: AqualinkClient,
    serial: str,
    minutes: int,
) -> None:
    frame = build_desired_state_frame(
        serial, {"stepper": minutes}, client_token(client)
    )
    await send_robot_frame(client, frame)


async def send_set_remote_state(
    client: AqualinkClient,
    serial: str,
    mode: int,
    direction: int,
) -> None:
    frame = build_desired_state_frame(
        serial, {"mode": mode, "direction": direction}, client_token(client)
    )
    await send_robot_frame(client, frame)
