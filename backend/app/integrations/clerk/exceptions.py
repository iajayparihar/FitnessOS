class ClerkConfigurationError(RuntimeError):
    """Raised when the Clerk integration is not configured."""


class ClerkAuthenticationError(ValueError):
    """Raised when a Clerk session token is invalid or malformed."""
