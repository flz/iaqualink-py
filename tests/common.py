from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

async_noop = AsyncMock(return_value=None)


def async_returns(x: Any) -> AsyncMock:
    return AsyncMock(return_value=x)


def async_raises(x: Any) -> AsyncMock:
    return AsyncMock(side_effect=x)
