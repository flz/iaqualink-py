from __future__ import annotations

from typing import Final

# --- robot main.state (runtime) -----------------------------------------

CYCLOBAT_STATE_STOPPED: Final = 0
CYCLOBAT_STATE_CLEANING: Final = 1
CYCLOBAT_STATE_RETURNING: Final = 3

CYCLOBAT_STATE_LABELS: Final[dict[int, str]] = {
    CYCLOBAT_STATE_STOPPED: "stopped",
    CYCLOBAT_STATE_CLEANING: "cleaning",
    CYCLOBAT_STATE_RETURNING: "returning",
}

# --- main.ctrl (write target) -------------------------------------------

CYCLOBAT_CTRL_STOP: Final = 0
CYCLOBAT_CTRL_START: Final = 1
CYCLOBAT_CTRL_RETURN: Final = 3

# --- cycle (lastCycle.endCycleType / cycles dict key) -------------------

CYCLE_FLOOR: Final = 0
CYCLE_FLOOR_AND_WALLS: Final = 1
CYCLE_SMART: Final = 2
CYCLE_WATERLINE: Final = 3

CYCLE_LABELS: Final[dict[int, str]] = {
    CYCLE_FLOOR: "floor",
    CYCLE_FLOOR_AND_WALLS: "floor_and_walls",
    CYCLE_SMART: "smart",
    CYCLE_WATERLINE: "waterline",
}

# Maps cycle id -> key in shadow.cycles to read .duration.
CYCLE_DURATION_KEY: Final[dict[int, str]] = {
    CYCLE_FLOOR: "floorTim",
    CYCLE_FLOOR_AND_WALLS: "floorWallsTim",
    CYCLE_SMART: "smartTim",
    CYCLE_WATERLINE: "waterlineTim",
}
