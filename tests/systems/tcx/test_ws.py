"""Tests for TCX WS state subscription (reads) and command frames (writes)."""

from __future__ import annotations

import json
import unittest
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.system import TcxSystem
from iaqualink.systems.tcx.ws import (
    NAMESPACE_FEATURE_CIRCUIT,
    NAMESPACE_FILTRATION,
    NAMESPACE_PIB,
    NAMESPACE_SWC,
    NAMESPACE_TCX,
    NAMESPACE_ZIGBEE,
)
from iaqualink.utils.websockets import SERVICE_AUTHORIZATION

SAMPLE_REPORTED: dict[str, Any] = {
    "sn": "ABCDEFG",
    "systemMode": 0,
    "tempSetting": 1,
    "aws": {"status": "connected", "timestamp": 123},
    "equipment": {"filt": {"present": True}, "ecm": {"present": True}},
    "filt0": {"st": 1, "en": 1, "fr": "Filter Pump"},
    "ecm0": {"cmdSpd": 2700, "minSpd": 1000, "maxSpd": 3450, "st": 1, "en": 1},
}


def _make_tcx_system() -> tuple[AqualinkClient, TcxSystem]:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "ABCDEFG",
        "device_type": "tcx",
        "name": "Pool",
    }
    sut = cast(TcxSystem, AqualinkSystem.from_data(client, data=data))
    return client, sut


def _auth_frame(reported: dict[str, Any]) -> dict[str, Any]:
    # Flat shape — kept as one of the two shapes _reported_from_payload
    # supports (the namespace-keyed shape confirmed on real hardware is
    # covered separately by _namespaced_auth_frame below).
    return {
        "service": SERVICE_AUTHORIZATION,
        "target": "ABCDEFG",
        "namespace": "authorization",
        "payload": {"state": {"reported": reported}},
    }


def _namespaced_auth_frame(
    **namespaces: dict[str, Any],
) -> dict[str, Any]:
    # Confirmed on real hardware: the Authorization full-state payload is
    # namespace-keyed, e.g. namespaces=dict(main={...}, filt={...}).
    return {
        "service": SERVICE_AUTHORIZATION,
        "target": "ABCDEFG",
        "namespace": "authorization",
        "payload": {
            ns: {
                "state": {"reported": reported},
                "metadata": {},
                "version": 1,
                "timestamp": 123,
            }
            for ns, reported in namespaces.items()
        },
    }


def _delta_frame(
    delta: dict[str, Any], service: str = "StateStreamer"
) -> dict[str, Any]:
    return {
        "service": service,
        "target": "ABCDEFG",
        "namespace": "filtration",
        "payload": {"state": {"reported": delta}},
    }


class TestTcxWsFullStateFromFrame:
    def test_authorization_frame_returns_reported(self) -> None:
        _, sut = _make_tcx_system()
        frame = _auth_frame(SAMPLE_REPORTED)
        assert sut._ws_full_state_from_frame(frame) == SAMPLE_REPORTED

    def test_wrong_service_returns_none(self) -> None:
        _, sut = _make_tcx_system()
        frame = _delta_frame(SAMPLE_REPORTED)
        assert sut._ws_full_state_from_frame(frame) is None

    def test_missing_payload_returns_none(self) -> None:
        _, sut = _make_tcx_system()
        frame = {"service": SERVICE_AUTHORIZATION}
        assert sut._ws_full_state_from_frame(frame) is None

    def test_empty_reported_returns_none(self) -> None:
        _, sut = _make_tcx_system()
        frame = _auth_frame({})
        assert sut._ws_full_state_from_frame(frame) is None

    def test_non_dict_reported_returns_none(self) -> None:
        _, sut = _make_tcx_system()
        frame = {
            "service": SERVICE_AUTHORIZATION,
            "payload": {"state": {"reported": "nope"}},
        }
        assert sut._ws_full_state_from_frame(frame) is None


class TestTcxWsFullStateNamespacedPayload:
    # Confirmed on real hardware: the Authorization full-state payload is
    # namespace-keyed, not the flat payload.state.reported shape.

    def test_merges_reported_across_namespaces(self) -> None:
        _, sut = _make_tcx_system()
        frame = _namespaced_auth_frame(
            main={
                "sn": "ABCDEFG",
                "systemMode": 0,
                "tempSetting": 1,
                "aws": {"status": "connected"},
            },
            filt={"filt0": {"st": 1, "en": 1, "fr": "Filter Pump"}},
            ecm={"ecm0": {"cmdSpd": 2700, "st": 1}},
            pib0={
                "water": {"value": 820, "us": "VALID"},
                "air": {"value": 720, "snsr": "air"},
                "aux0": {"st": 0},
            },
            zig={
                "zig": {"st": 1, "op": 0, "euid": "0011223344556677"},
                "auxz0": {"st": 1, "fr": "Pool Light"},
            },
            fea={"feaCircuit0": {"st": 0, "en": 1, "fr": "Spa Jets"}},
        )
        reported = sut._ws_full_state_from_frame(frame)
        assert reported is not None
        assert reported["sn"] == "ABCDEFG"
        assert reported["filt0"] == {"st": 1, "en": 1, "fr": "Filter Pump"}
        assert reported["ecm0"]["cmdSpd"] == 2700
        assert reported["water"]["value"] == 820
        assert reported["aux0"] == {"st": 0}
        assert reported["zig"] == {"st": 1, "op": 0, "euid": "0011223344556677"}
        assert reported["auxz0"] == {"st": 1, "fr": "Pool Light"}
        assert reported["feaCircuit0"]["fr"] == "Spa Jets"

    def test_non_dict_namespace_values_are_skipped(self) -> None:
        _, sut = _make_tcx_system()
        frame = {
            "service": SERVICE_AUTHORIZATION,
            "payload": {
                "main": {"state": {"reported": {"sn": "ABCDEFG"}}},
                "data": [1, 2, 3],
                "ota": {"jobId": None},
            },
        }
        reported = sut._ws_full_state_from_frame(frame)
        assert reported == {"sn": "ABCDEFG"}

    def test_all_namespaces_empty_returns_none(self) -> None:
        _, sut = _make_tcx_system()
        frame = {
            "service": SERVICE_AUTHORIZATION,
            "payload": {"sched": {"state": {"reported": {}}}},
        }
        assert sut._ws_full_state_from_frame(frame) is None

    def test_end_to_end_populates_devices_from_all_namespaces(self) -> None:
        _, sut = _make_tcx_system()
        frame = _namespaced_auth_frame(
            main={
                "sn": "ABCDEFG",
                "systemMode": 0,
                "tempSetting": 1,
                "aws": {"status": "connected"},
            },
            filt={"filt0": {"st": 1, "en": 1, "fr": "Filter Pump"}},
            fea={"feaCircuit0": {"st": 0, "en": 1, "fr": "Spa Jets"}},
            zig={
                "zig": {"st": 1, "op": 0, "euid": "0011223344556677"},
                "auxz0": {"st": 1, "fr": "Pool Light"},
            },
        )
        assert sut._apply_ws_frame(frame) is True
        assert sut.status is SystemStatus.CONNECTED
        assert sut.devices["filt0"].data["st"] == 1
        assert "feaCircuit0" in sut.devices
        assert "auxz0" in sut.devices


class TestTcxWsDeltaFromFrame:
    def test_state_streamer_returns_delta(self) -> None:
        _, sut = _make_tcx_system()
        delta = {"filt0": {"st": 0}}
        frame = _delta_frame(delta, service="StateStreamer")
        assert sut._ws_delta_from_frame(frame) == delta

    def test_data_streamer_returns_delta(self) -> None:
        _, sut = _make_tcx_system()
        delta = {"filt0": {"st": 0}}
        frame = _delta_frame(delta, service="DataStreamer")
        assert sut._ws_delta_from_frame(frame) == delta

    def test_event_streamer_returns_delta(self) -> None:
        _, sut = _make_tcx_system()
        delta = {"filt0": {"st": 0}}
        frame = _delta_frame(delta, service="EventStreamer")
        assert sut._ws_delta_from_frame(frame) == delta

    def test_error_streamer_returns_none(self) -> None:
        _, sut = _make_tcx_system()
        delta = {"filt0": {"st": 0}}
        frame = _delta_frame(delta, service="ErrorStreamer")
        assert sut._ws_delta_from_frame(frame) is None

    def test_authorization_service_returns_none(self) -> None:
        # Handled by the full-state branch, not this one.
        _, sut = _make_tcx_system()
        frame = _delta_frame(SAMPLE_REPORTED, service=SERVICE_AUTHORIZATION)
        assert sut._ws_delta_from_frame(frame) is None

    def test_empty_reported_returns_none(self) -> None:
        _, sut = _make_tcx_system()
        frame = _delta_frame({})
        assert sut._ws_delta_from_frame(frame) is None


class TestTcxApplyWsFrameEndToEnd:
    def test_full_ack_populates_devices_status_temp_unit(self) -> None:
        _, sut = _make_tcx_system()
        assert sut._apply_ws_frame(_auth_frame(SAMPLE_REPORTED)) is True
        assert sut.status is SystemStatus.CONNECTED
        assert sut.temp_unit == "F"
        assert sut.devices["filt0"].data["st"] == 1
        assert sut._ws_reported_cache == SAMPLE_REPORTED

    def test_delta_updates_one_device_leaves_siblings(self) -> None:
        _, sut = _make_tcx_system()
        sut._apply_ws_frame(_auth_frame(SAMPLE_REPORTED))

        delta_frame = _delta_frame({"filt0": {"st": 0}})
        assert sut._apply_ws_frame(delta_frame) is True

        assert sut.devices["filt0"].data["st"] == 0
        # Sibling device untouched by the delta.
        assert sut.devices["ecm0"].data["cmdSpd"] == 2700

    def test_delta_omitting_status_fields_does_not_reset_them(self) -> None:
        # Regression test: status/temp_unit derivation assumes a full tree.
        # A delta lacking aws/systemMode/tempSetting must not reset them.
        _, sut = _make_tcx_system()
        sut._apply_ws_frame(_auth_frame(SAMPLE_REPORTED))
        assert sut.status is SystemStatus.CONNECTED
        assert sut.temp_unit == "F"

        delta_frame = _delta_frame({"filt0": {"st": 0}})
        sut._apply_ws_frame(delta_frame)

        assert sut.status is SystemStatus.CONNECTED
        assert sut.temp_unit == "F"


def _ws_cm(ws: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=ws)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class _StopLoop(Exception):
    """Sentinel to break the receive loop in tests."""


class TestTcxWsReceiveLoopSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_ack_applied_end_to_end(self) -> None:
        _, sut = _make_tcx_system()
        ack = json.dumps(_auth_frame(SAMPLE_REPORTED))
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=[ack, _StopLoop()])
        sut.aqualink.ws_connect = MagicMock(return_value=_ws_cm(ws))

        with self.assertRaises(_StopLoop):
            await sut._ws_receive_loop()

        assert sut.status is SystemStatus.CONNECTED
        assert sut.devices["filt0"].data["st"] == 1


class TestTcxSendCommandFrame(unittest.IsolatedAsyncioTestCase):
    async def _sent_frame(self, sut: TcxSystem, coro: Any) -> dict[str, Any]:
        with patch.object(
            sut.aqualink, "send_ws_frame", new=AsyncMock()
        ) as mock_send:
            await coro
        mock_send.assert_awaited_once()
        assert mock_send.await_args is not None
        return cast(dict[str, Any], mock_send.await_args.args[1])

    async def test_set_filter_pump(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_filter_pump(1))
        assert frame["service"] == "StateController"
        assert frame["namespace"] == NAMESPACE_FILTRATION
        assert frame["action"] == "setFilterPumpState"
        assert frame["target"] == "ABCDEFG"
        assert frame["payload"]["filt0"] == {"st": 1}
        assert "clientToken" in frame["payload"]

    async def test_set_aux(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_aux("aux0", 1))
        assert frame["namespace"] == NAMESPACE_TCX
        assert frame["action"] == "setAuxState"
        assert frame["payload"]["aux0"] == {"st": 1}

    async def test_set_heat_enabled(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_heat_enabled(True))
        assert frame["namespace"] == NAMESPACE_TCX
        assert frame["action"] == "setHeatEnabled"
        assert frame["payload"]["TspBdy0"] == {"heatEnabled": True}

    async def test_set_water_temp_setpoint(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_water_temp_setpoint(88))
        assert frame["namespace"] == NAMESPACE_TCX
        assert frame["action"] == "setWaterTempSetpoint"
        assert frame["payload"]["TspBdy0"] == {"waterTempSet": 88}

    async def test_set_swc_boost(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_swc_boost(True))
        assert frame["namespace"] == NAMESPACE_SWC
        assert frame["action"] == "setBoostMode"
        assert frame["payload"]["swc0"] == {"boost": 1}

    async def test_set_vsp_speed_uses_generic_set_state_action(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_vsp_speed(2700))
        assert frame["namespace"] == NAMESPACE_TCX
        assert frame["action"] == "setState"
        assert frame["payload"]["ecm0"] == {"cmdSpd": 2700}

    async def test_set_feature_circuit_state(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(
            sut, sut.set_feature_circuit_state("feaCircuit0", 1)
        )
        assert frame["namespace"] == NAMESPACE_FEATURE_CIRCUIT
        assert frame["action"] == "setFeatureCircuitState"
        assert frame["payload"]["feaCircuit0"] == {"st": 1}

    async def test_set_zigbee_state(self) -> None:
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_zigbee_state("auxz0", 1))
        assert frame["namespace"] == NAMESPACE_ZIGBEE
        assert frame["action"] == "setZigbeeState"
        assert frame["payload"]["auxz0"] == {"st": 1}

    async def test_set_jva_state(self) -> None:
        # Inferred namespace/action (NAMESPACE_PIB/"setJvaState") — no "PIB"
        # command entries exist in the reference doc. Never wire-confirmed;
        # covered by this mocked test only, not exercised live.
        _, sut = _make_tcx_system()
        frame = await self._sent_frame(sut, sut.set_jva_state("jva1", 1))
        assert frame["namespace"] == NAMESPACE_PIB
        assert frame["action"] == "setJvaState"
        assert frame["payload"]["jva1"] == {"st": 1}
