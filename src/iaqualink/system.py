from __future__ import annotations

import enum
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ClassVar

from iaqualink.reauth import send_with_reauth_retry

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.device import AqualinkDevice
    from iaqualink.typing import Payload


LOGGER = logging.getLogger("iaqualink")


class SystemStatus(enum.Enum):
    CONNECTED = enum.auto()
    ONLINE = enum.auto()
    DISCONNECTED = enum.auto()
    OFFLINE = enum.auto()
    UNKNOWN = enum.auto()
    SERVICE = enum.auto()
    FIRMWARE_UPDATE = enum.auto()
    IN_PROGRESS = enum.auto()


class SystemStatusColor(enum.Enum):
    GREEN = "green"
    RED = "red"
    YELLOW = "yellow"
    IN_PROGRESS = None  # spinner / no color


_STATUS_COLOR_MAP: dict[SystemStatus, SystemStatusColor] = {
    SystemStatus.CONNECTED: SystemStatusColor.GREEN,
    SystemStatus.ONLINE: SystemStatusColor.GREEN,
    SystemStatus.DISCONNECTED: SystemStatusColor.RED,
    SystemStatus.OFFLINE: SystemStatusColor.RED,
    SystemStatus.UNKNOWN: SystemStatusColor.RED,
    SystemStatus.SERVICE: SystemStatusColor.YELLOW,
    SystemStatus.FIRMWARE_UPDATE: SystemStatusColor.YELLOW,
    SystemStatus.IN_PROGRESS: SystemStatusColor.IN_PROGRESS,
}


class AqualinkSystem:
    subclasses: ClassVar[dict[str, type[AqualinkSystem]]] = {}

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        self.aqualink = aqualink
        self.data = data
        self.devices: dict[str, AqualinkDevice] = {}
        self._status: SystemStatus = SystemStatus.IN_PROGRESS

    @classmethod
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if hasattr(cls, "NAME"):
            cls.subclasses[cls.NAME] = cls

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({', '.join(attrs)})"

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def serial(self) -> str:
        return self.data["serial_number"]

    @property
    def type(self) -> str:
        return self.data["device_type"]

    @property
    def supported(self) -> bool:
        return True

    @classmethod
    def from_data(
        cls, aqualink: AqualinkClient, data: Payload
    ) -> AqualinkSystem:
        if data["device_type"] not in cls.subclasses:
            return UnsupportedSystem(aqualink, data)

        return cls.subclasses[data["device_type"]](aqualink, data)

    async def get_devices(self) -> dict[str, AqualinkDevice]:
        if not self.devices:
            await self.update()
        return self.devices

    async def _send_with_reauth_retry(
        self,
        request_factory: Callable[[], Awaitable[httpx.Response]],
    ) -> httpx.Response:
        return await send_with_reauth_retry(
            request_factory,
            self.aqualink._refresh_auth,
        )

    @property
    def status(self) -> SystemStatus:
        raise NotImplementedError

    @property
    def status_color(self) -> SystemStatusColor:
        return _STATUS_COLOR_MAP[self.status]

    @property
    def status_translated(self) -> str:
        return self.status.name.replace("_", " ").title()

    async def update(self) -> None:
        raise NotImplementedError


class UnsupportedSystem(AqualinkSystem):
    @property
    def supported(self) -> bool:
        return False

    @property
    def status(self) -> SystemStatus:
        return SystemStatus.UNKNOWN

    async def update(self) -> None:
        LOGGER.debug("Skipping update for unsupported system %r", self.serial)

    async def get_devices(self) -> dict[str, AqualinkDevice]:
        LOGGER.debug(
            "Skipping get_devices for unsupported system %r", self.serial
        )
        return {}
