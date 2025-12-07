"""
Главный модуль FastAPI приложения для MinIO-Ranger Gateway.
Организует запуск, подключение внешних клиентов и регистрацию API маршрутов.
"""
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from app.api.main import api_router
from app.api.routes import check_ranger_access
from app.core.config import settings
from app.service.policy_loader import load_policies, start_policy_loader, stop_policy_loader
from app.service.ranger_client import RangerClient
from app.service.solr_logger import SolrLoggerClient
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


# if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
#     sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


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

    app.state.solr_logger = SolrLoggerClient(settings.SOLR_AUDIT_URL)

    yield
    stop_policy_loader()
    await app.state.solr_logger.aclose()
    await app.state.ranger_client.aclose()

app = FastAPI(
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

app.include_router(check_ranger_access.router, prefix=settings.API_V1_STR, tags=["gateway"])
app.include_router(api_router, prefix=settings.API_V1_STR)
