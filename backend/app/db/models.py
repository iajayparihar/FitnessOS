# Import every module so SQLAlchemy registers them
from app.db.base import Base
from app.modules.tenants.models import *
from app.modules.auth.models import *
from app.modules.rbac.models import *
from app.modules.subscriptions.models import *
from app.modules.crm.models import *
from app.modules.membership.models import *
from app.modules.attendance.models import *
from app.modules.billing.models import *
from app.modules.trainer.models import *
from app.modules.nutrition.models import *
from app.modules.inventory.models import *
from app.modules.expenses.models import *
from app.modules.notifications.models import *
from app.modules.analytics.models import *
from app.modules.integrations.models import *
from app.modules.ai.models import *
__all__ = [
    "Base",
    "tenants",
    "auth",
    "rbac",
    "subscriptions",
    "crm",
    "membership",
    "attendance",
    "billing",
    "trainer",
    "nutrition",
    "inventory",
    "expenses",
    "notifications",
    "analytics",
    "integrations",
    "ai",
]
