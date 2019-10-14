class AqualinkException(Exception):
    """Base exception for iAqualink library."""


class AqualinkLoginException(AqualinkException):
    """Exception raised when failing to log in."""


class AqualinkSystemOfflineException(AqualinkException):
    """Exception raised when a system is offline."""
