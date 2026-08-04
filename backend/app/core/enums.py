from __future__ import annotations

import enum


class OrganizationStatus(str, enum.Enum):
    """Status of an organization/tenant."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PENDING = "pending"


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
