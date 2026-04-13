from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from iaqualink.exception import AqualinkServiceUnauthorizedException

if TYPE_CHECKING:
    import httpx


async def send_with_reauth_retry(
    request_factory: Callable[[], Awaitable[httpx.Response]],
    refresh_auth: Callable[[], Awaitable[None]],
) -> httpx.Response:
    try:
        return await request_factory()
    except AqualinkServiceUnauthorizedException:
        await refresh_auth()

    return await request_factory()
