"""TCX WebSocket support: state subscription (reads) + command frames (writes).

Per the reference app, the REST shadow endpoint is only used as a one-shot
online/offline status check on the system list screen — live state and
commands both go over the shared wss transport
(`AqualinkClient.ws_connect`/`send_ws_frame`). tcx has no "robot" wrapper
concept — its shadow is a flat multi-key tree scoped across ~9 namespaces
(see docs/reference/systems/tcx.md), so it builds directly on the generic
`WsStateSubscription` engine rather than the robot-shaped mixin.

The WS ack/delta payload's inner shape (beyond the envelope) has no
confirmed example in the reference doc — this module assumes it mirrors the
REST `state.reported` shape with no extra nesting. See "Not Observed / Needs
Verification" in docs/reference/systems/tcx.md and "Deltas vs Protocol
Reference" in docs/implementation/systems/tcx.md.
"""

from __future__ import annotations

__all__ = [
    "NAMESPACE_FEATURE_CIRCUIT",
    "NAMESPACE_FILTRATION",
    "NAMESPACE_SWC",
    "NAMESPACE_TCX",
    "NAMESPACE_ZIGBEE",
    "TcxStateSubscription",
]

from abc import abstractmethod
from typing import Any

from iaqualink.utils.websockets import (
    SERVICE_AUTHORIZATION,
    SERVICE_STATE_CONTROLLER,
    WsStateSubscription,
    client_token,
    send_ws_command_frame,
)

# Namespaces (docs/reference/systems/tcx.md "Namespaces").
NAMESPACE_TCX = "tcx"
NAMESPACE_FILTRATION = "filtration"
NAMESPACE_FEATURE_CIRCUIT = "featureCircuit"
NAMESPACE_ZIGBEE = "zigbee"
NAMESPACE_SWC = "swc"

# Push services that carry state deltas (Authorization carries full state and
# is handled separately by the generic engine).
_TCX_WS_DELTA_SERVICES = frozenset(
    {"StateStreamer", "DataStreamer", "EventStreamer"}
)


class TcxStateSubscription(WsStateSubscription):
    """Mixin: tcx WS envelope parsing (reads) + command frames (writes).

    tcx's shadow has no sub-object to drill into like robots' `equipment.
    robot` — the reported tree itself is what's applied/merged, so
    validation is just "non-empty dict".
    """

    @abstractmethod
    def _apply_reported_state(self, reported: dict[str, Any]) -> None:
        """Apply a FULL tcx `state.reported` tree (REST shadow or WS
        Authorization ack): derive status/temp_unit and rebuild devices."""

    @abstractmethod
    def _apply_reported_delta(self, delta: dict[str, Any]) -> None:
        """Merge a partial tcx reported-state dict (WS push) onto cached
        state and re-derive via `_apply_reported_state`."""

    def _ws_full_state_from_frame(
        self, frame: dict[str, Any]
    ) -> dict[str, Any] | None:
        if frame.get("service") != SERVICE_AUTHORIZATION:
            return None
        reported = ((frame.get("payload") or {}).get("state") or {}).get(
            "reported"
        )
        return reported if isinstance(reported, dict) and reported else None

    def _ws_delta_from_frame(
        self, frame: dict[str, Any]
    ) -> dict[str, Any] | None:
        if frame.get("service") not in _TCX_WS_DELTA_SERVICES:
            return None
        reported = ((frame.get("payload") or {}).get("state") or {}).get(
            "reported"
        )
        return reported if isinstance(reported, dict) and reported else None

    def _apply_full_state(self, reported: dict[str, Any]) -> None:
        self._apply_reported_state(reported)

    def _apply_state_delta(self, delta: dict[str, Any]) -> None:
        self._apply_reported_delta(delta)

    async def _send_command_frame(
        self,
        *,
        namespace: str,
        action: str,
        delta: dict[str, Any],
    ) -> None:
        """Send a `StateController` command frame over the shared wss.

        `delta` reuses the exact dict shape each write method already built
        for its REST desired-state POST (e.g. `{"filt0": {"st": state}}`) —
        the only field-level shape actually confirmed on the wire. Per-action
        WS payload shapes aren't documented beyond the envelope, so this is
        the best available inference (flagged in the implementation doc).
        Fire-and-forget: `send_ws_frame` best-effort-acks, no synchronous
        error surfacing (wire errors arrive later via `ErrorStreamer`).
        """
        frame = {
            "version": 1,
            "action": action,
            "namespace": namespace,
            "service": SERVICE_STATE_CONTROLLER,
            "target": self.serial,
            "payload": {**delta, "clientToken": client_token(self.aqualink)},
        }
        await send_ws_command_frame(self.aqualink, frame)
