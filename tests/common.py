from __future__ import annotations

from unittest.mock import AsyncMock

async_noop = AsyncMock(return_value=None)


def async_returns(x):
    return AsyncMock(return_value=x)


def async_raises(x):
    return AsyncMock(side_effect=x)
