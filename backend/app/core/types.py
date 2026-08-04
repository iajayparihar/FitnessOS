from __future__ import annotations

import uuid
from sqlalchemy import BigInteger, String, TypeDecorator, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID


# Type alias for UUID primary keys
# Usage: id: Mapped[PrimaryKey] = mapped_column(primary_key=True)
class PrimaryKey(TypeDecorator):
    """UUID primary key with automatic uuid.uuid4() default."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def __init__(self):
        super().__init__()
        self.default = uuid.uuid4


# Type alias for integer primary keys (lookup/join tables only)
class IntPK(TypeDecorator):
    """Integer primary key for lookup and join tables."""

    impl = BigInteger
    cache_ok = True


class MoneyAmount(TypeDecorator):
    """
    BigInteger type for monetary amounts.
    Stored in smallest currency unit (paise/cents).
    Never use Float for money.

    Example: $10.50 = 1050 (in cents)
    Example: ₹100.50 = 10050 (in paise)
    """

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert input value to integer."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        # Assume decimal.Decimal or float converted to cents/paise
        return int(value)

    def process_result_value(self, value, dialect):
        """Ensure output is always integer."""
        if value is None:
            return None
        return int(value)


class CurrencyCode(String):
    """ISO 4217 currency code (3 characters, e.g., USD, INR, EUR)."""

    def __init__(self):
        super().__init__(3)
