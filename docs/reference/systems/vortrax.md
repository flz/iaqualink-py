# vortrax — Protocol Reference

**Python system name:** `"vortrax"`
**Protocol family:** AWS IoT shadow (REST polling for reads; WebSocket for writes)
**Endpoints:** Same as [vr](vr.md) — substitute `"vortrax"` wherever vr says `"vr"` in WebSocket frames.

---

## Delta vs vr

Only one wire-level difference: the WebSocket `namespace` field.

| Field | vr | vortrax |
|---|---|---|
| WS frame `namespace` | `"vr"` | `"vortrax"` |

All REST endpoints, shadow schema, state enums, cycle enums, and remote control enums are identical to [vr](vr.md).

---

## Extra Reported Field

Vortrax shadows may include `state.reported.eboxData.completeCleanerPn` (a string), which is surfaced as the `product_number` device. This field is absent in vr shadows.

| Path | Device key | Type |
|---|---|---|
| `state.reported.eboxData.completeCleanerPn` | `product_number` | string |

---

## See Also

- [vr Protocol Reference](vr.md) — full wire spec (endpoints, shadow schema, write frames)
- [Implementation Notes: vortrax](../../implementation/systems/vortrax.md)
