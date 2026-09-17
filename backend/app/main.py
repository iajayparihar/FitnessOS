from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_request_id
from app.core.rate_limit import limiter
from app.modules.analytics.router import router as analytics_router
from app.modules.attendance.router import router as attendance_router
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.crm.router import router as crm_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.expenses.router import router as expenses_router
from app.modules.integrations.router import router as integrations_router
from app.modules.inventory.router import router as inventory_router
from app.modules.membership.router import router as membership_router
from app.modules.notifications.router import router as notifications_router
from app.modules.nutrition.router import router as nutrition_router
from app.modules.rbac.router import router as rbac_router
from app.modules.subscriptions.router import router as subscriptions_router
from app.modules.tenants.router import router as tenants_router
from app.modules.trainer.router import router as trainer_router

API_V1_PREFIX = "/api/v1"

MODULE_ROUTERS: tuple[tuple[str, APIRouter, str], ...] = (
    ("analytics", analytics_router, "/analytics"),
    ("attendance", attendance_router, "/attendance"),
    ("auth", auth_router, "/auth"),
    ("billing", billing_router, "/billing"),
    ("crm", crm_router, "/crm"),
    ("dashboard", dashboard_router, "/dashboard"),
    ("expenses", expenses_router, "/expenses"),
    ("integrations", integrations_router, "/integrations"),
    ("inventory", inventory_router, "/inventory"),
    ("membership", membership_router, "/membership"),
    ("notifications", notifications_router, "/notifications"),
    ("nutrition", nutrition_router, "/nutrition"),
    ("rbac", rbac_router, "/rbac"),
    ("subscriptions", subscriptions_router, "/subscriptions"),
    ("tenants", tenants_router, "/tenants"),
    ("trainer", trainer_router, "/trainer"),
)


def health_check() -> dict[str, str]:
    """Return a lightweight process health signal."""
    return {"status": "ok"}


def register_routes(app: FastAPI) -> None:
    """Register public health checks and versioned module routers."""
    app.add_api_route("/health", health_check, methods=["GET"], tags=["health"])
    app.add_api_route(
        f"{API_V1_PREFIX}/health",
        health_check,
        methods=["GET"],
        tags=["health"],
    )

    for tag, router, prefix in MODULE_ROUTERS:
        app.include_router(router, prefix=f"{API_V1_PREFIX}{prefix}", tags=[tag])


def _enable_dev_auth_key() -> None:
    """When dev auth is on and no Clerk key is set, verify dev-issued tokens."""
    if settings.dev_auth_enabled and not (
        settings.clerk_jwt_public_key or settings.clerk_jwks_url
    ):
        from app.core.dev_auth import dev_public_key

        settings.clerk_jwt_public_key = dev_public_key()


def create_app() -> FastAPI:
    configure_logging()
    _enable_dev_auth_key()
    app = FastAPI(title="Fitness Business OS API", version="0.1.0")
    app.state.limiter = limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SlowAPIMiddleware)
    # Registered last so it wraps outermost and request_id is always set.
    register_request_id(app)
    register_error_handlers(app)
    register_routes(app)
    return app


app = create_app()
