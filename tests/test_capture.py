from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx

from iaqualink.cli.capture import CaptureSession, _redact_dict


def _make_request(
    method: str = "GET",
    url: str = "https://prod.zodiac-io.com/devices/v1/status",
    body: dict | None = None,
) -> httpx.Request:
    kwargs: dict = {}
    if body is not None:
        kwargs["json"] = body
    return httpx.Request(method, url, **kwargs)


def _make_response(
    request: httpx.Request,
    status_code: int = 200,
    body: dict | str | None = None,
) -> httpx.Response:
    if isinstance(body, dict):
        return httpx.Response(status_code, json=body, request=request)
    if isinstance(body, str):
        return httpx.Response(
            status_code, content=body.encode(), request=request
        )
    return httpx.Response(status_code, json={}, request=request)


class TestRedactDict(unittest.TestCase):
    def test_redacts_sensitive_keys(self) -> None:
        result = _redact_dict(
            {
                "email": "user@example.com",
                "password": "secret",
                "authentication_token": "tok123",
            }
        )
        assert result["email"] == "***"
        assert result["password"] == "***"
        assert result["authentication_token"] == "***"

    def test_passes_through_safe_keys(self) -> None:
        result = _redact_dict({"status": "ok", "device_type": "iaqua"})
        assert result == {"status": "ok", "device_type": "iaqua"}

    def test_empty_dict(self) -> None:
        assert _redact_dict({}) == {}

    def test_case_insensitive_key_match(self) -> None:
        result = _redact_dict(
            {"IdToken": "jwt-secret", "AccessKeyId": "AKIA123"}
        )
        assert result["IdToken"] == "***"
        assert result["AccessKeyId"] == "***"

    def test_recursive_nested_dicts(self) -> None:
        result = _redact_dict(
            {
                "status": "ok",
                "credentials": {
                    "AccessKeyId": "AKIA123",
                    "SecretKey": "secret",
                    "SessionToken": "token",
                },
                "userPoolOAuth": {
                    "IdToken": "jwt-value",
                    "ExpiresIn": 3600,
                },
            }
        )
        assert result["status"] == "ok"
        assert result["credentials"]["AccessKeyId"] == "***"
        assert result["credentials"]["SecretKey"] == "***"
        assert result["credentials"]["SessionToken"] == "***"
        assert result["userPoolOAuth"]["IdToken"] == "***"
        assert result["userPoolOAuth"]["ExpiresIn"] == 3600

    def test_pii_fields_redacted(self) -> None:
        result = _redact_dict(
            {
                "first_name": "Florent",
                "last_name": "Thoumie",
                "phone": "6508623243",
                "postal_code": "95051",
                "address": "123 Main St",
                "address_1": "123 Main St",
                "username": "f7ce4321-2927-4615-a30b-551d9873b2c3",
            }
        )
        for key in result:
            assert result[key] == "***", f"{key!r} not redacted"


class TestCaptureSession(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpfile = NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode="w"
        )
        self._tmpfile.close()
        self._path = Path(self._tmpfile.name)

    def tearDown(self) -> None:
        self._path.unlink(missing_ok=True)

    def _load_lines(self) -> list[dict]:
        return [
            json.loads(line)
            for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    async def test_happy_path_writes_jsonl(self) -> None:
        session = CaptureSession(path=self._path)
        request = _make_request("GET", "https://prod.zodiac-io.com/status")
        response = _make_response(request, 200, {"result": "ok"})

        await session._capture_response(response)
        session.close()

        lines = self._load_lines()
        assert len(lines) == 1
        entry = lines[0]
        assert "timestamp" in entry
        assert entry["request"]["method"] == "GET"
        assert "prod.zodiac-io.com" in entry["request"]["url"]
        assert entry["response"]["status_code"] == 200
        assert entry["response"]["body"] == {"result": "ok"}

    async def test_redacts_password_in_request_body(self) -> None:
        session = CaptureSession(path=self._path)
        request = _make_request(
            "POST",
            "https://prod.zodiac-io.com/login",
            body={"email": "u@example.com", "password": "hunter2"},
        )
        response = _make_response(request, 200, {"session_id": "s1"})

        await session._capture_response(response)
        session.close()

        entry = self._load_lines()[0]
        assert entry["request"]["body"]["password"] == "***"
        assert entry["request"]["body"]["email"] == "***"

    async def test_redacts_token_in_response_body(self) -> None:
        session = CaptureSession(path=self._path)
        request = _make_request("POST", "https://prod.zodiac-io.com/login")
        response = _make_response(
            request,
            200,
            {
                "authentication_token": "tok-secret",
                "refresh_token": "ref-secret",
                "session_id": "sess-123",
            },
        )

        await session._capture_response(response)
        session.close()

        body = self._load_lines()[0]["response"]["body"]
        assert body["authentication_token"] == "***"
        assert body["refresh_token"] == "***"
        assert body["session_id"] == "***"

    async def test_redacts_authorization_header(self) -> None:
        session = CaptureSession(path=self._path)
        request = httpx.Request(
            "GET",
            "https://prod.zodiac-io.com/devices",
            headers={"Authorization": "Bearer secret-id-token"},
        )
        response = _make_response(request, 200, {})

        await session._capture_response(response)
        session.close()

        headers = self._load_lines()[0]["request"]["headers"]
        assert headers["authorization"] == "***"

    async def test_redacts_sensitive_url_param(self) -> None:
        session = CaptureSession(path=self._path)
        request = _make_request(
            "GET",
            "https://r-api.iaqualink.net/devices?api_key=REAL_KEY&foo=bar",
        )
        response = _make_response(request, 200, {})

        await session._capture_response(response)
        session.close()

        url = self._load_lines()[0]["request"]["url"]
        assert "REAL_KEY" not in url
        assert "api_key=***" in url
        assert "foo=bar" in url

    async def test_non_json_response_stored_as_string(self) -> None:
        session = CaptureSession(path=self._path)
        request = _make_request("GET", "https://prod.zodiac-io.com/raw")
        response = _make_response(request, 200, "plain text body")

        await session._capture_response(response)
        session.close()

        body = self._load_lines()[0]["response"]["body"]
        assert body == "plain text body"

    async def test_multiple_requests_multiple_lines(self) -> None:
        session = CaptureSession(path=self._path)
        for i in range(3):
            request = _make_request("GET", f"https://example.com/path/{i}")
            response = _make_response(request, 200, {"i": i})
            await session._capture_response(response)
        session.close()

        lines = self._load_lines()
        assert len(lines) == 3
        for line in lines:
            assert "timestamp" in line

    def test_close_idempotent(self) -> None:
        session = CaptureSession(path=self._path)
        session.close()
        session.close()  # should not raise

    def test_make_hooks_returns_response_hook(self) -> None:
        session = CaptureSession(path=self._path)
        hooks = session.make_hooks()
        session.close()
        assert "response" in hooks
        assert len(hooks["response"]) == 1
        assert hooks["response"][0] == session._capture_response
