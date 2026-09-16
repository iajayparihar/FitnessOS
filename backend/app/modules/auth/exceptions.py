class AlreadyOnboarded(Exception):
    """Raised when a user who already belongs to an organization onboards again."""


class InviteInvalid(Exception):
    """Raised when an invite is missing, expired, already used, or mismatched."""
