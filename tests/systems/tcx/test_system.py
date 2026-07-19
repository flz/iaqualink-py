from __future__ import annotations

import copy
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.const import AQUALINK_API_SIGNING_KEY
from iaqualink.exception import AqualinkServiceUnauthorizedException
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.system import TcxSystem
from iaqualink.utils.crypto import sign

SAMPLE_REPORTED: dict[str, Any] = {
    "sn": "ABCDEFG",
    "systemMode": 0,
    "tempSetting": 1,
    "aws": {"status": "connected", "timestamp": 123},
    "equipment": {
        "filt": {"present": True},
        "ecm": {"present": True},
    },
    "filt0": {"st": 1, "en": 1, "fr": "Filter Pump"},
    "ecm0": {"cmdSpd": 2700, "minSpd": 1000, "maxSpd": 3450, "st": 1, "en": 1},
}

SAMPLE_DATA: dict[str, Any] = {"state": {"reported": SAMPLE_REPORTED}}


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


def _make_shadow_response(
    reported_overrides: dict[str, Any] | None = None,
    aws_status: str | None = "connected",
) -> MagicMock:
    reported = copy.deepcopy(SAMPLE_REPORTED)
    if aws_status is None:
        reported.pop("aws", None)
    elif "aws" in reported:
        reported["aws"]["status"] = aws_status
    if reported_overrides:
        reported.update(reported_overrides)
    response = MagicMock()
    response.json.return_value = {"state": {"reported": reported}}
    return response


class TestTcxSystemStatus:
    def test_service_mode_3(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response({"systemMode": 3})
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.SERVICE

    def test_service_mode_4(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response({"systemMode": 4})
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.SERVICE

    def test_connected(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response(aws_status="connected")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.CONNECTED

    def test_disconnected(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response(aws_status="disconnected")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.DISCONNECTED

    def test_absent_aws_status(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response(aws_status=None)
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    def test_unknown_aws_status_string(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response(aws_status="something_new")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    def test_firmware_update(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response(aws_status="firmware_update")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.FIRMWARE_UPDATE


class TestTcxTempUnit:
    def test_fahrenheit_by_default(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response({"tempSetting": 1})
        sut._parse_shadow_response(response)
        assert sut.temp_unit == "F"

    def test_celsius_when_temp_setting_zero(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response({"tempSetting": 0})
        sut._parse_shadow_response(response)
        assert sut.temp_unit == "C"


class TestFeaZigDeviceDiscovery:
    # _parse_fea_sub_shadow/_parse_zig_sub_shadow used to only ever run
    # against a dedicated REST sub-shadow response. That REST fetch is
    # confirmed non-functional against real hardware and has been removed;
    # these now run unconditionally against whatever reported tree
    # _apply_reported_state sees (REST main shadow, WS Authorization ack, or
    # a merged WS delta), best-effort — see "Deltas vs Protocol Reference" in
    # docs/implementation/systems/tcx.md.

    def test_fea_circuits_discovered_from_reported_tree(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response(
            {
                "feaCircuit0": {"st": 0, "en": 1, "fr": "Spa Jets"},
                "feaCircuit1": {"st": 1, "en": 1, "fr": "Spa Light"},
            }
        )
        sut._parse_shadow_response(response)
        assert "feaCircuit0" in sut.devices
        assert "feaCircuit1" in sut.devices

    def test_zig_devices_discovered_from_reported_tree(self) -> None:
        _, sut = _make_tcx_system()
        response = _make_shadow_response(
            {"zig": {"aabbccdd": {"st": 1, "fr": "Pool Light"}}}
        )
        sut._parse_shadow_response(response)
        assert "zig_aabbccdd" in sut.devices

    def test_absent_fea_and_zig_keys_is_a_no_op(self) -> None:
        _, sut = _make_tcx_system()
        sut._parse_shadow_response(_make_shadow_response())
        assert not any(k.startswith("feaCircuit") for k in sut.devices)
        assert not any(k.startswith("zig_") for k in sut.devices)


class TestTcxRefreshRestOnlyMainShadow:
    @patch("httpx.AsyncClient.request")
    async def test_refresh_issues_only_main_shadow_request(
        self, mock_request: MagicMock
    ) -> None:
        # No sub-shadow REST calls remain — only the main shadow GET.
        _, sut = _make_tcx_system()
        sut._ws_enabled = False
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: SAMPLE_DATA
        )
        await sut._refresh()
        assert mock_request.call_count == 1


class TestReportedStateRequest:
    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_includes_signature(
        self, mock_request
    ) -> None:
        client, sut = _make_tcx_system()
        client.user_id = "12345"
        mock_request.return_value = MagicMock(status_code=200)

        await sut.send_reported_state_request()

        params = mock_request.call_args[1]["params"]
        assert params == {
            "signature": sign(["ABCDEFG", "12345"], AQUALINK_API_SIGNING_KEY)
        }

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_unauthorized(
        self, mock_request
    ) -> None:
        _, sut = _make_tcx_system()
        mock_request.return_value.status_code = 401
        with pytest.raises(AqualinkServiceUnauthorizedException):
            await sut.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_retries_after_refresh(
        self, mock_request
    ) -> None:
        client, sut = _make_tcx_system()
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=200),
        ]
        client.id_token = "old-id-token"

        async def fake_refresh() -> None:
            client.id_token = "new-id-token"

        with patch.object(
            client, "_refresh_auth", side_effect=fake_refresh
        ) as mock_refresh:
            await sut.send_reported_state_request()

        retry_headers = mock_request.call_args_list[1][1]["headers"]
        mock_refresh.assert_awaited_once()
        assert retry_headers["Authorization"] == "new-id-token"


class TestTcxRefreshWsLifecycle:
    # _refresh() auto-starts the WS subscription via _ws_refresh_gate()
    # (idempotent — a no-op once a live task exists). Tests that don't want
    # a real background task/connection attempt patch start_ws_subscription
    # directly.

    async def test_refresh_auto_starts_subscription(self) -> None:
        _, sut = _make_tcx_system()
        with (
            patch.object(
                sut, "start_ws_subscription", new=AsyncMock()
            ) as mock_start,
            patch.object(sut, "send_reported_state_request", new=AsyncMock()),
            patch.object(sut, "_parse_shadow_response"),
        ):
            await sut._refresh()
        mock_start.assert_awaited_once()

    async def test_refresh_skips_rest_when_ws_state_fresh(self) -> None:
        _, sut = _make_tcx_system()
        sut._ws_reported_cache = copy.deepcopy(SAMPLE_REPORTED)
        with (
            patch.object(sut, "start_ws_subscription", new=AsyncMock()),
            patch.object(sut, "_ws_state_fresh", return_value=True),
            patch.object(
                sut, "send_reported_state_request", new=AsyncMock()
            ) as mock_req,
        ):
            await sut._refresh()
        mock_req.assert_not_called()

    async def test_refresh_restores_status_on_ws_fresh_skip(self) -> None:
        # refresh() resets status to IN_PROGRESS before calling _refresh();
        # the skip-REST path must restore it from the WS-derived cache.
        _, sut = _make_tcx_system()
        sut._ws_reported_cache = {
            **copy.deepcopy(SAMPLE_REPORTED),
            "aws": {"status": "connected"},
        }
        with (
            patch.object(sut, "start_ws_subscription", new=AsyncMock()),
            patch.object(sut, "_ws_state_fresh", return_value=True),
        ):
            await sut.refresh()
        assert sut.status is SystemStatus.CONNECTED

    @patch("httpx.AsyncClient.request")
    async def test_refresh_polls_rest_when_ws_disabled(
        self, mock_request: MagicMock
    ) -> None:
        # Disabled -> must still poll REST, and must not even attempt to
        # start the subscription.
        _, sut = _make_tcx_system()
        sut._ws_enabled = False
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: SAMPLE_DATA
        )
        with (
            patch.object(
                sut, "start_ws_subscription", new=AsyncMock()
            ) as mock_start,
            patch.object(sut, "_ws_state_fresh", return_value=True),
        ):
            await sut._refresh()
        mock_request.assert_called()
        mock_start.assert_not_awaited()

    @patch("httpx.AsyncClient.request")
    async def test_refresh_polls_rest_when_ws_never_connected(
        self, mock_request: MagicMock
    ) -> None:
        # start_ws_subscription() runs (auto-started) but the socket hasn't
        # delivered anything yet -> _ws_state_fresh() is naturally False ->
        # plain REST bootstrap, same as before WS support existed.
        _, sut = _make_tcx_system()
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: SAMPLE_DATA
        )
        with patch.object(sut, "start_ws_subscription", new=AsyncMock()):
            await sut._refresh()
        mock_request.assert_called()
        assert sut.status is SystemStatus.CONNECTED
