from __future__ import annotations


class AqualinkException(Exception):  # noqa: N818
    """Base exception for iAqualink library."""


class AqualinkInvalidParameterException(AqualinkException):
    """Exception raised when an invalid parameter is passed."""


class AqualinkServiceException(AqualinkException):
    """Exception raised when an error is raised by the iaqualink service."""


class AqualinkServiceUnauthorizedException(AqualinkServiceException):
    """Exception raised when service access is unauthorized."""


class AqualinkSystemOfflineException(AqualinkServiceException):
    """Exception raised when a system is offline."""


class AqualinkServiceThrottledException(AqualinkServiceException):
    """Exception raised when the service returns 429 Too Many Requests."""


class AqualinkOperationNotSupportedException(AqualinkException):
    """Exception raised when trying to issue an unsupported operation."""


class AqualinkDeviceNotSupported(AqualinkException):
    """Exception raised when a device isn't known-unsupported."""


class _AqualinkSystemUnsupportedDeprecated(AqualinkServiceException):
    """Deprecated stub; see AqualinkSystemUnsupportedException."""


def __getattr__(name: str) -> type[_AqualinkSystemUnsupportedDeprecated]:
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
