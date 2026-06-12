from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import httpx

from iaqualink.utils.capture import build_capture_entry

# Set by AqualinkSystem.diagnose() for the duration of a refresh(); read by
# AqualinkClient.send_request() to record redacted request/response traffic.
# None (the default) means no diagnose() call is in progress.
_DIAGNOSTIC_SINK: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "_iaqualink_diagnostic_sink", default=None
)


async def record_response(response: httpx.Response) -> None:
    sink = _DIAGNOSTIC_SINK.get()
    if sink is not None:
        sink.append(await build_capture_entry(response))
