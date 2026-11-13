"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import Clock, default_clock
from app.api.errors import install_error_handlers
from app.api.v1.router import api_router
from app.core import security
from app.core.config import Settings, get_settings
from app.database.migrate import apply_migrations
from app.database.seed import seed_system_accounts
from app.database.session import connect

_CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
_CORS_HEADERS = ["Authorization", "Content-Type", "Idempotency-Key", "If-Match", "X-Requested-With"]


def _prepare_database(settings: Settings) -> None:
    key = settings.db_key.get_secret_value() if settings.db_key else None
    conn = connect(settings.db_path, key)
    try:
        apply_migrations(conn)
        seed_system_accounts(conn)
    finally:
        conn.close()


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    """Build the app; fails fast on a missing/short JWT secret, then migrates and seeds the DB."""
    settings = settings or get_settings()
    security.validate_jwt_secret(settings.jwt_secret.get_secret_value() if settings.jwt_secret else None)
    if "*" in settings.allowed_origins:
        raise RuntimeError("FINSIGHT_ALLOWED_ORIGINS must list explicit origins; '*' is not allowed.")
    _prepare_database(settings)

    app = FastAPI(title="FinSight API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.clock = clock or default_clock
    app.state.login_throttle = security.LoginThrottle(clock=lambda: app.state.clock().timestamp())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=_CORS_METHODS,
        allow_headers=_CORS_HEADERS,
    )
    install_error_handlers(app)
    app.include_router(api_router)
    return app
