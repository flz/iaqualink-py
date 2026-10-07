from __future__ import annotations

import datetime
import json
from typing import Any

import httpx

from iaqualink.const import AQUALINK_LOGIN_URL, AQUALINK_REFRESH_URL
from iaqualink.utils.redact import (
    REDACT_KEYS_CI,
    redact_dict,
    redact_url,
    redact_value,
)

# "state" is PII (user address field) in auth responses but is the universal
# device on/off field in device API responses. Auth responses are never logged
# by the library, so REDACT_KEYS omits it to keep device debug logs useful.
# Capturing auth responses needs the extra redaction.
_AUTH_EXTRA_KEYS_CI: frozenset[str] = frozenset({"state"})

_AUTH_CAPTURE_KEYS_CI: frozenset[str] = REDACT_KEYS_CI | _AUTH_EXTRA_KEYS_CI

_AUTH_URLS: frozenset[str] = frozenset(
    {AQUALINK_LOGIN_URL, AQUALINK_REFRESH_URL}
)


async def build_capture_entry(response: httpx.Response) -> dict[str, Any]:
    """Convert an httpx response (and its request) into a redacted dict.

    Shared by the CLI's ``--capture`` flag and ``AqualinkSystem.diagnose()``.
    The returned ``request.url`` has only query-string values redacted
    (via :func:`redact_url`); callers that need to mask serials embedded in
    URL paths must do so themselves.
    """
    await response.aread()
    request = response.request

    url_str = str(request.url)
    keys_ci = _AUTH_CAPTURE_KEYS_CI if url_str in _AUTH_URLS else REDACT_KEYS_CI

    req_body: Any = None
    if request.content:
        try:
            req_body = json.loads(request.content)
        except ValueError:
            req_body = request.content.decode("utf-8", errors="replace") or None

    if isinstance(req_body, (dict, list)):
        req_body = redact_value(req_body, keys_ci)

    try:
        resp_body: Any = response.json()
    except Exception:
        resp_body = response.text or None

    if isinstance(resp_body, (dict, list)):
        resp_body = redact_value(resp_body, keys_ci)

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "request": {
            "method": request.method,
            "url": redact_url(url_str),
            "headers": redact_dict(dict(request.headers), keys_ci),
            "body": req_body,
        },
        "response": {
            "status_code": response.status_code,
            "reason": response.reason_phrase,
            "headers": redact_dict(dict(response.headers), keys_ci),
            "body": resp_body,
        },
    }
