from __future__ import annotations

import unittest

import pytest

from iaqualink.systems.i2d_robot.protocol import (
    EXPECTED_HEX_LEN,
    parse_status_hex,
)


class TestParseStatusHex(unittest.TestCase):
    def _make_hex(
        self,
        *,
        state: int = 0x04,
        error: int = 0x00,
        mode_byte: int = 0x03,
        time_remaining: int = 45,
        uptime: int = 0x010203,
        total_hours: int = 0x040506,
        hardware: bytes = b"\xaa\xbb\xcc",
        firmware: bytes = b"\xdd\xee\xff",
    ) -> str:
        prefix = b"\xff\xff"
        # Match the parser: bytes 6:9 / 9:12 are little-endian uint24.
        uptime_bytes = uptime.to_bytes(3, "little")
        total_hours_bytes = total_hours.to_bytes(3, "little")
        body = (
            prefix
            + bytes([state, error, mode_byte, time_remaining])
            + uptime_bytes
            + total_hours_bytes
            + hardware
            + firmware
        )
        assert len(body) == 18
        return body.hex()

    def test_parse_well_formed_payload(self) -> None:
        hex_str = self._make_hex(
            state=0x04,
            error=0x00,
            mode_byte=0x13,  # canister bit set + mode 3
            time_remaining=45,
        )
        assert len(hex_str) == EXPECTED_HEX_LEN
        status = parse_status_hex(hex_str)
        assert status.state_code == 0x04
        assert status.error_code == 0x00
        assert status.mode_code == 0x03
        assert status.canister_full is True
        assert status.time_remaining_min == 45
        assert status.state_label == "actively_cleaning"
        assert status.error_label == "no_error"
        assert status.mode_label == ("deep_clean_floor_and_walls_high_power")

    def test_parse_canister_empty_when_upper_nibble_zero(self) -> None:
        status = parse_status_hex(self._make_hex(mode_byte=0x00))
        assert status.canister_full is False
        assert status.mode_code == 0x00

    def test_parse_unknown_codes_get_unknown_labels(self) -> None:
        status = parse_status_hex(
            self._make_hex(state=0x99, error=0xFE, mode_byte=0x0F)
        )
        assert status.state_label.startswith("unknown_")
        assert status.error_label.startswith("unknown_")
        assert status.mode_label.startswith("unknown_")

    def test_parse_invalid_length_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_status_hex("AABB")

    def test_parse_invalid_hex_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_status_hex("zz" * 18)

    def test_parse_strips_spaces(self) -> None:
        raw = self._make_hex()
        with_spaces = " ".join(raw[i : i + 2] for i in range(0, len(raw), 2))
        status_a = parse_status_hex(raw)
        status_b = parse_status_hex(with_spaces)
        assert status_a == status_b
