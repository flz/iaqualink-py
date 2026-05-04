from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from iaqualink.systems.vr.system import VrSystem

if TYPE_CHECKING:
    import httpx

VORTRAX_NAMESPACE = "vortrax"


class VortraxSystem(VrSystem):
    NAME = "vortrax"
    namespace: ClassVar[str] = VORTRAX_NAMESPACE

    def _parse_shadow_response(self, response: httpx.Response) -> None:
        super()._parse_shadow_response(response)
        # Vortrax-only: surface the product-number string from eboxData
        # (separate from the numeric `id`-based model number).
        try:
            data = response.json()
            ebox = data["state"]["reported"].get("eboxData") or {}
            pn = ebox.get("completeCleanerPn")
        except (KeyError, TypeError, ValueError):
            pn = None
        if pn is not None:
            payload: dict[str, Any] = {
                "name": "product_number",
                "state": pn,
            }
            from iaqualink.systems.vr.device import VrDevice

            if "product_number" in self.devices:
                self.devices["product_number"].data.update(payload)
            else:
                self.devices["product_number"] = VrDevice.from_data(
                    self, payload
                )
