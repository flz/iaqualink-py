"""zs500 conformance-fixture declarations.

zs500 commands go over a persistent MQTT shadow connection rather than
httpx, and the conformance suite (tests/conformance/*) only mocks httpx via
respx — every generic contract test there asserts against
``respx_mock.calls``, which would always be empty for zs500. So none of
zs500's factories participate; all lists are declared empty per the
discovery convention (see tests/conformance/conftest.py), and correctness is
covered instead by the bespoke tests in this directory (test_system.py,
test_device.py) using the FakeShadowClient harness in conftest.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

zs500_device_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_sensor_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_binary_sensor_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_switch_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_light_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_climate_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_number_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_select_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_fan_factories: list[tuple[str, Callable[[], Any]]] = []
zs500_system_factories: list[tuple[str, Callable[[], Any]]] = []
