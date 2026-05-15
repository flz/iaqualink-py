from __future__ import annotations

import enum
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ClassVar

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
)
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


class AqualinkSystem:
    subclasses: ClassVar[dict[str, type[AqualinkSystem]]] = {}

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        self.aqualink = aqualink
        self.data = data
        self.devices: dict[str, AqualinkDevice] = {}
        self._status: SystemStatus | None = None

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
            await self.refresh()
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
        return (
            self._status
            if self._status is not None
            else SystemStatus.IN_PROGRESS
        )

    @status.setter
    def status(self, value: SystemStatus) -> None:
        self._status = value

    @property
    def status_translated(self) -> str:
        return self.status.name.replace("_", " ").title()

    async def refresh(self) -> None:
        self._status = None  # sentinel: not yet set by _refresh()
        try:
            await self._refresh()
        except AqualinkServiceThrottledException:
            self.status = SystemStatus.UNKNOWN
            raise
        except AqualinkServiceException:
            self.status = SystemStatus.DISCONNECTED
            raise
        if self._status is None:
            LOGGER.warning(
                "%s._refresh() returned without updating status",
                type(self).__name__,
            )

    async def _refresh(self) -> None:
        """Fetch and parse the latest state from the API.

        Called by `refresh()`, which owns the status lifecycle. Implementors
        must follow this contract:

        **Status on normal return:**
        Set `self.status` before returning. `refresh()` uses an internal
        `None` sentinel to detect whether the setter was called; it logs a
        warning if `_refresh()` returns without ever writing `self.status`.
        Setting `self.status = SystemStatus.IN_PROGRESS` is valid and will
        not trigger the warning.

        **`AqualinkServiceThrottledException` / `AqualinkServiceException`:**
        Do not catch these. `refresh()` intercepts them and sets `UNKNOWN` or
        `DISCONNECTED` respectively before re-raising.

        **All other exceptions** propagate unchanged.
        """
        raise NotImplementedError


class UnsupportedSystem(AqualinkSystem):
    def __init__(self, aqualink: AqualinkClient, data: Payload) -> None:
        super().__init__(aqualink, data)
        self.status = SystemStatus.UNKNOWN

    @property
    def supported(self) -> bool:
        return False

    async def refresh(self) -> None:
        LOGGER.debug("Skipping refresh for unsupported system %r", self.serial)

    async def get_devices(self) -> dict[str, AqualinkDevice]:
        LOGGER.debug(
            "Skipping get_devices for unsupported system %r", self.serial
        )
        return {}
