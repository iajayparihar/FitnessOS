from __future__ import annotations

import enum


class OrganizationStatus(str, enum.Enum):
    """Status of an organization/tenant."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PENDING = "pending"
    ARCHIVED = "archived"

    @classmethod
    def operational(cls) -> frozenset[OrganizationStatus]:
        """Return the states in which normal tenant operations are permitted."""
        return frozenset({cls.ACTIVE, cls.PENDING})


class BusinessType(str, enum.Enum):
    """Kind of fitness business an organization operates."""

    GYM = "gym"
    FITNESS_STUDIO = "fitness_studio"
    YOGA = "yoga"
    CROSSFIT = "crossfit"
    PERSONAL_TRAINING = "personal_training"
    NUTRITION = "nutrition"
    WELLNESS = "wellness"
    OTHER = "other"


class OrganizationMemberRole(str, enum.Enum):
    """
    Seat a user holds inside an organization.

    This is the coarse organization-level seat. Fine-grained authorization stays
    with the RBAC permission system; this value exists so invariants such as
    "an organization always keeps one owner" can be enforced, and so the RBAC
    role assigned at provisioning time has a stable counterpart.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    TRAINER = "trainer"
    STAFF = "staff"
    MEMBER = "member"


class OrganizationMemberStatus(str, enum.Enum):
    """Lifecycle of a user's membership in an organization."""

    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class BillingCycle(str, enum.Enum):
    """Billing frequency for subscriptions."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Currency(str, enum.Enum):
    """Supported currencies (ISO 4217)."""

    INR = "INR"
    USD = "USD"
    GBP = "GBP"
    EUR = "EUR"


class Gender(str, enum.Enum):
    """Gender options for member/user profiles."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class PaymentStatus(str, enum.Enum):
    """Status of a payment transaction."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    """Payment method/instrument."""

    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    CHEQUE = "cheque"
    GATEWAY = "gateway"


class NotificationChannel(str, enum.Enum):
    """Channel through which notifications are sent."""

    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    INAPP = "inapp"


class NotificationStatus(str, enum.Enum):
    """Status of a sent notification."""

    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActorType(str, enum.Enum):
    """Type of actor performing an action (for audit logs)."""

    USER = "user"
    SYSTEM = "system"
    API_KEY = "api_key"
