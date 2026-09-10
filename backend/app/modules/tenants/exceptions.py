"""
Tenant-domain exceptions.

Cross-tenant access deliberately raises the same "not found" error as a missing
record, so a caller cannot use response codes to probe which identifiers exist in
other organizations.
"""


class OrgNotFound(Exception):
    """Raised when an organization is not visible to the current caller."""


class SlugUnavailable(Exception):
    """Raised when an organization slug is already taken."""


class NotAnOrganizationMember(Exception):
    """Raised when a user has no active membership in the target organization."""


class OrganizationNotOperational(Exception):
    """Raised when an organization's status forbids normal tenant operations."""


class MembershipNotFound(Exception):
    """Raised when a membership is absent or belongs to another tenant."""


class DuplicateMembership(Exception):
    """Raised when a user already has a live membership in the organization."""


class LastOwnerRemoval(Exception):
    """Raised when removing or demoting the organization's final owner."""


class BranchNotFound(Exception):
    """Raised when a branch is absent or belongs to another tenant."""


class MainBranchRequired(Exception):
    """Raised when an action would leave the organization without a main branch."""


class UserNotFound(Exception):
    """Raised when the user being added to an organization does not exist."""


class SelfRoleChangeNotAllowed(Exception):
    """Raised when an actor attempts to change their own membership role."""


class OwnerSeatRequiresOwner(Exception):
    """Raised when a non-owner actor tries to grant or revoke the owner seat."""
