from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional, Type

from iaqualink.exception import AqualinkSystemUnsupportedException
from iaqualink.typing import Payload

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient
    from iaqualink.device import AqualinkDevice


LOGGER = logging.getLogger("iaqualink")


class AqualinkSystem:
    subclasses: Dict[str, Type[AqualinkSystem]] = {}

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        self.aqualink = aqualink
        self.data = data
        self.devices: Dict[str, AqualinkDevice] = {}
        self.last_refresh = 0

        # Semantics here are somewhat odd.
        # True/False are obvious, None means "unknown".
        self.online: Optional[bool] = None

    @classmethod
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if hasattr(cls, "NAME"):
            cls.subclasses[getattr(cls, "NAME")] = cls

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return f'{self.__class__.__name__}({", ".join(attrs)})'

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def serial(self) -> str:
        return self.data["serial_number"]

    @classmethod
    def from_data(
        cls, aqualink: AqualinkClient, data: Payload
    ) -> AqualinkSystem:
        if data["device_type"] not in cls.subclasses:
            m = f"{data['device_type']} is not a supported system type."
            LOGGER.warning(m)
            raise AqualinkSystemUnsupportedException(m)

        return cls.subclasses[data["device_type"]](aqualink, data)

    async def get_devices(self) -> Dict[str, AqualinkDevice]:
        if not self.devices:
            await self.update()
        return self.devices

    async def update(self) -> None:
        raise NotImplementedError
