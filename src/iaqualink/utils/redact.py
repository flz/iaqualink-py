from __future__ import annotations

import re
from typing import Any

REDACT_KEYS: frozenset[str] = frozenset(
    {
        # auth tokens & credentials
        "AccessKeyId",
        "IdToken",
        "IdentityId",
        "SecretKey",
        "SessionToken",
        "api_key",
        "authentication_token",
        "authorization",
        "client_id",
        "id_token",
        "password",
        "refresh_token",
        "session_id",
        "sessionID",
        "signature",
        # PII / session
        "address",
        "address_1",
        "address_2",
        "city",
        "cookie",
        "email",
        "id",
        "first_name",
        "last_name",
        "phone",
        "postal_code",
        "owner_id",
        "serial",
        "serial_number",
        "serialnumber",
        "set-cookie",
        "ssid",
        "user_id",
        "username",
    }
)

REDACT_KEYS_CI: frozenset[str] = frozenset(k.lower() for k in REDACT_KEYS)

# Key names containing these substrings are always fully redacted.
REDACT_SUBSTRINGS: tuple[str, ...] = (
    "credential",
    "secret",
    "session",
    "token",
)

# Keys whose string values are partially masked rather than fully replaced.
_EMAIL_KEYS: frozenset[str] = frozenset({"email", "username"})
_SERIAL_KEYS: frozenset[str] = frozenset(
    {"serial", "serial_number", "serialnumber"}
)

_REDACT_URL_RE = re.compile(
    r"(?<=[?&])(" + "|".join(sorted(REDACT_KEYS)) + r")=[^&]*"
)


def mask_email(value: str) -> str:
    # fl***t@t***.net — preserves enough to identify the account
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


def mask_serial(value: str) -> str:
    # ABCDEFGHIJKL → ***JKL  (last 3 chars preserved)
    if len(value) <= 3:
        return "***"
    return "***" + value[-3:]


def redact_value(v: Any, keys_ci: frozenset[str] = REDACT_KEYS_CI) -> Any:
    if isinstance(v, dict):
        return redact_dict(v, keys_ci)
    if isinstance(v, list):
        return [redact_value(item, keys_ci) for item in v]
    return v


def redact_dict(
    d: dict[str, Any], keys_ci: frozenset[str] = REDACT_KEYS_CI
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in d.items():
        k_lower = k.lower()
        if k_lower in _EMAIL_KEYS and isinstance(v, str):
            result[k] = mask_email(v)
        elif k_lower in _SERIAL_KEYS and isinstance(v, str):
            result[k] = mask_serial(v)
        elif k_lower in keys_ci or any(s in k_lower for s in REDACT_SUBSTRINGS):
            result[k] = "***"
        else:
            result[k] = redact_value(v, keys_ci)
    return result


def redact_url(url: str) -> str:
    return _REDACT_URL_RE.sub(r"\1=***", url)


def redact_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    # Always uses base REDACT_KEYS_CI. Capture uses URL-aware key sets via
    # redact_dict() / redact_value() directly, so no keys_ci parameter needed.
    out = dict(kwargs)
    for key in ("json", "params", "data"):
        if key in out and isinstance(out[key], dict):
            out[key] = redact_dict(out[key])
    return out
