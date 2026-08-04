from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Boolean,
    Integer,
    BigInteger,
    Text,
    Date,
    DateTime,
    Numeric,
    SmallInteger,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    func,
    text,
    Enum as sa_Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.mixins import (
    TimestampMixin,
    AuditMixin,
    TenantScopedMixin,
    SoftDeleteMixin,
)


class ProductCategory(str, enum.Enum):
    EQUIPMENT = "equipment"
    SUPPLEMENT = "supplement"
    MERCHANDISE = "merchandise"
    CONSUMABLE = "consumable"
    SERVICE = "service"


class InventoryTransactionType(str, enum.Enum):
    PURCHASE_IN = "purchase_in"
    SALE_OUT = "sale_out"
    ADJUSTMENT = "adjustment"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    RETURN = "return"
    WRITE_OFF = "write_off"


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Supplier(Base, AuditMixin):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    email: Mapped[Optional[str]] = mapped_column(Text, default=None)
    phone: Mapped[Optional[str]] = mapped_column(Text, default=None)
    address: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        "PurchaseOrder",
        back_populates="supplier",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            func.lower(name),
            name="uq_suppliers_org_name",
            postgresql_where=deleted_at.is_(None),
        ),
        Index("organization_id"),
        {"extend_existing": True},
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<Supplier(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r})>"
        )


class Product(Base, AuditMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[Optional[str]] = mapped_column(Text, default=None)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    category: Mapped[ProductCategory] = mapped_column(
        sa_Enum(ProductCategory, name="productcategory"),
        nullable=False,
    )
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_service: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )

    inventories: Mapped[list["Inventory"]] = relationship(
        "Inventory",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            func.lower(sku),
            name="uq_products_org_sku",
            postgresql_where=sku.isnot(None) & deleted_at.is_(None),
        ),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_products_unit_price_non_negative"
        ),
        Index("organization_id", "is_active", "category"),
        {"extend_existing": True},
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<Product(id={self.id}, organization_id={self.organization_id}, "
            f"sku={self.sku!r}, name={self.name!r})>"
        )


class StockLocation(Base, AuditMixin):
    __tablename__ = "stock_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_branches.id", ondelete="SET NULL"),
        default=None,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    inventories: Mapped[list["Inventory"]] = relationship(
        "Inventory",
        back_populates="location",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_stock_locations_org_code",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("organization_id"),
        {"extend_existing": True},
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<StockLocation(id={self.id}, organization_id={self.organization_id}, "
            f"code={self.code!r})>"
        )


class Inventory(Base, TimestampMixin):
    __tablename__ = "inventories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_locations.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped[Product] = relationship(
        "Product",
        back_populates="inventories",
    )
    location: Mapped[StockLocation] = relationship(
        "StockLocation",
        back_populates="inventories",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "product_id",
            "location_id",
            name="uq_inventories_product_location",
        ),
        CheckConstraint(
            "quantity_on_hand >= 0", name="ck_inventories_quantity_on_hand_non_negative"
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="ck_inventories_reserved_quantity_non_negative",
        ),
        Index("organization_id"),
        {"extend_existing": True},
    )

    @property
    def available_quantity(self) -> int:
        return self.quantity_on_hand - self.reserved_quantity

    def __repr__(self) -> str:
        return (
            f"<Inventory(id={self.id}, organization_id={self.organization_id}, "
            f"product_id={self.product_id}, location_id={self.location_id})>"
        )


class PurchaseOrder(Base, AuditMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_number: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        sa_Enum(PurchaseOrderStatus, name="purchaseorderstatus"),
        nullable=False,
        default=PurchaseOrderStatus.DRAFT,
    )
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    ordered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    expected_at: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    supplier: Mapped[Supplier] = relationship(
        "Supplier",
        back_populates="purchase_orders",
    )
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "order_number",
            name="uq_purchase_orders_org_number",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "total_cents >= 0", name="ck_purchase_orders_total_non_negative"
        ),
        Index("organization_id"),
        {"extend_existing": True},
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrder(id={self.id}, organization_id={self.organization_id}, "
            f"order_number={self.order_number!r}, status={self.status})>"
        )


class PurchaseOrderItem(Base, TimestampMixin):
    __tablename__ = "purchase_order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder",
        back_populates="items",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0", name="ck_purchase_order_items_quantity_positive"
        ),
        CheckConstraint(
            "unit_cost_cents >= 0",
            name="ck_purchase_order_items_unit_cost_non_negative",
        ),
        CheckConstraint(
            "received_quantity >= 0",
            name="ck_purchase_order_items_received_quantity_non_negative",
        ),
        CheckConstraint(
            "received_quantity <= quantity",
            name="ck_purchase_order_items_received_quantity_lte_quantity",
        ),
        Index("purchase_order_id"),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderItem(id={self.id}, purchase_order_id={self.purchase_order_id}, "
            f"product_id={self.product_id}, quantity={self.quantity})>"
        )


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_locations.id", ondelete="SET NULL"),
        default=None,
    )
    transaction_type: Mapped[InventoryTransactionType] = mapped_column(
        sa_Enum(InventoryTransactionType, name="inventorytransactiontype"),
        nullable=False,
    )
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(Text, default=None)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None
    )
    balance_after: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("quantity_change != 0", name="ck_inv_tx_nonzero"),
        Index("organization_id", "product_id", created_at.desc()),
        Index(
            "organization_id",
            "location_id",
            created_at.desc(),
            postgresql_where=location_id.isnot(None),
            name="ix_inventory_transactions_org_location_time",
        ),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryTransaction(id={self.id}, organization_id={self.organization_id}, "
            f"product_id={self.product_id}, quantity_change={self.quantity_change})>"
        )
