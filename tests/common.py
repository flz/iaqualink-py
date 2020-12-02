from __future__ import annotations

import asynctest


async_noop = asynctest.CoroutineMock(return_value=None)


def async_returns(x):
    return asynctest.CoroutineMock(return_value=x)


def async_raises(x):
    return asynctest.CoroutineMock(side_effect=x)
