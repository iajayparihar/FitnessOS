class InvalidCredentials(Exception):
    """Raised when supplied credentials or tokens are invalid."""


class InactiveUser(Exception):
    """Raised when an inactive user tries to authenticate."""


class InvalidAuthActionToken(Exception):
    """Raised when an auth action token is invalid, expired, or already used."""


class AuthActionRateLimited(Exception):
    """Raised when an auth action is requested too frequently."""
