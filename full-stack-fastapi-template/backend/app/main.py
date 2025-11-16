import logging

import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.api.routes import gateway
from app.core.config import settings
from app.gateway.policy_loader import load_policies, start_policy_loader, stop_policy_loader

logger = logging.getLogger(__name__)


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown tasks."""
    # Startup: Load policies and start background loader
    logger.info("Loading policies on startup...")
    start_policy_loader()
    yield
    # Shutdown: Stop policy loader
    stop_policy_loader()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
# Gateway router on root path for S3 API compatibility
app.include_router(gateway.router, prefix="", tags=["gateway"])
