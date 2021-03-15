from __future__ import annotations

__author__ = "Florent Thoumie"
__email__ = "florent@thoumie.net"
__version__ = "0.3.5"


from .client import AqualinkClient
from .system import AqualinkSystem, AqualinkPoolSystem
from .device import (
    AqualinkAuxToggle,
    AqualinkBinarySensor,
    AqualinkColorLight,
    AqualinkDevice,
    AqualinkDimmableLight,
    AqualinkHeater,
    AqualinkLight,
    AqualinkLightToggle,
    AqualinkLightType,
    AqualinkPump,
    AqualinkSensor,
    AqualinkState,
    AqualinkThermostat,
    AqualinkToggle,
)
