from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence


def sign(parts: Sequence[str], secret: str) -> str:
    if not parts:
        raise ValueError("parts must be non-empty")
    message = ",".join(parts)
    return hmac.new(secret.encode(), message.encode(), hashlib.sha1).hexdigest()
