from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt

from iaqualink.exception import AqualinkServiceUnauthorizedException

if TYPE_CHECKING:
    import httpx


async def send_with_reauth_retry(
    request_factory: Callable[[], Awaitable[httpx.Response]],
    refresh_auth: Callable[[], Awaitable[None]],
    can_refresh: Callable[[], bool] | None = None,
) -> httpx.Response:
    should_retry = False

    def should_retry_unauthorized(exc: BaseException) -> bool:
        return should_retry and isinstance(
            exc, AqualinkServiceUnauthorizedException
        )

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(2),
        retry=retry_if_exception(should_retry_unauthorized),
        reraise=True,
    ):
        with attempt:
            try:
                return await request_factory()
            except AqualinkServiceUnauthorizedException:
                should_retry = False
                if attempt.retry_state.attempt_number == 1 and (
                    can_refresh is None or can_refresh()
                ):
                    should_retry = True
                    await refresh_auth()
                raise

    raise AssertionError("unreachable")
