"""MinIO Gateway routes - proxy requests to MinIO with Ranger authorization."""

import logging
from typing import Any
import redis.asyncio as redis
import re

from fastapi import APIRouter, HTTPException, Request, Response, status, Depends
from fastapi.responses import StreamingResponse
import httpx

from app.core.config import settings
from app.gateway.authorizer import (
    check_authorization,
    extract_resource_from_path,
    map_http_method_to_access_type,
)
from app.gateway.user_groups import get_user_groups_from_ranger
from app.gateway.solr_logger import SolrLoggerClient
from app.gateway.ranger_client import RangerClient
from app.utils import get_user_from_access_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.api_route("/{path:path}", methods=["GET", "PUT", "POST", "DELETE", "HEAD"])
async def proxy_to_minio(
    request: Request,
    path: str,
):
    """
    Прокси S3-запросы к MinIO через авторизацию Apache Ranger.

    1. Извлечь пользователя и группы
    2. Проверить разрешения через Ranger
    3. Если разрешено — проксировать запрос к MinIO
    4. Вернуть ответ клиента
    Логгировать действия (аудит) через Solr, если требуется политикой
    """
    try:
        user = await get_user_from_access_key(request, request.app.state.redis_client)
        logger.debug(f"Extracted user from access_key: {user}")
    except HTTPException as e:
        logger.warning(f"Auth failed: {e.detail}")
        return Response(content=e.detail, status_code=e.status_code)

    ranger_client: RangerClient = request.app.state.ranger_client
    # Get user groups from Ranger UserSync
    user_groups = await get_user_groups_from_ranger(ranger_client, user)
    logger.debug(f"Groups for {user}: {user_groups}")

    # Extract bucket and object from path
    bucket, object_path = extract_resource_from_path(path)
    logger.debug(f"Parsed path: bucket={bucket}, object_path={object_path}")

    # if not bucket:
    #     logger.error("Bucket name is required")
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Bucket name is required",
    #     )

    # Map HTTP method to access type
    access_type = map_http_method_to_access_type(request.method)

    # For bucket-only requests (list), adjust access type
    if object_path is None and request.method.upper() == "GET":
        access_type = "list"

    # Check authorization
    is_allowed, is_audited, policy_id = await check_authorization(
        user=user,
        bucket=bucket,
        object_path=object_path,
        access_type=access_type,
        user_groups=user_groups,
    )

    if not is_allowed:
        logger.warning(
            f"Access denied: user={user}, bucket={bucket}, "
            f"object={object_path}, access={access_type}"
        )
        # TODO тут тоже лог в solr
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied by policy",
        )
    logger.info(f"Access GRANTED: user={user}, bucket={bucket}, object={object_path}, access={access_type}")

    # Log audit to Solr if needed
    if is_audited:
        solr_logger: SolrLoggerClient = request.app.state.solr_logger
        audit_record = solr_logger.build_audit_record(
            policy=policy_id,
            policyVersion=1,
            access=access_type,
            repo=bucket,
            repoType=1,
            sess=request.headers.get("X-Session-Id", ""),
            reqUser=user,
            resource=f"/{bucket}/{object_path}" if object_path else f"/{bucket}",
            cliIP=request.client.host if request.client else "",
            result=1,
            agentHost=settings.API_HOST if hasattr(settings, 'API_HOST') else "localhost",
            action=access_type
        )
        await solr_logger.log_event(audit_record)
        logger.debug(f"Audit event logged for user={user}, policy={policy_id}")

    # Proxy request to MinIO
    try:
        minio_client: httpx.AsyncClient = request.app.state.minio_client
        url = f"/{path}"
        headers = dict(request.headers)
        # Get request body if present
        body = await request.body()

        response = await minio_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )

        logger.debug(f"Proxied to MinIO: url={url}, status={response.status_code}")
        # Return response from MinIO
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )
    except httpx.HTTPError as e:
        logger.error(f"Error proxying to MinIO: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error connecting to MinIO",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

