from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from iaqualink.system import AqualinkSystem
from iaqualink.systems.vortrax.system import VortraxSystem
from iaqualink.systems.vr.const import VR_STATE_CLEANING


def _system() -> VortraxSystem:
    aqualink = MagicMock()
    aqualink.user_id = "u"
    aqualink.id_token = "tok"
    aqualink.authentication_token = "at"
    aqualink.app_client_id = "app"
    sys = AqualinkSystem.from_data(
        aqualink,
        {
            "id": 999,
            "serial_number": "VTX-1",
            "device_type": "vortrax",
            "name": "vac",
        },
    )
    assert isinstance(sys, VortraxSystem)
    return sys


class TestVortraxSystem(unittest.IsolatedAsyncioTestCase):
    def test_from_data_dispatches(self) -> None:
        _ = _system()

    def test_namespace_is_vortrax(self) -> None:
        sys = _system()
        assert sys.namespace == "vortrax"

    async def test_start_uses_vortrax_namespace(self) -> None:
        sys = _system()
        with patch(
            "iaqualink.systems.vr.ws.send_set_state",
            new_callable=AsyncMock,
        ) as send:
            await sys.start_cleaning()
            send.assert_awaited_once_with(
                sys.aqualink,
                sys.serial,
                VR_STATE_CLEANING,
                namespace="vortrax",
            )

    def test_parse_surfaces_product_number_from_ebox(self) -> None:
        sys = _system()
        response = MagicMock()
        response.json.return_value = {
            "state": {
                "reported": {
                    "eboxData": {"completeCleanerPn": "WR-PN-9000"},
                    "equipment": {
                        "robot": {
                            "state": 0,
                            "prCyc": 1,
                            "cycleStartTime": 0,
                            "durations": {"a": 90, "b": 150},
                        }
                    },
                }
            }
        }
        sys._parse_shadow_response(response)
        assert sys.devices["product_number"].state == "WR-PN-9000"
