from __future__ import annotations

from typing import TYPE_CHECKING, Any

from iaqualink.systems._robot_ws import (
    ACTION_SET_CLEANER_STATE,
    ACTION_SET_REMOTE_STEERING,
    build_set_state_frame,
    client_token,
    send_frame,
)

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

VR_NAMESPACE = "vr"


def build_robot_state_frame(
    serial: str,
    robot_state: dict[str, Any],
    token: str,
    *,
    namespace: str = VR_NAMESPACE,
    action: str = ACTION_SET_CLEANER_STATE,
) -> dict[str, Any]:
    return build_set_state_frame(
        namespace=namespace,
        target=serial,
        equipment_state={"robot": robot_state},
        token=token,
        action=action,
    )


async def send_set_state(
    client: AqualinkClient,
    serial: str,
    state: int,
    *,
    namespace: str = VR_NAMESPACE,
) -> None:
    # state: 0=stop, 1=clean, 2=pause, 3=return.
    frame = build_robot_state_frame(
        serial,
        {"state": state},
        client_token(client),
        namespace=namespace,
    )
    await send_frame(client, frame)


async def send_set_cycle(
    client: AqualinkClient,
    serial: str,
    cycle: int,
    *,
    namespace: str = VR_NAMESPACE,
) -> None:
    frame = build_robot_state_frame(
        serial,
        {"prCyc": cycle},
        client_token(client),
        namespace=namespace,
    )
    await send_frame(client, frame)


async def send_set_stepper(
    client: AqualinkClient,
    serial: str,
    minutes: int,
    *,
    namespace: str = VR_NAMESPACE,
) -> None:
    # Absolute runtime extension in minutes.
    frame = build_robot_state_frame(
        serial,
        {"stepper": minutes},
        client_token(client),
        namespace=namespace,
    )
    await send_frame(client, frame)


async def send_remote_steering(
    client: AqualinkClient,
    serial: str,
    rmt_ctrl: int,
    *,
    namespace: str = VR_NAMESPACE,
) -> None:
    # Caller must put the robot in pause state (state==2) first; the
    # `VrSystem.remote_*` helpers handle that transition automatically.
    frame = build_robot_state_frame(
        serial,
        {"rmt_ctrl": rmt_ctrl},
        client_token(client),
        namespace=namespace,
        action=ACTION_SET_REMOTE_STEERING,
    )
    await send_frame(client, frame)
