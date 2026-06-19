# Vortrax Implementation Notes

Vortrax (`device_type: "vortrax"`) is a thin subclass of `VrSystem`. For full read/write semantics, see [Implementation Notes: vr](vr.md).

## Overview

| Property | Value |
|---|---|
| `device_type` | `vortrax` |
| Parent class | `VrSystem` |
| Python class | `VortraxSystem` in `src/iaqualink/systems/vortrax/system.py` |
| API host | `prod.zodiac-io.com` (same as vr) |
| WebSocket namespace | `vortrax` (overrides vr's `"vr"`) |

## Delta vs VR

Two changes relative to `VrSystem`:

1. **`namespace = "vortrax"`** — ClassVar override. All WebSocket write frames use `"namespace": "vortrax"` instead of `"namespace": "vr"`.

2. **`product_number` device** — `_parse_shadow_response` calls `super()` then reads `state.reported.eboxData.completeCleanerPn`. If present, surfaces it as a `VrDevice` named `product_number`. Absent `eboxData` or absent key → device is silently omitted (no crash).

Everything else — shadow endpoint, device model, write commands, error handling — is identical to vr.

## See Also

- [Implementation Notes: vr](vr.md) — full read/write semantics
- [API Reference: vortrax](../../api/systems/vortrax.md)
- [Protocol Reference: vortrax](../../reference/systems/vortrax.md)
