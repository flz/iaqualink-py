from __future__ import annotations


class AqualinkException(Exception):
    """Base exception for iAqualink library."""


class AqualinkLoginException(AqualinkException):
    """Exception raised when failing to log in."""


class AqualinkSystemOfflineException(AqualinkException):
    """Exception raised when a system is offline."""


class AqualinkInvalidParameterException(AqualinkException):
    """Exception raised when an invalid parameter is passed."""


class AqualinkServiceException(AqualinkException):
    """Exception raised when an error is raised by the iaqualink service."""
