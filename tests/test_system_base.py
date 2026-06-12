"""Tests for AqualinkSystem base-class contracts not covered by the conformance suite.

The conformance suite only parametrizes over concrete, supported system implementations.
These tests cover base-class behaviour: ABC enforcement and UnsupportedSystem routing.
"""

from __future__ import annotations

import httpx
import pytest
import respx.router

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem, UnsupportedSystem
from iaqualink.systems.i2d.system import I2D_CONTROL_URL
from iaqualink.systems.iaqua.system import IAQUA_SESSION_URL
from iaqualink.utils.diagnostics import _DIAGNOSTIC_SINK

from .conftest import load_fixture


class TestAqualinkSystemABC:
    def test_concrete_subclass_without_refresh_raises(self) -> None:
        """Subclassing AqualinkSystem without _refresh() raises TypeError."""

        with pytest.raises(TypeError):

            class _Incomplete(AqualinkSystem):  # type: ignore[abstract]
                pass

            _Incomplete(AqualinkClient("u", "p"), {"serial_number": "X"})


class TestUnsupportedSystem:
    def _make(self) -> UnsupportedSystem:
        client = AqualinkClient("u", "p")
        return UnsupportedSystem(
            client, {"serial_number": "SN001", "device_type": "unknown_xyz"}
        )

    def test_from_data_returns_unsupported_system(self) -> None:
        client = AqualinkClient("u", "p")
        system = AqualinkSystem.from_data(
            client, {"serial_number": "SN001", "device_type": "unknown_xyz"}
        )
        assert isinstance(system, UnsupportedSystem)

    def test_type_returns_raw_device_type_string(self) -> None:
        system = self._make()
        assert system.type == "unknown_xyz"

    def test_supported_is_false(self) -> None:
        system = self._make()
        assert system.supported is False


def _make_iaqua_system() -> AqualinkSystem:
    client = AqualinkClient("foo", "bar")
    return AqualinkSystem.from_data(
        client,
        {
            "id": 1,
            "serial_number": "SN123456",
            "name": "Pool",
            "device_type": "iaqua",
        },
    )


def _make_i2d_system() -> AqualinkSystem:
    client = AqualinkClient("foo", "bar")
    return AqualinkSystem.from_data(
        client,
        {
            "id": 1,
            "serial_number": "ABC123",
            "name": "Pump",
            "device_type": "i2d",
        },
    )


class TestDiagnose:
    async def test_iaqua_success(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system = _make_iaqua_system()

        home = load_fixture("iaqua", "session_get_home")
        devices = load_fixture("iaqua", "session_get_devices")
        onetouch = load_fixture("iaqua", "session_get_onetouch")
        bodies = {
            "get_home": home,
            "get_devices": devices,
            "get_onetouch": onetouch,
        }

        def _responder(request: httpx.Request) -> httpx.Response:
            command = request.url.params.get("command")
            return httpx.Response(200, json=bodies[command])

        respx_mock.route(url__startswith=IAQUA_SESSION_URL).mock(
            side_effect=_responder
        )

        result = await system.diagnose()

        assert result["status"] == "ONLINE"
        assert result["error"] is None
        assert result["system"]["serial"] == "***456"

        assert len(result["refresh_calls"]) == 3
        commands = {
            entry["request"]["url"].split("command=")[1].split("&")[0]
            for entry in result["refresh_calls"]
        }
        assert commands == {"get_home", "get_devices", "get_onetouch"}
        for entry in result["refresh_calls"]:
            assert "SN123456" not in entry["request"]["url"]
            assert entry["response"]["status_code"] == 200

        assert result["devices"]
        for device in result["devices"].values():
            assert "type" in device
            assert "label" in device
            assert "data" in device

    async def test_i2d_offline(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system = _make_i2d_system()

        respx_mock.route(url__startswith=f"{I2D_CONTROL_URL}/").mock(
            httpx.Response(
                500,
                json={"status": "500", "error": {"message": "Device offline."}},
            )
        )

        result = await system.diagnose()

        assert result["status"] == "OFFLINE"
        assert result["error"] is None
        assert len(result["refresh_calls"]) == 1
        assert result["refresh_calls"][0]["response"]["status_code"] == 500
        assert result["devices"] == {}

    async def test_i2d_online_redacts_serial_in_devices(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        # i2d's shared device data uses "name" for the system serial, and the
        # primary fan device is keyed by serial — both must be masked.
        system = _make_i2d_system()
        serial = system.serial

        alldata = load_fixture("i2d", "control_alldata_read")

        respx_mock.route(url__startswith=f"{I2D_CONTROL_URL}/").mock(
            httpx.Response(200, json=alldata)
        )

        result = await system.diagnose()

        assert serial not in result["devices"]
        masked = f"***{serial[-3:]}"
        assert masked in result["devices"]
        for device in result["devices"].values():
            assert device["data"].get("name") != serial

    async def test_iaqua_service_exception_sets_error(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system = _make_iaqua_system()

        respx_mock.route(url__startswith=IAQUA_SESSION_URL).mock(
            httpx.Response(500)
        )

        result = await system.diagnose()

        assert result["status"] == "DISCONNECTED"
        assert result["error"] is not None
        assert len(result["refresh_calls"]) == 1
        assert result["refresh_calls"][0]["response"]["status_code"] == 500

    async def test_diagnostic_sink_does_not_leak(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system = _make_iaqua_system()

        home = load_fixture("iaqua", "session_get_home")
        devices = load_fixture("iaqua", "session_get_devices")
        onetouch = load_fixture("iaqua", "session_get_onetouch")
        bodies = {
            "get_home": home,
            "get_devices": devices,
            "get_onetouch": onetouch,
        }

        def _responder(request: httpx.Request) -> httpx.Response:
            command = request.url.params.get("command")
            return httpx.Response(200, json=bodies[command])

        respx_mock.route(url__startswith=IAQUA_SESSION_URL).mock(
            side_effect=_responder
        )

        assert _DIAGNOSTIC_SINK.get() is None
        await system.refresh()
        assert _DIAGNOSTIC_SINK.get() is None

        await system.diagnose()
        assert _DIAGNOSTIC_SINK.get() is None
