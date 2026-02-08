"""MinIO Gateway routes - proxy requests to MinIO with Ranger authorization."""
import logging
import time  # Добавляем импорт time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from starlette.responses import JSONResponse

from app.models.request import RequestBody
from app.service.authorizer import (
    check_authorization,
)
from app.service.constants import (
    S3AccessType,
)
from app.service.ip_whitelist import is_ip_allowed
from app.service.policy_parser import PolicyChecker
from app.service.ranger_client import RangerClient
from app.service.service import (
    extract_request_metadata,
    handle_access_denied,
    handle_access_granted,
)
from app.service.solr_logger import SolrLoggerClient
from app.service.user_groups import get_user_groups_roles_from_ranger

logger = logging.getLogger(__name__)

router = APIRouter()


@router.api_route("/check", methods=["POST"], tags=["check"])
async def check_ranger_access(
    body: RequestBody,
    request: Request
) -> Response:
    """
    Проверка политик в Apache Ranger.

    Flow:
    1. Извлечь и валидировать метаданные запроса
    2. Получить группы пользователя из Ranger
    3. Проверить разрешения через Ranger
    4. Записать результат в аудит
    5. Вернуть ответ

    Args:
        body: Данные запроса
        request: HTTP запрос

    Returns:
        Response: 200 OK если доступ разрешен, 403 Forbidden если запрещен

    Raises:
        HTTPException: 400 если отсутствуют обязательные поля
                     403 если доступ запрещен политикой
    """
    start_time = time.time()
    timings = {}  # Словарь для хранения времени выполнения этапов

    # client_ip = request.client.host
    # if not is_ip_allowed(client_ip):
    #     raise HTTPException(
    #         status_code=403,
    #         detail=f"Access denied from IP {client_ip}. IP is not in whitelist."
    #     )

    try:
        # Этап 1: Извлечение метаданных
        stage_start = time.time()
        username, bucket, object_path, access_type = extract_request_metadata(
            body,
        )
        timings["extract_metadata"] = round((time.time() - stage_start) * 1000, 2)  # мс

        logger.debug(
            f"Processing request: user={username}, bucket={bucket}, "
            f"object={object_path}, access={access_type.value}"
        )

        ranger_client: RangerClient = request.app.state.ranger_client
        solr_logger: SolrLoggerClient = request.app.state.solr_logger

        # Этап 2: Получение групп пользователя из Ranger
        stage_start = time.time()
        user_groups, user_roles = await get_user_groups_roles_from_ranger(ranger_client, username)
        timings["get_user_groups"] = round((time.time() - stage_start) * 1000, 2)  # мс

        logger.debug(f"Groups for {username}: {user_groups}")

        # Проверка на админа
        if access_type == S3AccessType.ADMIN or PolicyChecker.is_admin(user_roles):
            total_time = round((time.time() - start_time) * 1000, 2)
            timings["total"] = total_time
            logger.info(f"Admin access granted in {total_time}ms")
            return JSONResponse(content={"result": True})

        # Этап 3: Проверка авторизации в Ranger
        stage_start = time.time()
        is_allowed, is_audited, policy_id = await check_authorization(
            user=username,
            bucket=bucket,
            object_path=object_path,
            access_type=access_type.value,
            user_groups=user_groups,
            user_roles=user_roles,
        )
        timings["check_authorization"] = round((time.time() - stage_start) * 1000, 2)  # мс

        # Этап 4: Обработка результата и аудит
        stage_start = time.time()
        if not is_allowed:
            await handle_access_denied(
                username=username,
                bucket=bucket,
                object_path=object_path,
                access_type=access_type.value,
                policy_id=policy_id,
                request=request,
                solr_logger=solr_logger
            )
            # Прерываем выполнение если доступ запрещен
            timings["audit_and_response"] = round((time.time() - stage_start) * 1000, 2)
            total_time = round((time.time() - start_time) * 1000, 2)
            timings["total"] = total_time

            # Логируем подробные тайминги для запрещенных запросов
            logger.warning(
                f"Access DENIED for {username}@{bucket}/{object_path} "
                f"in {total_time}ms. Timings: {timings}"
            )

            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Access denied",
                    "user": username,
                    "resource": f"{bucket}/{object_path}" if object_path else bucket,
                    "action": access_type.value,
                    "policy_id": policy_id,
                    "timings_ms": timings  # Добавляем тайминги в ответ
                }
            )

        # Если доступ разрешен - логируем успех
        await handle_access_granted(
            username=username,
            bucket=bucket,
            object_path=object_path,
            access_type=access_type.value,
            policy_id=policy_id,
            request=request,
            solr_logger=solr_logger
        )
        timings["audit_and_response"] = round((time.time() - stage_start) * 1000, 2)

        # Итоговое время
        total_time = round((time.time() - start_time) * 1000, 2)
        timings["total"] = total_time

        # Логируем результат с таймингами
        if total_time > 100:  # Если больше 100ms - логируем как warning
            logger.warning(
                f"SLOW request for {username}@{bucket}/{object_path} "
                f"in {total_time}ms. Timings: {timings}"
            )
        else:
            logger.info(
                f"Access GRANTED for {username}@{bucket}/{object_path} "
                f"in {total_time}ms. Timings: {timings}"
            )

        return JSONResponse(content={
            "result": True,
            "timings_ms": timings  # Возвращаем тайминги в ответ для отладки
        })

    except HTTPException as e:
        # Если это наш HTTPException - добавляем тайминги
        total_time = round((time.time() - start_time) * 1000, 2)
        if e.status_code == 403:
            logger.warning(f"HTTPException 403 after {total_time}ms: {e.detail}")
        raise e
    except ValueError as e:
        total_time = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Validation error after {total_time}ms: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        total_time = round((time.time() - start_time) * 1000, 2)
        logger.exception(f"Unexpected error after {total_time}ms during authorization check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )