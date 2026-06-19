from __future__ import annotations

from enum import StrEnum


class AqualinkRobotActivity(StrEnum):
    """Operational state of a robot cleaner.

    Mirrors Home Assistant's ``homeassistant.components.vacuum.VacuumActivity``
    so concrete robots map onto the HA vacuum entity without translation.
    """

    CLEANING = "cleaning"
    DOCKED = "docked"
    IDLE = "idle"
    PAUSED = "paused"
    RETURNING = "returning"
    ERROR = "error"
