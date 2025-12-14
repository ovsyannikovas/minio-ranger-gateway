"""
Главный модуль FastAPI приложения для MinIO-Ranger Gateway.
Организует запуск, подключение внешних клиентов и регистрацию API маршрутов.
"""
import logging
import time
from contextlib import asynccontextmanager

import colorlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.main import api_router
from app.api.routes import check_ranger_access
from app.core.config import settings
from app.service.policy_loader import (
    start_policy_loader,
    stop_policy_loader,
)
from app.service.ranger_client import RangerClient
from app.service.solr_logger import SolrLoggerClient

logger = logging.getLogger(__name__)


def setup_colored_logging():
    """Настройка цветных логов с помощью colorlog."""
    # Создаем цветной форматтер
    formatter = colorlog.ColoredFormatter(
        "%(asctime)s %(log_color)s[%(levelname)s]%(reset)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'bold_red',
        }
    )

    # Настраиваем handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Применяем ко всем логгерам
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler]
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Получаем информацию о запросе
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        url = str(request.url)

        # Логируем начало запроса
        logger.info(f"→ {method} {url} from {client_ip}")

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Логируем успешный ответ
            logger.info(
                f"← {method} {url} {response.status_code} "
                f"({process_time:.3f}s) from {client_ip}"
            )

            # Добавляем заголовок с временем выполнения
            response.headers["X-Process-Time"] = f"{process_time:.3f}s"
            return response

        except Exception as e:
            process_time = time.time() - start_time

            # Логируем ошибку
            logger.error(
                f"✗ {method} {url} ERROR ({process_time:.3f}s) "
                f"from {client_ip}: {str(e)}"
            )
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Лайфспан-контекст для lifecycle-ивентов приложения.
    Включает:
    - Загрузку политик из Ranger
    - Инициализацию клиентов (Ranger, MinIO, Solr, Redis)
    - Освобождение ресурсов на shutdown
    """
    setup_colored_logging()

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

app.add_middleware(LoggingMiddleware)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

app.include_router(check_ranger_access.router, prefix=settings.API_V1_STR, tags=["gateway"])
app.include_router(api_router, prefix=settings.API_V1_STR)
