class InvalidCredentials(Exception):
    """Raised when supplied credentials or tokens are invalid."""


class InactiveUser(Exception):
    """Raised when an inactive user tries to authenticate."""


class AlreadyOnboarded(Exception):
    """Raised when a user that already belongs to a tenant is onboarded again."""
