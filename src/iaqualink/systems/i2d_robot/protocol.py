from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from iaqualink.systems.i2d_robot.const import (
    I2D_ERROR_LABELS,
    I2D_MODE_LABELS,
    I2D_STATE_LABELS,
)

EXPECTED_HEX_LEN: Final = 36  # 18 bytes


@dataclass(frozen=True)
class I2dStatus:
    state_code: int
    error_code: int
    mode_code: int
    canister_full: bool
    time_remaining_min: int
    uptime_min: int
    total_hours: int
    hardware_id: str
    firmware_id: str

    @property
    def state_label(self) -> str:
        return I2D_STATE_LABELS.get(
            self.state_code,
            f"unknown_{self.state_code:02X}",
        )

    @property
    def error_label(self) -> str:
        return I2D_ERROR_LABELS.get(
            self.error_code,
            f"unknown_{self.error_code:02X}",
        )

    @property
    def mode_label(self) -> str:
        return I2D_MODE_LABELS.get(
            self.mode_code,
            f"unknown_{self.mode_code:02X}",
        )


def parse_status_hex(hex_str: str) -> I2dStatus:
    # Raises ValueError when the input is malformed.
    cleaned = hex_str.replace(" ", "")
    if len(cleaned) != EXPECTED_HEX_LEN:
        msg = f"Expected {EXPECTED_HEX_LEN} hex characters; got {len(cleaned)}."
        raise ValueError(msg)
    try:
        data = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid hex string: {exc}") from exc

    state_code = data[2]
    error_code = data[3]
    mode_byte = data[4]
    mode_code = mode_byte & 0x0F
    canister_full = (mode_byte & 0xF0) > 0
    time_remaining = data[5]
    uptime_min = int.from_bytes(data[6:9], byteorder="little")
    total_hours = int.from_bytes(data[9:12], byteorder="little")
    hardware_id = data[12:15].hex()
    firmware_id = data[15:18].hex()

    return I2dStatus(
        state_code=state_code,
        error_code=error_code,
        mode_code=mode_code,
        canister_full=canister_full,
        time_remaining_min=time_remaining,
        uptime_min=uptime_min,
        total_hours=total_hours,
        hardware_id=hardware_id,
        firmware_id=firmware_id,
    )
