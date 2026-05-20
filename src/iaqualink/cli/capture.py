from __future__ import annotations

import asyncio
import atexit
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

import httpx

from iaqualink.utils.redact import (
    REDACT_KEYS,
    mask_serial,
    redact_dict,
    redact_url,
    redact_value,
)

# Fields redacted only in capture output (safe to show in debug logs).
# "state" is PII in user-profile context but is the universal device on/off
# field in device API responses — keeping it in REDACT_KEYS would redact
# device state throughout debug logging and make captures useless for
# diagnosing device issues.
# "username" is the email used for login; auth INFO events now mask it via
# mask_email(), but it stays capture-only so device state bodies aren't affected.
_CAPTURE_EXTRA_KEYS: frozenset[str] = frozenset(
    {"set-cookie", "state", "username"}
)

_CAPTURE_KEYS_CI: frozenset[str] = frozenset(
    k.lower() for k in (*REDACT_KEYS, *_CAPTURE_EXTRA_KEYS)
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

        req_body: Any = None
        if request.content:
            try:
                req_body = json.loads(request.content)
            except ValueError:
                req_body = (
                    request.content.decode("utf-8", errors="replace") or None
                )

        if isinstance(req_body, (dict, list)):
            req_body = redact_value(req_body, _CAPTURE_KEYS_CI)

        try:
            resp_body: Any = response.json()
        except Exception:
            resp_body = response.text or None

        if isinstance(resp_body, (dict, list)):
            resp_body = redact_value(resp_body, _CAPTURE_KEYS_CI)

        entry = {
            "timestamp": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "request": {
                "method": request.method,
                "url": self._redact_url(str(request.url)),
                "headers": redact_dict(dict(request.headers), _CAPTURE_KEYS_CI),
                "body": req_body,
            },
            "response": {
                "status_code": response.status_code,
                "reason": response.reason_phrase,
                "headers": redact_dict(
                    dict(response.headers), _CAPTURE_KEYS_CI
                ),
                "body": resp_body,
            },
        }
        async with self._lock:
            await asyncio.to_thread(self._write_line, json.dumps(entry) + "\n")
