from __future__ import annotations

from enum import StrEnum, unique


@unique
class ExoSystemStatus(StrEnum):
    CONNECTED = "connected"
    ONLINE = "online"
    OFFLINE = "offline"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"
    SERVICE = "service"
    FIRMWARE_UPDATE = "firmware_update"
    IN_PROGRESS = "in_progress"
