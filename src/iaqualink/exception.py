from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


class AqualinkException(Exception):  # noqa: N818
    """Base exception for iAqualink library."""


class AqualinkInvalidParameterException(AqualinkException):
    """Exception raised when an invalid parameter is passed."""


class AqualinkServiceException(AqualinkException):
    """Exception raised when an error is raised by the iaqualink service."""

    def __init__(
        self, *args: Any, response: httpx.Response | None = None
    ) -> None:
        super().__init__(*args)
        self.response = response


class AqualinkServiceUnauthorizedException(AqualinkServiceException):
    """Exception raised when service access is unauthorized."""


class AqualinkServiceThrottledException(AqualinkServiceException):
    """Exception raised when the service returns 429 Too Many Requests."""


class _AqualinkOfflineSignal(AqualinkServiceException):
    """Internal signal: raised by _refresh() to indicate device-offline.

    Caught by AqualinkSystem.refresh(); never propagates to callers.
    Do not catch or raise this outside of the iaqualink package internals.
    """


class AqualinkOperationNotSupportedException(AqualinkException):
    """Exception raised when trying to issue an unsupported operation."""


class AqualinkStateUnavailableException(AqualinkException):
    """Exception raised when accessing state that requires refresh() to be called first."""


class _AqualinkSystemUnsupportedDeprecated(AqualinkServiceException):
    """Backward-compat stub; use iaqualink.system.UnsupportedSystem instead."""


def __getattr__(name: str) -> Any:
    if name == "AqualinkSystemUnsupportedException":
        import warnings

        warnings.warn(
            "AqualinkSystemUnsupportedException is deprecated and will be removed "
            "in a future release. Unknown device types now return "
            "iaqualink.system.UnsupportedSystem instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _AqualinkSystemUnsupportedDeprecated
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
