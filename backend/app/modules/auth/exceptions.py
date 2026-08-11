class InvalidCredentials(Exception):
    """Raised when supplied credentials or tokens are invalid."""


class InactiveUser(Exception):
    """Raised when an inactive user tries to authenticate."""
