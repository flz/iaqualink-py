from __future__ import annotations

from typing import Final

I2D_CONTROL_URL = "https://r-api.iaqualink.net/v2/devices/{serial}/control.json"

# Hex-encoded request strings.
I2D_REQUEST_STATUS: Final = "OA11"
I2D_REQUEST_START: Final = "0A1240&timeout=800"
I2D_REQUEST_STOP: Final = "0A1210&timeout=800"
I2D_REQUEST_RETURN_TO_BASE: Final = "0A1701&timeout=800"

# State byte (data[2]).
I2D_STATE_LABELS: Final[dict[int, str]] = {
    0x01: "idle_or_docked",
    0x02: "cleaning_just_started",
    0x03: "finished",
    0x04: "actively_cleaning",
    0x0C: "paused",
    0x0D: "error_state_d",
    0x0E: "error_state_e",
}

# Error byte (data[3]).
I2D_ERROR_LABELS: Final[dict[int, str]] = {
    0x00: "no_error",
    0x01: "pump_short_circuit",
    0x02: "right_drive_motor_short_circuit",
    0x03: "left_drive_motor_short_circuit",
    0x04: "pump_motor_overconsumption",
    0x05: "right_drive_motor_overconsumption",
    0x06: "left_drive_motor_overconsumption",
    0x07: "floats_on_surface",
    0x08: "running_out_of_water",
    0x0A: "communication_error",
}

# Mode nibble (lower 4 bits of data[4]).
I2D_MODE_LABELS: Final[dict[int, str]] = {
    0x00: "quick_clean_floor_only_standard",
    0x03: "deep_clean_floor_and_walls_high_power",
    0x04: "waterline_only_standard",
    0x08: "quick_floor_only_standard",
    0x09: "custom_floor_only_high_power",
    0x0A: "custom_floor_and_walls_standard",
    0x0B: "custom_floor_and_walls_high_power",
    0x0C: "waterline_only_standard_v2",
    0x0D: "custom_waterline_high_power",
    0x0E: "custom_waterline_standard",
}
