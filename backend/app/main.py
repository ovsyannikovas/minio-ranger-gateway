"""
Главный модуль FastAPI приложения для MinIO-Ranger Gateway.
Организует запуск, подключение внешних клиентов и регистрацию API маршрутов.
"""
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
from app.gateway.ranger_client import RangerClient
from app.gateway.solr_logger import SolrLoggerClient
import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Лайфспан-контекст для lifecycle-ивентов приложения.
    Включает:
    - Загрузку политик из Ranger
    - Инициализацию клиентов (Ranger, MinIO, Solr, Redis)
    - Освобождение ресурсов на shutdown
    """
    logger.info("Loading policies on startup...")

    app.state.ranger_client = RangerClient()

    start_policy_loader(app.state.ranger_client)

    app.state.minio_client = httpx.AsyncClient(base_url=settings.MINIO_ENDPOINT, timeout=60)
    app.state.solr_logger = SolrLoggerClient(settings.SOLR_AUDIT_URL)
    app.state.redis_client = redis.Redis(host="redis", port=6379, db=0, password="redispass123")

    yield
    stop_policy_loader()
    await app.state.minio_client.aclose()
    await app.state.solr_logger.aclose()
    await app.state.redis_client.aclose()
    await app.state.ranger_client.aclose()


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

# В первую очередь маршрутизатор gateway, затем API v1
app.include_router(gateway.router, prefix="", tags=["gateway"])
app.include_router(api_router, prefix=settings.API_V1_STR)
