from __future__ import annotations

import re
from typing import Any

_REDACT_KEYS: frozenset[str] = frozenset(
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
        "ssid",
        "user_id",
    }
)

_REDACT_KEYS_CI: frozenset[str] = frozenset(k.lower() for k in _REDACT_KEYS)

# Key names containing these substrings are always fully redacted.
_REDACT_SUBSTRINGS: tuple[str, ...] = ("credential", "secret", "session", "token")

# Keys whose string values are partially masked rather than fully replaced.
_EMAIL_KEYS: frozenset[str] = frozenset({"email", "username"})

_REDACT_URL_RE = re.compile(
    r"(?<=[?&])(" + "|".join(sorted(_REDACT_KEYS)) + r")=[^&]*"
)


def _mask_email(value: str) -> str:
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


def _redact_value(v: Any, keys_ci: frozenset[str] = _REDACT_KEYS_CI) -> Any:
    if isinstance(v, dict):
        return _redact_dict(v, keys_ci)
    if isinstance(v, list):
        return [_redact_value(item, keys_ci) for item in v]
    return v


def _redact_dict(
    d: dict[str, Any], keys_ci: frozenset[str] = _REDACT_KEYS_CI
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in d.items():
        k_lower = k.lower()
        if k_lower in _EMAIL_KEYS and isinstance(v, str):
            result[k] = _mask_email(v)
        elif k_lower in keys_ci or any(s in k_lower for s in _REDACT_SUBSTRINGS):
            result[k] = "***"
        else:
            result[k] = _redact_value(v, keys_ci)
    return result


def _redact_url(url: str) -> str:
    return _REDACT_URL_RE.sub(r"\1=***", url)


def _redact_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    for key in ("json", "params", "data"):
        if key in out and isinstance(out[key], dict):
            out[key] = _redact_dict(out[key])
    return out
