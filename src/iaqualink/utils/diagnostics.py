from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

import httpx

from iaqualink.utils.capture import build_capture_entry

# Set by start_capture() for the duration of a refresh(); read by
# AqualinkClient.send_request() to record redacted request/response traffic.
# None (the default) means no diagnose() call is in progress.
_DIAGNOSTIC_SINK: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "_iaqualink_diagnostic_sink", default=None
)


def start_capture() -> Token[list[dict[str, Any]] | None]:
    """Start recording request/response traffic for AqualinkSystem.diagnose()."""
    return _DIAGNOSTIC_SINK.set([])


def stop_capture(
    token: Token[list[dict[str, Any]] | None],
) -> list[dict[str, Any]]:
    """Stop recording and return the captures collected since start_capture()."""
    captures = _DIAGNOSTIC_SINK.get() or []
    _DIAGNOSTIC_SINK.reset(token)
    return captures


async def record_response(response: httpx.Response) -> None:
    sink = _DIAGNOSTIC_SINK.get()
    if sink is not None:
        sink.append(await build_capture_entry(response))
