"""TCX WebSocket support: state subscription (reads) + command frames (writes).

Per the reference app, the REST shadow endpoint is only used as a one-shot
online/offline status check on the system list screen — live state and
commands both go over the shared wss transport
(`AqualinkClient.ws_connect`/`send_ws_frame`). tcx has no "robot" wrapper
concept — its shadow is a flat multi-key tree scoped across ~9 namespaces
(see docs/reference/systems/tcx.md), so it builds directly on the generic
`WsStateSubscription` engine rather than the robot-shaped mixin.

Confirmed from live wire traffic: the Authorization full-state payload is
namespace-keyed — `{<ns>: {"state": {"reported": {...}}, ...}, ...}` for
namespaces `main`, `filt`, `ecm`, `pib0`, `zig`, `fea`, `sched`, `scene` —
not a single flat `payload.state.reported` as originally assumed. Each
namespace's `reported` tree merges into one flat dict, matching what
`_update_devices`/`_parse_fea_sub_shadow`/`_parse_zig_sub_shadow` expect.
`StateStreamer`/`DataStreamer`/`EventStreamer` delta payload shape has not
been directly observed — `_reported_from_payload` supports both the flat and
namespace-keyed shapes so either works if/when confirmed. See "Not Observed /
Needs Verification" in docs/reference/systems/tcx.md and "Deltas vs Protocol
Reference" in docs/implementation/systems/tcx.md.
"""

from __future__ import annotations

__all__ = [
    "NAMESPACE_FEATURE_CIRCUIT",
    "NAMESPACE_FILTRATION",
    "NAMESPACE_PIB",
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
NAMESPACE_PIB = "pib"

# Push services that carry state deltas (Authorization carries full state and
# is handled separately by the generic engine).
_TCX_WS_DELTA_SERVICES = frozenset(
    {"StateStreamer", "DataStreamer", "EventStreamer"}
)


def _reported_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract/merge the reported-state tree from a tcx WS frame payload.

    Confirmed on real hardware: the Authorization full-state payload is
    namespace-keyed (`main`, `filt`, `ecm`, `pib0`, `zig`, `fea`, `sched`,
    `scene`), each holding its own `state.reported`/`state.desired`/
    `metadata`/`version`/`timestamp` — not a single flat
    `payload["state"]["reported"]`. Every namespace's reported tree is
    merged into one flat dict (no observed key collisions across
    namespaces on real data).

    Delta-frame (StateStreamer/DataStreamer/EventStreamer) shape hasn't
    been directly observed, so a flat `payload.state.reported` is checked
    first (in case a delta arrives that way) before falling back to the
    namespace-merge — either shape resolves correctly.
    """
    direct = (payload.get("state") or {}).get("reported")
    if isinstance(direct, dict) and direct:
        return direct

    merged: dict[str, Any] = {}
    for value in payload.values():
        if not isinstance(value, dict):
            continue
        reported = (value.get("state") or {}).get("reported")
        if isinstance(reported, dict):
            merged.update(reported)
    return merged or None


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
        return _reported_from_payload(frame.get("payload") or {})

    def _ws_delta_from_frame(
        self, frame: dict[str, Any]
    ) -> dict[str, Any] | None:
        if frame.get("service") not in _TCX_WS_DELTA_SERVICES:
            return None
        return _reported_from_payload(frame.get("payload") or {})

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
