# iaqualink/systems/iaqua/system.py
# NOTE: Existing system discovery remains; AquaPure discovery is added.

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Existing imports for iaqua system (keep yours here)
try:
    from iaqualink.base import AqualinkSystem
except Exception:  # pragma: no cover
    AqualinkSystem = object  # minimal fallback for static analysis

# Import AquaPure entities implemented in iaqua/device.py
from .device import (
    IAquaAquapureProductionSwitch,
    IAquaAquapureBoostSwitch,
    IAquaAquapureProductionLevelNumber,
)

# ---------------------------------------------------------------------------
# Existing IAqua system class and device discovery go here…
# (All your current discovery for pumps/heaters/lights/etc. remains unchanged)
#
# class IAquaSystem(AqualinkSystem):
#     def _build_devices(self, topology: Dict[str, Any]) -> List[Any]:
#         ...
#         return devices
#
# For convenience, below is a minimal skeleton that shows where AquaPure plugs in.
# Replace/merge with your existing IAquaSystem class if different.


class IAquaSystem(AqualinkSystem):  # type: ignore[misc]
    """IAqua system manager. Builds concrete entity instances from topology."""

    def __init__(self, client, serial: str, data: Dict[str, Any] | None = None) -> None:
        super().__init__(client, serial, data or {})
        self._client = client
        self.serial = serial

    # ----------------------- AquaPure discovery -----------------------
    def _discover_aquapure(self, raw_dev: Dict[str, Any]) -> List[Any]:
        """
        Create AquaPure entities if a salt water chlorinator is present.

        Heuristics:
        - dev["type"] one of: chlorinator, aquapure, salt, swc, swcg
        - or explicit flag dev["has_swcg"] is True
        """
        dev_type = (raw_dev.get("type") or "").lower()
        is_swcg = dev_type in {"chlorinator", "aquapure", "salt", "swc", "swcg"} or bool(
            raw_dev.get("has_swcg")
        )
        if not is_swcg:
            return []

        serial = raw_dev.get("serial_number") or raw_dev.get("serial") or self.serial
        name_prefix = raw_dev.get("name") or "AquaPure"
        base = {"serial": serial}

        return [
            IAquaAquapureProductionSwitch(f"{name_prefix} Production", base, self._client),
            IAquaAquapureBoostSwitch(f"{name_prefix} Boost", base, self._client),
            IAquaAquapureProductionLevelNumber(f"{name_prefix} Level", base, self._client),
        ]

    # ----------------------- Main device builder -----------------------
    def _build_devices(self, topology: Dict[str, Any]) -> List[Any]:
        """
        Build the full set of IAqua entities from a topology dict.
        This method preserves existing entity creation and appends AquaPure.
        """
        devices: List[Any] = []

        # ---- Existing discovery (keep your current calls here) ----
        # for dev in topology.get("devices", []):
        #     devices.extend(self._discover_pumps(dev))
        #     devices.extend(self._discover_heaters(dev))
        #     devices.extend(self._discover_lights(dev))
        #     devices.extend(self._discover_sensors(dev))
        #     devices.extend(self._discover_aux(dev))
        #     ...
        # ------------------------------------------------------------

        # AquaPure discovery (additive)
        for dev in topology.get("devices", []):
            devices.extend(self._discover_aquapure(dev))

        return devices

