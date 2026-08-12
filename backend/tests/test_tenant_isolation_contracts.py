import pytest

from app.modules.attendance.models import (
    AttendanceDevice,
    AttendanceQRToken,
    AttendanceRecord,
)
from app.modules.billing.models import (
    Coupon,
    Discount,
    Invoice,
    InvoiceItem,
    Payment,
    Refund,
)
from app.modules.crm.models import Lead, LeadActivity, LeadFollowUp, LeadSource, Note
from app.modules.inventory.models import (
    Inventory,
    InventoryTransaction,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockLocation,
    Supplier,
)
from app.modules.membership.models import (
    Member,
    MemberDocument,
    MemberEmergencyContact,
    MemberProfile,
    Membership,
    MembershipFreeze,
    MembershipPlan,
    MembershipTransfer,
)


TENANT_SCOPED_MODELS = (
    pytest.param(LeadSource, id="crm.lead_source"),
    pytest.param(Lead, id="crm.lead"),
    pytest.param(LeadFollowUp, id="crm.lead_follow_up"),
    pytest.param(LeadActivity, id="crm.lead_activity"),
    pytest.param(Note, id="crm.note"),
    pytest.param(Coupon, id="billing.coupon"),
    pytest.param(Invoice, id="billing.invoice"),
    pytest.param(InvoiceItem, id="billing.invoice_item"),
    pytest.param(Discount, id="billing.discount"),
    pytest.param(Payment, id="billing.payment"),
    pytest.param(Refund, id="billing.refund"),
    pytest.param(Member, id="membership.member"),
    pytest.param(MemberProfile, id="membership.member_profile"),
    pytest.param(MemberEmergencyContact, id="membership.emergency_contact"),
    pytest.param(MemberDocument, id="membership.document"),
    pytest.param(MembershipPlan, id="membership.plan"),
    pytest.param(Membership, id="membership.membership"),
    pytest.param(MembershipFreeze, id="membership.freeze"),
    pytest.param(MembershipTransfer, id="membership.transfer"),
    pytest.param(AttendanceDevice, id="attendance.device"),
    pytest.param(AttendanceRecord, id="attendance.record"),
    pytest.param(AttendanceQRToken, id="attendance.qr_token"),
    pytest.param(Supplier, id="inventory.supplier"),
    pytest.param(Product, id="inventory.product"),
    pytest.param(StockLocation, id="inventory.stock_location"),
    pytest.param(Inventory, id="inventory.inventory"),
    pytest.param(PurchaseOrder, id="inventory.purchase_order"),
    pytest.param(PurchaseOrderItem, id="inventory.purchase_order_item"),
    pytest.param(InventoryTransaction, id="inventory.transaction"),
)


@pytest.mark.parametrize("model", TENANT_SCOPED_MODELS)
def test_tenant_scoped_models_require_organization_id(model):
    organization_id = model.__table__.c.get("organization_id")

    assert organization_id is not None
    assert organization_id.nullable is False
    assert any(
        foreign_key.column.table.name == "organizations"
        for foreign_key in organization_id.foreign_keys
    )


@pytest.mark.parametrize("model", TENANT_SCOPED_MODELS)
def test_tenant_scoped_models_have_tenant_lookup_support(model):
    table = model.__table__
    organization_id = table.c.organization_id
    index_columns = {
        column.name
        for index in table.indexes
        for column in index.columns
    }
    constraint_columns = {
        column.name
        for constraint in table.constraints
        if hasattr(constraint, "columns")
        for column in constraint.columns
    }

    assert (
        organization_id.index
        or "organization_id" in index_columns
        or "organization_id" in constraint_columns
    )
