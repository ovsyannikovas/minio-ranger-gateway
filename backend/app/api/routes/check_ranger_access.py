"""MinIO Gateway routes - proxy requests to MinIO with Ranger authorization."""
import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import settings
from app.service.authorizer import (
    check_authorization,
    extract_resource_from_path,
    map_action_to_access_type,
)
from app.service.user_groups import get_user_groups_from_ranger
from app.service.solr_logger import SolrLoggerClient
from app.service.ranger_client import RangerClient
from app.models.request import RequestBody
from app.service.constants import (
    S3AccessType,
    S3ResourceType,
    AuditResult,
    DEFAULT_POLICY_VERSION
)

from app.service.service import handle_access_denied, handle_access_granted, extract_request_metadata


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
    try:
        username, bucket, object_path, access_type = extract_request_metadata(
            body, request
        )

        logger.debug(
            f"Processing request: user={username}, bucket={bucket}, "
            f"object={object_path}, access={str(access_type)}"
        )

        ranger_client: RangerClient = request.app.state.ranger_client
        solr_logger: SolrLoggerClient = request.app.state.solr_logger

        user_groups = await get_user_groups_from_ranger(ranger_client, username)
        logger.debug(f"Groups for {username}: {user_groups}")

        is_allowed, is_audited, policy_id = await check_authorization(
            user=username,
            bucket=bucket,
            object_path=object_path,
            access_type=str(access_type),
            user_groups=user_groups
        )

        if not is_allowed:
            await handle_access_denied(
                username=username,
                bucket=bucket,
                object_path=object_path,
                access_type=str(access_type),
                policy_id=policy_id,
                request=request,
                solr_logger=solr_logger
            )

        await handle_access_granted(
            username=username,
            bucket=bucket,
            object_path=object_path,
            access_type=str(access_type),
            policy_id=policy_id,
            request=request,
            solr_logger=solr_logger
        )

        return Response(status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Unexpected error during authorization check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
