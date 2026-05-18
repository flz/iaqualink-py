from __future__ import annotations

import atexit
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

import httpx

from iaqualink.client import _REDACT_KEYS, _redact_url


def _redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    return {k: "***" if k in _REDACT_KEYS else v for k, v in d.items()}


@dataclass
class CaptureSession:
    path: Path
    _file: IO[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._file = self.path.open("a", encoding="utf-8")
        atexit.register(self.close)

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def make_hooks(self) -> dict[str, list]:
        return {"response": [self._capture_response]}

    async def _capture_response(self, response: httpx.Response) -> None:
        await response.aread()
        request = response.request

        try:
            req_body: Any = json.loads(request.content) if request.content else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            req_body = request.content.decode("utf-8", errors="replace") or None

        if isinstance(req_body, dict):
            req_body = _redact_dict(req_body)

        try:
            resp_body: Any = response.json()
        except Exception:
            resp_body = response.text or None

        if isinstance(resp_body, dict):
            resp_body = _redact_dict(resp_body)

        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "request": {
                "method": request.method,
                "url": _redact_url(str(request.url)),
                "headers": _redact_dict(dict(request.headers)),
                "body": req_body,
            },
            "response": {
                "status_code": response.status_code,
                "reason": response.reason_phrase,
                "headers": dict(response.headers),
                "body": resp_body,
            },
        }
        self._file.write(json.dumps(entry) + "\n")
        self._file.flush()
