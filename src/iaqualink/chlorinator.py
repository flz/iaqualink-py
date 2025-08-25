from __future__ import annotations
from typing import Any, Dict, Optional

from ..base import AqualinkDevice

class AqualinkChlorinator(AqualinkDevice):
    """Jandy AquaPure salt chlorinator (basic scaffold)."""

    DEVICE_TYPE = "chlorinator"  # used by factory/registry if applicable

    def __init__(self, name: str, data: Dict[str, Any], client):
        super().__init__(name, data, client)
        self._data = data

    # --- Read-only properties exposed by shadow/reported state ---
    @property
    def salinity_ppm(self) -> Optional[float]:
        v = self._data.get("salinity")
        return float(v) if v is not None else None

    @property
    def production_percent(self) -> Optional[int]:
        v = self._data.get("production")
        return int(v) if v is not None else None

    @property
    def status(self) -> Optional[str]:
        # e.g., "on", "off", "boost", or fault code string if available
        return self._data.get("status")

    # --- Mutations (async) ---
    async def set_production(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        payload = {"state": {"desired": {"equipment": {"swc_0": {"production": percent}}}}}
        await self._client.patch_device_shadow(self.serial, payload)

    async def set_enabled(self, enabled: bool) -> None:
        payload = {"state": {"desired": {"equipment": {"swc_0": {"enabled": bool(enabled)}}}}}
        await self._client.patch_device_shadow(self.serial, payload)

    async def set_boost(self, boost: bool) -> None:
        payload = {"state": {"desired": {"equipment": {"swc_0": {"boost": bool(boost)}}}}}
        await self._client.patch_device_shadow(self.serial, payload)

    async def refresh(self) -> None:
        shadow = await self._client.get_device_shadow(self.serial)
        reported = shadow.get("state", {}).get("reported", {})
        # adapt these keys to the actual shape once confirmed
        eq = reported.get("equipment", {}).get("swc_0", {})
        self._data.update({
            "salinity": eq.get("salinity"),
            "production": eq.get("production"),
            "status": eq.get("status") or ("on" if eq.get("enabled") else "off"),
        })

