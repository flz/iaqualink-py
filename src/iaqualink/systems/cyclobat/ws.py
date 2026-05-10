from __future__ import annotations

from typing import TYPE_CHECKING, Any

from iaqualink.systems._robot_ws import (
    ACTION_SET_CLEANING_MODE,
    build_set_state_frame,
    client_token,
    send_frame,
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
    await send_frame(client, frame)
