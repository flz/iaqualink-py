from __future__ import annotations

import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkServiceUnauthorizedException
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.hpm.system import HpmSystem

# Mirrors the shape of a real shadow response. Values are representative
# rather than a literal capture.
SAMPLE_DATA = {
    "state": {
        "reported": {
            "aws": {
                "status": "connected",
                "timestamp": 123,
                "session_id": "xxxx",
            },
            "debug": {"RSSI": -66, "Still alive": 1},
            "ty": "UNK",
            "vr": "V71W4",
            "equipment": {
                "hp_0": {
                    "hp": 1,
                    "state": 1,
                    "sn": "xxxxx",
                    "sns_1": {
                        "type": "water",
                        "state": "connected",
                        "value": 30.4,
                    },
                    "status": 2,
                    "fan": 1,
                    "vr": "V71R54",
                    "wf": 1,
                    "sns_2": {
                        "type": "air",
                        "state": "connected",
                        "value": 28.6,
                    },
                    "tsp": 32,
                    "st": 0,
                    "cl": 0,
                    "reason": 6,
                    "tmp": 1,
                    "led": 1,
                }
            },
            "hmi": {},
            "main": {},
        }
    },
    "deviceId": "JX00000000",
    "ts": 123,
}


def _make_hpm_system() -> tuple[AqualinkClient, HpmSystem]:
    client = AqualinkClient("foo", "bar")
    data: dict[str, Any] = {
        "id": 1,
        "serial_number": "JX00000000",
        "device_type": "hpm",
        "name": "Heat_Pump-1",
    }
    sut = cast(HpmSystem, AqualinkSystem.from_data(client, data=data))
    return client, sut


def _fresh_sample_data() -> dict[str, Any]:
    # Round-trip through JSON (rather than copy.deepcopy) so the result is a
    # plain dict[str, Any] rather than a structurally-typed literal copy —
    # ty infers a very specific shape for SAMPLE_DATA itself, and deep
    # mutation below needs the looser type.
    return cast(dict[str, Any], json.loads(json.dumps(SAMPLE_DATA)))


def _make_shadow_response(aws_status: str | None) -> MagicMock:
    data: dict[str, Any] = _fresh_sample_data()
    if aws_status is None:
        del data["state"]["reported"]["aws"]
    else:
        data["state"]["reported"]["aws"]["status"] = aws_status
    response = MagicMock()
    response.json.return_value = data
    return response


class TestHpmSystem:
    def test_parse_shadow_absent_aws_status(self) -> None:
        _, sut = _make_hpm_system()
        response = _make_shadow_response(None)
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    def test_parse_shadow_connected(self) -> None:
        _, sut = _make_hpm_system()
        response = _make_shadow_response("connected")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.CONNECTED

    def test_parse_shadow_disconnected(self) -> None:
        _, sut = _make_hpm_system()
        response = _make_shadow_response("disconnected")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.DISCONNECTED

    def test_parse_shadow_unknown_string(self) -> None:
        _, sut = _make_hpm_system()
        response = _make_shadow_response("something_unknown")
        sut._parse_shadow_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    def test_parse_shadow_missing_equipment_block(self) -> None:
        _, sut = _make_hpm_system()
        data = _fresh_sample_data()
        del data["state"]["reported"]["equipment"]
        response = MagicMock()
        response.json.return_value = data
        sut._parse_shadow_response(response)
        assert sut.devices == {}

    def test_parse_shadow_populates_devices(self) -> None:
        _, sut = _make_hpm_system()
        response = _make_shadow_response("connected")
        sut._parse_shadow_response(response)

        assert set(sut.devices) == {
            "heatpump",
            "mode",
            "cooling_priority",
            "status",
            "reason",
            "water_temp",
            "air_temp",
            "water_flow",
        }
        assert sut.devices["heatpump"].data["state"] == 1
        assert sut.devices["heatpump"].data["tsp"] == 32
        assert sut.devices["water_temp"].data["value"] == 30.4
        assert sut.devices["water_temp"].data["state"] == "connected"
        assert sut.devices["air_temp"].data["value"] == 28.6
        assert sut.devices["water_flow"].data["wf"] == 1
        assert sut.devices["status"].data["status"] == 2
        assert sut.devices["reason"].data["reason"] == 6

    def test_parse_shadow_gives_each_device_only_its_own_keys(self) -> None:
        _, sut = _make_hpm_system()
        sut._parse_shadow_response(_make_shadow_response("connected"))

        assert set(sut.devices["mode"].data) == {"name", "st"}
        assert set(sut.devices["cooling_priority"].data) == {"name", "cl"}
        assert set(sut.devices["heatpump"].data) == {"name", "state", "tsp"}

    def test_parse_shadow_skips_devices_whose_keys_are_absent(self) -> None:
        _, sut = _make_hpm_system()
        data = _fresh_sample_data()
        hp_zero = data["state"]["reported"]["equipment"]["hp_0"]
        del hp_zero["wf"]
        del hp_zero["sns_2"]
        response = MagicMock()
        response.json.return_value = data
        sut._parse_shadow_response(response)

        assert "water_flow" not in sut.devices
        assert "air_temp" not in sut.devices
        assert "water_temp" in sut.devices

    def test_parse_shadow_updates_existing_devices_in_place(self) -> None:
        _, sut = _make_hpm_system()
        sut._parse_shadow_response(_make_shadow_response("connected"))
        heatpump = sut.devices["heatpump"]

        data = _fresh_sample_data()
        data["state"]["reported"]["equipment"]["hp_0"]["state"] = 0
        response = MagicMock()
        response.json.return_value = data
        sut._parse_shadow_response(response)

        assert sut.devices["heatpump"] is heatpump
        assert sut.devices["heatpump"].data["state"] == 0

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request(self, mock_request) -> None:
        _, sut = _make_hpm_system()
        mock_request.return_value.status_code = 200
        await sut.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_unauthorized(
        self, mock_request
    ) -> None:
        _, sut = _make_hpm_system()
        mock_request.return_value.status_code = 401
        with pytest.raises(AqualinkServiceUnauthorizedException):
            await sut.send_reported_state_request()

    @patch("httpx.AsyncClient.request")
    async def test_reported_state_request_retries_after_refresh(
        self, mock_request
    ) -> None:
        client, sut = _make_hpm_system()
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


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


class TestHpmSystemDesiredState:
    """Body shape of each write helper.

    Dispatch from the device methods is covered by the shared conformance
    suite via factories.py.
    """

    async def test_set_state_body_shape(self) -> None:
        _, sut = _make_hpm_system()
        calls: list[dict[str, Any]] = []

        async def fake_send(state: dict[str, Any]) -> _FakeResponse:
            calls.append(state)
            return _FakeResponse()

        sut.send_desired_state_request = fake_send  # type: ignore[method-assign]  # ty: ignore
        await sut.set_state(1)
        assert calls == [{"equipment": {"hp_0": {"state": 1}}}]

    async def test_set_setpoint_body_shape(self) -> None:
        _, sut = _make_hpm_system()
        calls: list[dict[str, Any]] = []

        async def fake_send(state: dict[str, Any]) -> _FakeResponse:
            calls.append(state)
            return _FakeResponse()

        sut.send_desired_state_request = fake_send  # type: ignore[method-assign]  # ty: ignore
        await sut.set_setpoint(30)
        assert calls == [{"equipment": {"hp_0": {"tsp": 30}}}]

    async def test_set_mode_body_shape(self) -> None:
        _, sut = _make_hpm_system()
        calls: list[dict[str, Any]] = []

        async def fake_send(state: dict[str, Any]) -> _FakeResponse:
            calls.append(state)
            return _FakeResponse()

        sut.send_desired_state_request = fake_send  # type: ignore[method-assign]  # ty: ignore
        await sut.set_mode(2)
        assert calls == [{"equipment": {"hp_0": {"st": 2}}}]

    async def test_set_cooling_priority_body_shape(self) -> None:
        _, sut = _make_hpm_system()
        calls: list[dict[str, Any]] = []

        async def fake_send(state: dict[str, Any]) -> _FakeResponse:
            calls.append(state)
            return _FakeResponse()

        sut.send_desired_state_request = fake_send  # type: ignore[method-assign]  # ty: ignore
        await sut.set_cooling_priority(1)
        assert calls == [{"equipment": {"hp_0": {"cl": 1}}}]
