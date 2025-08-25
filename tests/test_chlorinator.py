import asyncio
import pytest

from iaqualink.devices.chlorinator import AqualinkChlorinator

class DummyClient:
    def __init__(self, shadow):
        self._shadow = shadow
        self.patched = None

    async def get_device_shadow(self, serial):
        return self._shadow

    async def patch_device_shadow(self, serial, body):
        self.patched = body
        return {"ok": True}

@pytest.mark.asyncio
async def test_refresh_and_properties():
    shadow = {
        "state": {
            "reported": {
                "equipment": {
                    "swc_0": {"salinity": 3200, "production": 45, "enabled": True, "status": "on"}
                }
            }
        }
    }
    c = AqualinkChlorinator("Chlorinator", {"type": "chlorinator", "serial": "ABC"}, DummyClient(shadow))
    c.serial = "ABC"  # usually set by base class/loader
    await c.refresh()
    assert c.salinity_ppm == 3200
    assert c.production_percent == 45
    assert c.status == "on"

@pytest.mark.asyncio
async def test_setters_bound_production():
    c = AqualinkChlorinator("Chlorinator", {"type": "chlorinator", "serial": "ABC"}, DummyClient({"state":{"reported":{}}}))
    c.serial = "ABC"
    await c.set_production(150)  # clamps to 100
    assert c._client.patched["state"]["desired"]["equipment"]["swc_0"]["production"] == 100

