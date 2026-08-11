class PermissionDenied(Exception):
    """Raised when a user lacks a required permission."""


class RoleNotFound(Exception):
    """Raised when a role does not exist or is not visible."""


class PermissionNotFound(Exception):
    """Raised when a permission code does not exist."""


class UserNotInOrganization(Exception):
    """Raised when assigning a role to a user outside the organization."""


class BranchNotInOrganization(Exception):
    """Raised when assigning a branch-scoped role outside the organization."""
