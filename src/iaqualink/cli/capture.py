from __future__ import annotations

import asyncio
import atexit
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import httpx

from iaqualink.utils.capture import build_capture_entry
from iaqualink.utils.redact import mask_serial, redact_url


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
        entry = await build_capture_entry(response)
        entry["request"]["url"] = self._redact_url(entry["request"]["url"])
        async with self._lock:
            await asyncio.to_thread(self._write_line, json.dumps(entry) + "\n")
