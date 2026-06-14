"""Cyclobat write-side WebSocket commands."""

from __future__ import annotations

__all__ = [
    "CYCLOBAT_NAMESPACE",
    "build_cyclobat_main_ctrl_frame",
    "build_cyclobat_main_mode_frame",
    "send_set_ctrl",
    "send_set_mode",
]

from typing import TYPE_CHECKING, Any

from iaqualink.shared.robots import (
    ACTION_SET_CLEANING_MODE,
    build_set_state_frame,
    client_token,
    send_robot_frame,
)

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

CYCLOBAT_NAMESPACE = "cyclobat"


def build_cyclobat_main_ctrl_frame(
    serial: str,
    ctrl: int,
    token: str,
) -> dict[str, Any]:
    return build_set_state_frame(
        namespace=CYCLOBAT_NAMESPACE,
        target=serial,
        equipment_state={"robot": {"main": {"ctrl": ctrl}}},
        token=token,
        action=ACTION_SET_CLEANING_MODE,
    )


async def send_set_ctrl(
    client: AqualinkClient,
    serial: str,
    ctrl: int,
) -> None:
    frame = build_cyclobat_main_ctrl_frame(serial, ctrl, client_token(client))
    await send_robot_frame(client, frame)


def build_cyclobat_main_mode_frame(
    serial: str,
    mode: int,
    token: str,
) -> dict[str, Any]:
    # Cleaning-mode (cycle type) selection. Same setCleaningMode action as
    # ctrl, targeting main.mode. Mirrors the ctrl frame shape; not yet
    # confirmed against live hardware (see CLAUDE.md quality gate).
    return build_set_state_frame(
        namespace=CYCLOBAT_NAMESPACE,
        target=serial,
        equipment_state={"robot": {"main": {"mode": mode}}},
        token=token,
        action=ACTION_SET_CLEANING_MODE,
    )


async def send_set_mode(
    client: AqualinkClient,
    serial: str,
    mode: int,
) -> None:
    frame = build_cyclobat_main_mode_frame(serial, mode, client_token(client))
    await send_robot_frame(client, frame)
