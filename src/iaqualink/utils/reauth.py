from __future__ import annotations

from collections.abc import Awaitable, Callable

from iaqualink.exception import AqualinkServiceUnauthorizedException


async def send_with_reauth_retry[T](
    request_factory: Callable[[], Awaitable[T]],
    refresh_auth: Callable[[], Awaitable[None]],
) -> T:
    try:
        return await request_factory()
    except AqualinkServiceUnauthorizedException:
        await refresh_auth()

    return await request_factory()
