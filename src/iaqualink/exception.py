from __future__ import annotations


class AqualinkException(Exception):
    """Base exception for iAqualink library."""


class AqualinkInvalidParameterException(AqualinkException):
    """Exception raised when an invalid parameter is passed."""


class AqualinkServiceException(AqualinkException):
    """Exception raised when an error is raised by the iaqualink service."""


class AqualinkServiceUnauthorizedException(AqualinkServiceException):
    """Exception raised when service access is unauthorized."""


class AqualinkSystemOfflineException(AqualinkServiceException):
    """Exception raised when a system is offline."""
