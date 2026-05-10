from __future__ import annotations

from typing import Final

# Mode values (live RE 2026-04). ``MODE_PAUSE`` kept as an alias
# because earlier code used the name; mode==2 is actually the
# Remote-control surface, not a cycle pause.
MODE_STOP: Final = 0
MODE_START: Final = 1
MODE_REMOTE: Final = 2
MODE_PAUSE: Final = MODE_REMOTE
MODE_LIFT: Final = 3

MODE_LABELS: Final[dict[int, str]] = {
    MODE_STOP: "stopped",
    MODE_START: "running",
    MODE_REMOTE: "remote_control",
    MODE_LIFT: "lift_system",
}

# Cycle programme. Only Floor and Floor+Wall observed live on the Alpha
# series; higher-tier robots may expose deep/smart/scan/waterline.
CYCLE_FLOOR: Final = 1
CYCLE_FLOOR_AND_WALLS: Final = 3

CYCLE_LABELS: Final[dict[int, str]] = {
    CYCLE_FLOOR: "floor",
    CYCLE_FLOOR_AND_WALLS: "floor_and_walls",
}

# Each cycle id maps to a key in the shadow's `durations` dict.
CYCLE_DURATION_KEY: Final[dict[int, str]] = {
    CYCLE_FLOOR: "quickTim",
    CYCLE_FLOOR_AND_WALLS: "deepTim",
}

# Increment unit for runtime extension (mirrors `stepperAdjTime`).
RUNTIME_EXTENSION_STEP_MIN: Final = 15

# Direction — Remote screen (mode=2).
DIRECTION_STOP: Final = 0
DIRECTION_FORWARD: Final = 1
DIRECTION_BACKWARD: Final = 2
DIRECTION_ROTATE_RIGHT: Final = 3
DIRECTION_ROTATE_LEFT: Final = 4

# Direction — Lift screen (mode=3).
DIRECTION_LIFT_EJECT: Final = 5
DIRECTION_LIFT_ROTATE_LEFT: Final = 6
DIRECTION_LIFT_ROTATE_RIGHT: Final = 7

REMOTE_DIRECTION_LABELS: Final[dict[int, str]] = {
    DIRECTION_STOP: "stop",
    DIRECTION_FORWARD: "forward",
    DIRECTION_BACKWARD: "backward",
    DIRECTION_ROTATE_RIGHT: "rotate_right",
    DIRECTION_ROTATE_LEFT: "rotate_left",
}

LIFT_DIRECTION_LABELS: Final[dict[int, str]] = {
    DIRECTION_STOP: "stop",
    DIRECTION_LIFT_EJECT: "eject",
    DIRECTION_LIFT_ROTATE_LEFT: "rotate_left",
    DIRECTION_LIFT_ROTATE_RIGHT: "rotate_right",
}

# Duration keys observed in the shadow's `durations` dict.
DURATION_KEYS: Final[tuple[str, ...]] = (
    "customTim",
    "deepTim",
    "firstSmartTim",
    "quickTim",
    "scanTim",
    "smartTim",
    "waterTim",
)
