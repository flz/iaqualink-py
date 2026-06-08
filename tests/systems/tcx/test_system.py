from __future__ import annotations

import copy
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkServiceUnauthorizedException
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.system import TcxSystem

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


class TestActiveSubShadowSuffixes:
    def test_no_equipment_key(self) -> None:
        _, sut = _make_tcx_system()
        reported: dict[str, Any] = {}
        assert sut._active_sub_shadow_suffixes(reported) == []

    def test_filt_and_ecm(self) -> None:
        _, sut = _make_tcx_system()
        reported: dict[str, Any] = {"equipment": {"filt": {}, "ecm": {}}}
        result = sut._active_sub_shadow_suffixes(reported)
        assert set(result) == {"_filt", "_ecm"}

    def test_all_sub_shadows(self) -> None:
        _, sut = _make_tcx_system()
        reported: dict[str, Any] = {
            "equipment": {
                "filt": {},
                "ecm": {},
                "sched": {},
                "pib0": {},
                "fea": {},
                "zig": {},
                "scene": {},
            }
        }
        result = sut._active_sub_shadow_suffixes(reported)
        assert set(result) == {
            "_filt",
            "_ecm",
            "_sched",
            "_pib0",
            "_fea",
            "_zig",
            "_scene",
        }


class TestSubShadowMerge:
    def test_filt_sub_shadow_merges_into_filt0(self) -> None:
        _, sut = _make_tcx_system()
        sut._parse_shadow_response(_make_shadow_response())

        sub_resp = MagicMock()
        sub_resp.json.return_value = {
            "state": {
                "reported": {
                    "sl": [{"start": "08:00", "end": "20:00", "en": 1}],
                    "st": 1,
                }
            }
        }
        sut._parse_sub_shadow_response("_filt", sub_resp)
        assert "sl" in sut.devices["filt0"].data

    def test_ecm_sub_shadow_merges_into_ecm0(self) -> None:
        _, sut = _make_tcx_system()
        sut._parse_shadow_response(_make_shadow_response())

        sub_resp = MagicMock()
        sub_resp.json.return_value = {
            "state": {"reported": {"servTm": 999, "cmdSpd": 2700}}
        }
        sut._parse_sub_shadow_response("_ecm", sub_resp)
        assert sut.devices["ecm0"].data["servTm"] == 999

    def test_fea_sub_shadow_creates_feature_circuits(self) -> None:
        _, sut = _make_tcx_system()
        sut._parse_shadow_response(_make_shadow_response())

        sub_resp = MagicMock()
        sub_resp.json.return_value = {
            "state": {
                "reported": {
                    "feaCircuit0": {"st": 0, "en": 1, "fr": "Spa Jets"},
                    "feaCircuit1": {"st": 1, "en": 1, "fr": "Spa Light"},
                }
            }
        }
        sut._parse_sub_shadow_response("_fea", sub_resp)
        assert "feaCircuit0" in sut.devices
        assert "feaCircuit1" in sut.devices

    def test_zig_sub_shadow_creates_zigbee_devices(self) -> None:
        _, sut = _make_tcx_system()
        sut._parse_shadow_response(_make_shadow_response())

        sub_resp = MagicMock()
        sub_resp.json.return_value = {
            "state": {
                "reported": {
                    "zig": {
                        "aabbccdd": {"st": 1, "fr": "Pool Light"},
                    }
                }
            }
        }
        sut._parse_sub_shadow_response("_zig", sub_resp)
        assert "zig_aabbccdd" in sut.devices

    def test_unknown_suffix_is_silently_ignored(self) -> None:
        _, sut = _make_tcx_system()
        sut._parse_shadow_response(_make_shadow_response())
        device_count = len(sut.devices)

        sub_resp = MagicMock()
        sub_resp.json.return_value = {"state": {"reported": {"foo": "bar"}}}
        sut._parse_sub_shadow_response("_scene", sub_resp)
        assert len(sut.devices) == device_count


class TestSubShadowFetchIsolation:
    @patch("httpx.AsyncClient.request")
    async def test_sub_shadow_failure_does_not_abort_others(
        self, mock_request
    ) -> None:
        _, sut = _make_tcx_system()

        main_resp = MagicMock()
        main_resp.json.return_value = {
            "state": {
                "reported": {
                    **SAMPLE_REPORTED,
                    "equipment": {"filt": {}, "fea": {}},
                }
            }
        }
        fea_resp = MagicMock()
        fea_resp.json.return_value = {
            "state": {
                "reported": {
                    "feaCircuit0": {"st": 0, "en": 1, "fr": "Spa Jets"}
                }
            }
        }

        async def fake_send_reported() -> MagicMock:
            return main_resp

        async def fake_filt_fail(suffix: str) -> MagicMock:
            if suffix == "_filt":
                raise ConnectionError("network error")
            return fea_resp

        with (
            patch.object(
                sut,
                "send_reported_state_request",
                side_effect=fake_send_reported,
            ),
            patch.object(
                sut,
                "_send_sub_shadow_read_request",
                side_effect=fake_filt_fail,
            ),
        ):
            await sut._refresh()

        # _fea succeeded despite _filt failure
        assert "feaCircuit0" in sut.devices
        # filt0 still created from main shadow
        assert "filt0" in sut.devices

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
