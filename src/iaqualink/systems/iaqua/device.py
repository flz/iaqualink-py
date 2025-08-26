# iaqualink/systems/iaqua/device.py
# NOTE: Existing iaqua device/entity implementations remain untouched below.
#       AquaPure support is appended at the end under "AquaPure additions".

from __future__ import annotations

from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Existing imports for iaqua device types (keep your current ones here)
# Example (these may already exist in your file):
try:
    from iaqualink.base import AqualinkDevice
except Exception:  # pragma: no cover - keep repo import behavior
    AqualinkDevice = object  # minimal fallback for static analysis

# If your project exposes a specific toggle/switch base, import it.
# Fallback: use AqualinkDevice semantics and define is_on/turn_on/turn_off.
try:
    from iaqualink.toggle import AqualinkToggle
except Exception:  # pragma: no cover
    class AqualinkToggle(AqualinkDevice):  # type: ignore[misc]
        """Minimal fallback toggle base; replace with project toggle base if present."""

        @property
        def is_on(self) -> Optional[bool]:  # abstract
            raise NotImplementedError

        async def turn_on(self) -> None:  # abstract
            raise NotImplementedError

        async def turn_off(self) -> None:  # abstract
            raise NotImplementedError

        async def refresh(self) -> None:  # abstract
            raise NotImplementedError


# ---------------------------------------------------------------------------
# Existing iaqua device classes go here…
# (keep the rest of your file content exactly as-is)
# e.g., pumps, heaters, lights, sensors, aux toggles, etc.
#
# class IAquaPump(...): ...
# class IAquaHeater(...): ...
# ...


# ===========================================================================
#                           AquaPure additions
# ===========================================================================

# A tiny numeric base (kept local to iaqua) to avoid changing top-level package API.
class IAqualinkNumber(AqualinkDevice):  # type: ignore[misc]
    """Generic numeric entity (e.g., setpoints, percentages) for iaqua."""

    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0
    unit_of_measurement: Optional[str] = None

    @property
    def value(self) -> Optional[float]:  # abstract
        raise NotImplementedError

    async def set_value(self, value: float) -> None:  # abstract
        raise NotImplementedError


# ------ helpers for AquaPure device shadow (SWCG = salt water chlorinator) ------
_SWC_REPORTED_PATH: tuple[str, ...] = ("state", "reported", "equipment", "swc_0")


def _get_nested(d: Dict[str, Any], path: tuple[str, ...], default=None):
    cur: Any = d
    for k in path:
        cur = cur.get(k, {})
    return cur if cur != {} else default


def _desired(**fields) -> Dict[str, Any]:
    """
    Build the standard PATCH body:
    {"state":{"desired":{"equipment":{"swc_0":{ ...fields }}}}}
    """
    return {"state": {"desired": {"equipment": {"swc_0": fields}}}}


# ---------------- Switch: enable/disable chlorine production ----------------
class IAquaAquapureProductionSwitch(AqualinkToggle):  # type: ignore[misc]
    """Enable or disable chlorine production on the AquaPure chlorinator."""

    device_type = "aquapure_production_switch"

    @property
    def is_on(self) -> Optional[bool]:
        return self._data.get("enabled")

    async def turn_on(self) -> None:
        await self._client.patch_device_shadow(self.serial, _desired(enabled=True))
        await self.refresh()

    async def turn_off(self) -> None:
        await self._client.patch_device_shadow(self.serial, _desired(enabled=False))
        await self.refresh()

    async def refresh(self) -> None:
        shadow = await self._client.get_device_shadow(self.serial)
        eq = _get_nested(shadow, _SWC_REPORTED_PATH, {}) or {}
        self._data.update({"enabled": eq.get("enabled")})


# ---------------- Switch: Boost / super-chlorinate ----------------
class IAquaAquapureBoostSwitch(AqualinkToggle):  # type: ignore[misc]
    """Toggle Boost (super-chlorinate) mode."""

    device_type = "aquapure_boost_switch"

    @property
    def is_on(self) -> Optional[bool]:
        return self._data.get("boost")

    async def turn_on(self) -> None:
        await self._client.patch_device_shadow(self.serial, _desired(boost=True))
        await self.refresh()

    async def turn_off(self) -> None:
        await self._client.patch_device_shadow(self.serial, _desired(boost=False))
        await self.refresh()

    async def refresh(self) -> None:
        shadow = await self._client.get_device_shadow(self.serial)
        eq = _get_nested(shadow, _SWC_REPORTED_PATH, {}) or {}
        self._data.update({"_

