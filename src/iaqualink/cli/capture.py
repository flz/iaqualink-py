from __future__ import annotations

import asyncio
import atexit
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

import httpx

from iaqualink.const import AQUALINK_LOGIN_URL, AQUALINK_REFRESH_URL
from iaqualink.utils.redact import (
    REDACT_KEYS_CI,
    mask_serial,
    redact_dict,
    redact_url,
    redact_value,
)

# "state" is PII (user address field) in auth responses but is the universal
# device on/off field in device API responses. Auth responses are never logged
# by the library, so REDACT_KEYS omits it to keep device debug logs useful.
# Capture writes all responses to disk, so auth responses need extra redaction.
_AUTH_EXTRA_KEYS_CI: frozenset[str] = frozenset({"state"})

_AUTH_CAPTURE_KEYS_CI: frozenset[str] = REDACT_KEYS_CI | _AUTH_EXTRA_KEYS_CI

_AUTH_URLS: frozenset[str] = frozenset(
    {AQUALINK_LOGIN_URL, AQUALINK_REFRESH_URL}
)


@dataclass
class CaptureSession:
    path: Path
    _file: IO[str] = field(init=False, repr=False)
    _literals: set[str] = field(init=False, repr=False, default_factory=set)
    _lock: asyncio.Lock = field(
        init=False, repr=False, default_factory=asyncio.Lock
    )

    def __post_init__(self) -> None:
        self._file = self.path.open("a", encoding="utf-8")
        atexit.register(self.close)

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def _write_line(self, line: str) -> None:
        self._file.write(line)
        self._file.flush()

    def register_serials(self, *serials: str) -> None:
        # Called after get_systems() resolves. Requests made before that point
        # (login, initial device list) are captured with serial numbers
        # unredacted in URLs. The device-list response body is still redacted
        # since serial_number is in REDACT_KEYS.
        self._literals.update(s for s in serials if s)

    def _redact_url(self, url: str) -> str:
        url = redact_url(url)
        for literal in self._literals:
            url = url.replace(literal, mask_serial(literal))
        return url

    def make_hooks(self) -> dict[str, list]:
        return {"response": [self._capture_response]}

    async def _capture_response(self, response: httpx.Response) -> None:
        await response.aread()
        request = response.request

        url_str = str(request.url)
        keys_ci = (
            _AUTH_CAPTURE_KEYS_CI if url_str in _AUTH_URLS else REDACT_KEYS_CI
        )

        req_body: Any = None
        if request.content:
            try:
                req_body = json.loads(request.content)
            except ValueError:
                req_body = (
                    request.content.decode("utf-8", errors="replace") or None
                )

        if isinstance(req_body, (dict, list)):
            req_body = redact_value(req_body, keys_ci)

        try:
            resp_body: Any = response.json()
        except Exception:
            resp_body = response.text or None

        if isinstance(resp_body, (dict, list)):
            resp_body = redact_value(resp_body, keys_ci)

        entry = {
            "timestamp": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "request": {
                "method": request.method,
                "url": self._redact_url(url_str),
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
        async with self._lock:
            await asyncio.to_thread(self._write_line, json.dumps(entry) + "\n")
