class ClerkConfigurationError(RuntimeError):
    """Raised when the Clerk integration is not configured."""


class ClerkAuthenticationError(ValueError):
    """Raised when a Clerk session token is invalid or malformed."""


class ClerkIdentityConflict(ClerkAuthenticationError):
    """
    Raised when a Clerk identity cannot own its email address locally.

    Happens when a FitnessOS user already holds the email but is not eligible for
    migration linking. Provisioning refuses rather than creating a shadow account
    or silently taking over the existing one.
    """
