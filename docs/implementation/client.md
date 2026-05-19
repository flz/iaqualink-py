# Client Implementation Notes

Implementation details for `AqualinkClient` (`src/iaqualink/client.py`). For the wire-level auth protocol, see [Protocol Reference: Client](../reference/client.md).

## Sensitive Data Redaction

Two complementary mechanisms redact sensitive field values before they reach any log or output.

### `_REDACT_KEYS` — global redaction

Applied in both debug logging (`_redact_url`, `_redact_kwargs`) and CLI capture output. Covers fields that are sensitive in any context:

| Category | Fields |
|----------|--------|
| Auth tokens | `authentication_token`, `authorization`, `id_token`, `IdToken`, `refresh_token`, `session_id`, `sessionID` |
| AWS credentials | `AccessKeyId`, `IdentityId`, `SecretKey`, `SessionToken` |
| Auth config | `api_key`, `client_id`, `signature` |
| PII | `address`, `address_1`, `address_2`, `city`, `cookie`, `email`, `first_name`, `id`, `last_name`, `owner_id`, `phone`, `postal_code`, `serial`, `serial_number`, `serialnumber`, `ssid`, `user_id` |

`_REDACT_URL_RE` is built from this set and redacts matching query parameters in URLs.

`_redact_kwargs` applies a shallow walk to `json`, `params`, and `data` request body dicts. It is intentionally shallow: all outgoing request bodies in this library are flat dicts, so nested credential blocks never appear in requests.

### `AqualinkAuthState.__repr__`

Uses `_REDACT_KEYS` to decide which dataclass fields to mask. `username` is intentionally **not** in `_REDACT_KEYS` so that auth lifecycle INFO events (`Authenticated: user=…`, `Auth token refreshed: user=…`) remain useful for triage in multi-user environments.

### Capture-only redaction (`_CAPTURE_EXTRA_KEYS`)

Defined in `src/iaqualink/cli/capture.py`. Applied only to JSONL capture output, not to debug logs. Contains fields that are safe to show in debug context but should be redacted in shareable captures:

| Field | Reason excluded from `_REDACT_KEYS` |
|-------|--------------------------------------|
| `state` | Universal device on/off field throughout the protocol; redacting it globally would make device state invisible in debug logs |
| `username` | Must stay visible in auth INFO log events (see above) |
| `set-cookie` | Response header containing session cookies; not a request body field |

Capture output also applies **substring matching**: any key whose name contains `"token"`, `"secret"`, `"session"`, or `"credential"` is redacted, catching variants like `access_token` or `client_secret` without explicit enumeration.

### Email masking

In capture output, `email` and `username` fields are **partially masked** rather than fully replaced. The local part and domain label are individually truncated with `***`:

```
testuser@example.net  →  te***r@e***.net
ab@example.com        →  ***@e***.com
```

This preserves enough structure to identify the account without exposing the full address. Full `***` redaction is used in debug logs via `_redact_kwargs`.

### Serial numbers in URL paths

`_redact_url` only handles query parameters. Serial numbers that appear as URL path segments (e.g. `/v2/devices/{serial}/control.json`) are handled separately by `CaptureSession.register_serials()`, which is called after `get_systems()` resolves. Requests made before that point — login and the initial device list — are captured with serial numbers unredacted in URLs. The device-list response body is still redacted since `serial_number` is in `_REDACT_KEYS`.
