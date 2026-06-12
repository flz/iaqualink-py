from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx

from iaqualink.cli.capture import CaptureSession
from iaqualink.utils.capture import build_capture_entry
from iaqualink.utils.redact import mask_email, mask_serial, redact_dict


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


class TestMaskEmail(unittest.TestCase):
    def test_masks_normal_email(self) -> None:
        result = mask_email("testuser@example.net")
        assert "testuser" not in result
        assert "example" not in result
        assert "@" in result
        assert result.endswith(".net")

    def test_short_local_part(self) -> None:
        result = mask_email("ab@example.com")
        assert "ab" not in result
        assert "@" in result

    def test_very_short_local_part(self) -> None:
        result = mask_email("a@b.com")
        assert result == "***@b***.com"

    def test_non_email_returns_redacted(self) -> None:
        assert mask_email("not-an-email") == "***"

    def test_preserves_tld(self) -> None:
        result = mask_email("user@example.org")
        assert result.endswith(".org")


class TestMaskSerial(unittest.TestCase):
    def test_normal_serial(self) -> None:
        result = mask_serial("TESTSERIAL1")
        assert result == "***AL1"
        assert "TESTSERIAL1"[:-3] not in result

    def test_exactly_three_chars(self) -> None:
        assert mask_serial("ABC") == "***"

    def test_short_serial(self) -> None:
        assert mask_serial("AB") == "***"

    def test_empty_string(self) -> None:
        assert mask_serial("") == "***"

    def test_four_char_serial(self) -> None:
        result = mask_serial("ABCD")
        assert result == "***BCD"


class TestRedactDict(unittest.TestCase):
    def test_redacts_sensitive_keys(self) -> None:
        result = redact_dict(
            {
                "email": "user@example.com",
                "password": "secret",
                "authentication_token": "tok123",
            }
        )
        assert result["email"] != "user@example.com"  # partially masked
        assert "@" in result["email"]  # still recognisably an email
        assert result["password"] == "***"
        assert result["authentication_token"] == "***"

    def test_passes_through_safe_keys(self) -> None:
        result = redact_dict({"status": "ok", "device_type": "iaqua"})
        assert result == {"status": "ok", "device_type": "iaqua"}

    def test_empty_dict(self) -> None:
        assert redact_dict({}) == {}

    def test_substring_key_match(self) -> None:
        result = redact_dict(
            {
                "access_token": "tok",
                "session_key": "sk",
                "client_secret": "cs",
                "api_credential": "cred",
                "device_type": "iaqua",
            }
        )
        assert result["access_token"] == "***"
        assert result["session_key"] == "***"
        assert result["client_secret"] == "***"
        assert result["api_credential"] == "***"
        assert result["device_type"] == "iaqua"

    def test_case_insensitive_key_match(self) -> None:
        result = redact_dict(
            {"IdToken": "jwt-secret", "AccessKeyId": "AKIA123"}
        )
        assert result["IdToken"] == "***"
        assert result["AccessKeyId"] == "***"

    def test_recursive_nested_dicts(self) -> None:
        result = redact_dict(
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
        assert result["credentials"] == "***"
        assert result["userPoolOAuth"]["IdToken"] == "***"
        assert result["userPoolOAuth"]["ExpiresIn"] == 3600

    def test_pii_fields_redacted(self) -> None:
        result = redact_dict(
            {
                "first_name": "Test",
                "last_name": "User",
                "phone": "5550001234",
                "postal_code": "00000",
                "address": "123 Main St",
                "address_1": "123 Main St",
                "username": "f7ce4321-2927-4615-a30b-551d9873b2c3",
            }
        )
        for key in result:
            assert result[key] == "***", f"{key!r} not redacted"

    def test_serial_keys_partially_masked(self) -> None:
        result = redact_dict(
            {
                "serial": "TESTSERIAL1",
                "serial_number": "TESTDEVICE2",
                "serialnumber": "TESTUNIT003",
            }
        )
        assert result["serial"] == "***AL1"
        assert result["serial_number"] == "***CE2"
        assert result["serialnumber"] == "***003"

    def test_serial_key_short_value(self) -> None:
        result = redact_dict({"serial_number": "AB"})
        assert result["serial_number"] == "***"


class TestBuildCaptureEntry(unittest.IsolatedAsyncioTestCase):
    async def test_auth_url_redacts_extended_keys(self) -> None:
        request = _make_request(
            "POST", "https://prod.zodiac-io.com/users/v1/login"
        )
        response = _make_response(
            request,
            200,
            {"username": "florent@example.com", "state": "CA"},
        )

        entry = await build_capture_entry(response)

        assert entry["response"]["body"]["state"] == "***"
        assert "florent" not in entry["response"]["body"]["username"]

    async def test_non_auth_url_keeps_state_field(self) -> None:
        request = _make_request(
            "GET",
            "https://r-api.iaqualink.net/v2/devices/SERIAL/control.json",
        )
        response = _make_response(
            request,
            200,
            {"devices_screen": [{"name": "Pool Pump", "state": "1"}]},
        )

        entry = await build_capture_entry(response)

        assert entry["response"]["body"]["devices_screen"][0]["state"] == "1"


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
        assert "u@example.com" not in entry["request"]["body"]["email"]

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

    async def test_redacts_response_headers(self) -> None:
        session = CaptureSession(path=self._path)
        request = _make_request("GET", "https://prod.zodiac-io.com/status")
        response = httpx.Response(
            200,
            headers={
                "set-cookie": "session_id=abc123; HttpOnly",
                "x-cdn": "Imperva",
            },
            json={},
            request=request,
        )

        await session._capture_response(response)
        session.close()

        headers = self._load_lines()[0]["response"]["headers"]
        assert headers["set-cookie"] == "***"
        assert headers.get("x-cdn") == "Imperva"

    async def test_redacts_serial_in_url_path(self) -> None:
        session = CaptureSession(path=self._path)
        session.register_serials("ZZZ000SERIAL")
        request = _make_request(
            "GET",
            "https://r-api.iaqualink.net/v2/devices/ZZZ000SERIAL/control.json",
        )
        response = _make_response(request, 200, {})

        await session._capture_response(response)
        session.close()

        url = self._load_lines()[0]["request"]["url"]
        assert "ZZZ000SERIAL" not in url
        assert "***" + "ZZZ000SERIAL"[-3:] in url

    def test_register_serials_ignores_empty(self) -> None:
        session = CaptureSession(path=self._path)
        session.register_serials("", "SN001")
        session.close()
        assert "" not in session._literals
        assert "SN001" in session._literals

    async def test_redacts_fields_in_list_response_body(self) -> None:
        session = CaptureSession(path=self._path)
        request = _make_request(
            "GET", "https://r-api.iaqualink.net/v2/devices.json"
        )
        response = httpx.Response(
            200,
            json=[
                {
                    "id": 113883,
                    "serial_number": "ZZZ000SERIAL",
                    "device_type": "iaqua",
                    "owner_id": None,
                },
                {
                    "id": 607822,
                    "serial_number": "ZZZ111SERIAL",
                    "device_type": "i2d",
                    "owner_id": 833029,
                },
            ],
            request=request,
        )

        await session._capture_response(response)
        session.close()

        body = self._load_lines()[0]["response"]["body"]
        assert isinstance(body, list)
        assert body[0]["id"] == "***"
        assert body[0]["serial_number"] == "***" + "ZZZ000SERIAL"[-3:]
        assert body[0]["device_type"] == "iaqua"
        assert body[0]["owner_id"] == "***"
        assert body[1]["id"] == "***"
        assert body[1]["serial_number"] == "***" + "ZZZ111SERIAL"[-3:]

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

    async def test_state_redacted_in_auth_response(self) -> None:
        # "state" is a user-profile PII field (address state) in auth responses.
        session = CaptureSession(path=self._path)
        request = _make_request(
            "POST",
            "https://prod.zodiac-io.com/users/v1/login",
            body={"email": "u@example.com", "password": "hunter2"},
        )
        response = _make_response(
            request,
            200,
            {"id": 1, "state": "CA", "username": "u@example.com"},
        )

        await session._capture_response(response)
        session.close()

        body = self._load_lines()[0]["response"]["body"]
        assert body["state"] == "***"

    async def test_state_visible_in_device_response(self) -> None:
        # "state" in device responses is the on/off field — must not be redacted.
        session = CaptureSession(path=self._path)
        request = _make_request(
            "GET",
            "https://r-api.iaqualink.net/v2/devices/SERIAL/control.json",
        )
        response = _make_response(
            request,
            200,
            {"devices_screen": [{"name": "Pool Pump", "state": "1"}]},
        )

        await session._capture_response(response)
        session.close()

        body = self._load_lines()[0]["response"]["body"]
        assert body["devices_screen"][0]["state"] == "1"

    async def test_auth_url_applies_extended_key_set(self) -> None:
        # Verifies URL dispatch: auth URL → _AUTH_CAPTURE_KEYS_CI (includes state).
        # username is masked unconditionally via _EMAIL_KEYS; state being redacted
        # proves the auth key set (not just REDACT_KEYS_CI) was selected.
        session = CaptureSession(path=self._path)
        request = _make_request(
            "POST",
            "https://prod.zodiac-io.com/users/v1/login",
        )
        response = _make_response(
            request,
            200,
            {"username": "florent@example.com", "state": "CA"},
        )

        await session._capture_response(response)
        session.close()

        body = self._load_lines()[0]["response"]["body"]
        assert body["state"] == "***"
        assert "@" in body["username"]
        assert "florent" not in body["username"]
