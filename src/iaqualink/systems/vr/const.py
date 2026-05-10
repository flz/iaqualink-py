from __future__ import annotations

from typing import Final

# --- robot state (runtime) ----------------------------------------------

VR_STATE_STOPPED: Final = 0
VR_STATE_CLEANING: Final = 1
VR_STATE_PAUSED: Final = 2
VR_STATE_RETURNING: Final = 3

VR_STATE_LABELS: Final[dict[int, str]] = {
    VR_STATE_STOPPED: "stopped",
    VR_STATE_CLEANING: "cleaning",
    VR_STATE_PAUSED: "paused",
    VR_STATE_RETURNING: "returning",
}

# --- cycle / programme (prCyc field) ------------------------------------

CYCLE_WALL_ONLY: Final = 0
CYCLE_FLOOR_ONLY: Final = 1
CYCLE_SMART_FLOOR_AND_WALLS: Final = 2
CYCLE_FLOOR_AND_WALLS: Final = 3

CYCLE_LABELS: Final[dict[int, str]] = {
    CYCLE_WALL_ONLY: "wall_only",
    CYCLE_FLOOR_ONLY: "floor_only",
    CYCLE_SMART_FLOOR_AND_WALLS: "smart_floor_and_walls",
    CYCLE_FLOOR_AND_WALLS: "floor_and_walls",
}

# --- remote control (rmt_ctrl field) ------------------------------------

REMOTE_STOP: Final = 0
REMOTE_FORWARD: Final = 1
REMOTE_BACKWARD: Final = 2
REMOTE_ROTATE_RIGHT: Final = 3
REMOTE_ROTATE_LEFT: Final = 4

# Runtime extension increment (mirrors stepperAdjTime; 15 min default).
RUNTIME_EXTENSION_STEP_MIN: Final = 15
