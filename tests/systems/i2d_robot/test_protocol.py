"""Tests for i2d_robot hex-status protocol parser."""

from __future__ import annotations

import pytest

from iaqualink.systems.i2d_robot.protocol import (
    EXPECTED_HEX_LEN,
    I2dStatus,
    parse_status_hex,
)

# ---------------------------------------------------------------------------
# Known-good 18-byte fixture
#
# Byte layout (0-indexed):
#   [0-1]   = AA BB  — reserved / header (2 bytes)
#   [2]     = 04     — state_code (0x04 = actively_cleaning)
#   [3]     = 00     — error_code (0x00 = no_error)
#   [4]     = 0A     — mode byte: low nibble 0x0A = custom_floor_and_walls_standard,
#                       high nibble 0x0 → canister_full = False
#   [5]     = 1E     — time_remaining_min = 30
#   [6-8]   = 01 00 00 — uptime_min = 1 (little-endian)
#   [9-11]  = 02 00 00 — total_hours = 2 (little-endian)
#   [12-14] = AB CD EF — hardware_id = "abcdef"
#   [15-17] = 12 34 56 — firmware_id = "123456"
# ---------------------------------------------------------------------------
_FIXTURE_HEX = "AABB04000A1E010000020000ABCDEF123456"

# Canister-full variant: high nibble of mode byte = 0x1 (non-zero → full)
# mode byte = 0x10 → mode_code = 0x00, canister_full = True
_FIXTURE_CANISTER_FULL_HEX = "AABB04001010000000020000ABCDEF123456"


class TestParseStatusHex:
    def test_valid_fixture_parses(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert isinstance(status, I2dStatus)

    def test_state_code(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.state_code == 0x04

    def test_error_code(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.error_code == 0x00

    def test_mode_code(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        # low nibble of 0x0A
        assert status.mode_code == 0x0A

    def test_canister_full_false(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.canister_full is False

    def test_canister_full_true(self) -> None:
        status = parse_status_hex(_FIXTURE_CANISTER_FULL_HEX)
        assert status.canister_full is True

    def test_time_remaining_min(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.time_remaining_min == 0x1E  # 30

    def test_uptime_min(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.uptime_min == 1

    def test_total_hours(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.total_hours == 2

    def test_hardware_id(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.hardware_id == "abcdef"

    def test_firmware_id(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.firmware_id == "123456"

    def test_state_label_known(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.state_label == "actively_cleaning"

    def test_error_label_known(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.error_label == "no_error"

    def test_mode_label_known(self) -> None:
        status = parse_status_hex(_FIXTURE_HEX)
        assert status.mode_label == "custom_floor_and_walls_standard"

    def test_state_label_unknown(self) -> None:
        # Build a hex string with state_code = 0xFF (unknown)
        raw = bytes.fromhex(_FIXTURE_HEX)
        modified = bytearray(raw)
        modified[2] = 0xFF
        status = parse_status_hex(modified.hex())
        assert status.state_label == "unknown_FF"

    def test_error_label_unknown(self) -> None:
        raw = bytes.fromhex(_FIXTURE_HEX)
        modified = bytearray(raw)
        modified[3] = 0xFF
        status = parse_status_hex(modified.hex())
        assert status.error_label == "unknown_FF"

    def test_mode_label_unknown(self) -> None:
        # mode_code 0x0F is not in I2D_MODE_LABELS
        raw = bytes.fromhex(_FIXTURE_HEX)
        modified = bytearray(raw)
        modified[4] = 0x0F
        status = parse_status_hex(modified.hex())
        assert status.mode_label == "unknown_0F"

    def test_short_input_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected 36 hex characters"):
            parse_status_hex("AABB")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected 36 hex characters"):
            parse_status_hex(_FIXTURE_HEX + "00")

    def test_non_hex_raises(self) -> None:
        bad = "ZZZZ04000A1E010000020000ABCDEF123456"
        with pytest.raises(ValueError):
            parse_status_hex(bad)

    def test_whitespace_stripped(self) -> None:
        # Spaces in the hex string should be tolerated
        spaced = " ".join(
            _FIXTURE_HEX[i : i + 2] for i in range(0, len(_FIXTURE_HEX), 2)
        )
        status = parse_status_hex(spaced)
        assert status.state_code == 0x04

    def test_uptime_multi_byte_little_endian(self) -> None:
        # uptime_min bytes [6-8] = 0x01 0x02 0x00 → 0x000201 = 513
        raw = bytes.fromhex(_FIXTURE_HEX)
        modified = bytearray(raw)
        modified[6] = 0x01
        modified[7] = 0x02
        modified[8] = 0x00
        status = parse_status_hex(modified.hex())
        assert status.uptime_min == 0x0201  # 513

    def test_total_hours_multi_byte_little_endian(self) -> None:
        # total_hours bytes [9-11] = 0x0A 0x00 0x01 → 0x01000A = 65546
        raw = bytes.fromhex(_FIXTURE_HEX)
        modified = bytearray(raw)
        modified[9] = 0x0A
        modified[10] = 0x00
        modified[11] = 0x01
        status = parse_status_hex(modified.hex())
        assert status.total_hours == 0x01000A  # 65546

    def test_expected_hex_len_constant(self) -> None:
        assert EXPECTED_HEX_LEN == 36
