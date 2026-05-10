from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import TYPE_CHECKING, ClassVar

from iaqualink.reauth import send_with_reauth_retry

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.device import AqualinkDevice
    from iaqualink.typing import Payload


LOGGER = logging.getLogger("iaqualink")


class AqualinkSystem:
    subclasses: ClassVar[dict[str, type[AqualinkSystem]]] = {}
    MIN_SECS_TO_REFRESH: ClassVar[int] = 5

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        self.aqualink = aqualink
        self.data = data
        self.devices: dict[str, AqualinkDevice] = {}
        self.last_refresh: int

        # Semantics here are somewhat odd.
        # True/False are obvious, None means "unknown".
        self.online: bool | None = None

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
    def supported(self) -> bool:
        return True

    @classmethod
    def from_data(
        cls, aqualink: AqualinkClient, data: Payload
    ) -> AqualinkSystem:
        if data["device_type"] not in cls.subclasses:
            LOGGER.warning(
                "%s is not a supported system type.", data["device_type"]
            )
            # UnsupportedSystem is defined after this class in this module.
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

    async def update(self) -> None:
        raise NotImplementedError


class UnsupportedSystem(AqualinkSystem):
    @property
    def supported(self) -> bool:
        return False

    async def update(self) -> None:
        LOGGER.debug("Skipping update for unsupported system %r", self.serial)

    async def get_devices(self) -> dict[str, AqualinkDevice]:
        return {}
