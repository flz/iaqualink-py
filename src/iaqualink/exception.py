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


class AqualinkSystemUnsupportedException(AqualinkServiceException):
    """Exception raised when a system isn't supported by the library."""


class AqualinkOperationNotSupportedException(AqualinkException):
    """Exception raised when trying to issue an unsupported operation."""


class AqualinkDeviceNotSupported(AqualinkException):
    """Exception raised when a device isn't known-unsupported."""
