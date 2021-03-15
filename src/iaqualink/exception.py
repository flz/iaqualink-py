from __future__ import annotations


class AqualinkException(Exception):
    """Base exception for iAqualink library."""


class AqualinkSystemOfflineException(AqualinkException):
    """Exception raised when a system is offline."""


class AqualinkInvalidParameterException(AqualinkException):
    """Exception raised when an invalid parameter is passed."""


class AqualinkServiceException(AqualinkException):
    """Exception raised when an error is raised by the iaqualink service."""


class AqualinkServiceUnauthorizedException(AqualinkServiceException):
    """Exception raised when service access is unauthorized."""
