"""Tests for AqualinkSystem base-class contracts not covered by the conformance suite.

The conformance suite only parametrizes over concrete, supported system implementations.
These tests cover base-class behaviour: ABC enforcement and UnsupportedSystem routing.
"""

from __future__ import annotations

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.system import AqualinkSystem, UnsupportedSystem


class TestAqualinkSystemABC:
    def test_concrete_subclass_without_refresh_raises(self) -> None:
        """Subclassing AqualinkSystem without _refresh() raises TypeError."""

        with pytest.raises(TypeError):

            class _Incomplete(AqualinkSystem):  # type: ignore[abstract]
                pass

            _Incomplete(AqualinkClient("u", "p"), {"serial_number": "X"})


class TestUnsupportedSystem:
    def _make(self) -> UnsupportedSystem:
        client = AqualinkClient("u", "p")
        return UnsupportedSystem(
            client, {"serial_number": "SN001", "device_type": "unknown_xyz"}
        )

    def test_from_data_returns_unsupported_system(self) -> None:
        client = AqualinkClient("u", "p")
        system = AqualinkSystem.from_data(
            client, {"serial_number": "SN001", "device_type": "unknown_xyz"}
        )
        assert isinstance(system, UnsupportedSystem)

    def test_type_returns_raw_device_type_string(self) -> None:
        system = self._make()
        assert system.type == "unknown_xyz"

    def test_supported_is_false(self) -> None:
        system = self._make()
        assert system.supported is False
