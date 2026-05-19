from __future__ import annotations

import asyncio
import atexit
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

import httpx

from iaqualink.client import _REDACT_KEYS, _redact_url

# Fields redacted only in capture output (safe to show in debug logs).
# "state" is PII in user-profile context but is the universal device on/off
# field in device API responses — keeping it in _REDACT_KEYS would redact
# device state throughout debug logging and make captures useless for
# diagnosing device issues.
# "username" is the email used for login; it must remain visible in auth
# INFO log events per the logging contract in docs/contributing/setup.md.
_CAPTURE_EXTRA_KEYS: frozenset[str] = frozenset(
    {"set-cookie", "state", "username"}
)

_REDACT_KEYS_CI = frozenset(
    k.lower() for k in (*_REDACT_KEYS, *_CAPTURE_EXTRA_KEYS)
)
_REDACT_SUBSTRINGS = ("credential", "secret", "session", "token")

# Keys whose string values are partially masked rather than fully replaced.
_EMAIL_KEYS: frozenset[str] = frozenset({"email", "username"})


def _mask_email(value: str) -> str:
    """Partially mask an email: fl***t@t***.net — preserves enough to identify the account."""
    if "@" not in value:
        return "***"
    local, domain = value.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = "***"
    elif len(local) <= 5:
        masked_local = local[:1] + "***"
    else:
        masked_local = local[:2] + "***" + local[-1:]
    domain_parts = domain.split(".", 1)
    masked_domain = domain_parts[0][:1] + "***"
    if len(domain_parts) > 1:
        masked_domain += "." + domain_parts[1]
    return f"{masked_local}@{masked_domain}"


def _redact_value(v: Any) -> Any:
    if isinstance(v, dict):
        return _redact_dict(v)
    if isinstance(v, list):
        return [_redact_value(item) for item in v]
    return v


def _redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in d.items():
        k_lower = k.lower()
        if k_lower in _EMAIL_KEYS and isinstance(v, str):
            result[k] = _mask_email(v)
        elif k_lower in _REDACT_KEYS_CI or any(
            s in k_lower for s in _REDACT_SUBSTRINGS
        ):
            result[k] = "***"
        else:
            result[k] = _redact_value(v)
    return result


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
        # since serial_number is in _REDACT_KEYS.
        self._literals.update(s for s in serials if s)

    def _redact_url(self, url: str) -> str:
        url = _redact_url(url)
        for literal in self._literals:
            url = url.replace(literal, "***")
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
            req_body = _redact_value(req_body)

        try:
            resp_body: Any = response.json()
        except Exception:
            resp_body = response.text or None

        if isinstance(resp_body, (dict, list)):
            resp_body = _redact_value(resp_body)

        entry = {
            "timestamp": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "request": {
                "method": request.method,
                "url": self._redact_url(str(request.url)),
                "headers": _redact_dict(dict(request.headers)),
                "body": req_body,
            },
            "response": {
                "status_code": response.status_code,
                "reason": response.reason_phrase,
                "headers": _redact_dict(dict(response.headers)),
                "body": resp_body,
            },
        }
        async with self._lock:
            await asyncio.to_thread(self._write_line, json.dumps(entry) + "\n")
