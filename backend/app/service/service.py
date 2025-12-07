"""MinIO Gateway routes - proxy requests to MinIO with Ranger authorization."""
import logging
from typing import Optional, Tuple, Dict, Any
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException, Request, status

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

logger = logging.getLogger(__name__)

router = APIRouter()


def get_first_or_none(items: list, default: Any = None) -> Optional[Any]:
    """Безопасное получение первого элемента списка."""
    return items[0] if items else default


def extract_request_metadata(
        body: RequestBody,
        request: Request
) -> Tuple[str, str, str, Optional[str]]:
    """Извлечение и валидация метаданных запроса."""
    username = get_first_or_none(body.input.conditions.username)
    if not username:
        logger.error("Username not provided in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is required"
        )

    bucket = body.input.bucket or ""
    object_path = body.input.object or ""
    access_type = map_action_to_access_type(body.input.action)

    return username, bucket, object_path, access_type


def get_client_ip(request: Request) -> str:
    """Получение IP клиента с учетом прокси."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Берем первый IP из цепочки прокси
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


@asynccontextmanager
async def log_audit_context(
        solr_logger: SolrLoggerClient,
        username: str,
        bucket: str,
        object_path: str,
        access_type: str,
        request: Request,
        result: AuditResult,
        policy_id: Optional[str] = None,
        **extra_fields: Dict[str, Any]
):
    """Контекстный менеджер для логгирования аудита."""
    try:
        resource_path = f"/{bucket}/{object_path}" if object_path else f"/{bucket}"

        audit_record = solr_logger.build_audit_record(
            policy=policy_id or "no-policy",
            policyVersion=DEFAULT_POLICY_VERSION,
            access=access_type,
            repo=bucket,
            repoType=S3ResourceType.BUCKET.value,
            sess=request.headers.get("X-Session-Id", ""),
            reqUser=username,
            resource=resource_path,
            cliIP=get_client_ip(request),
            result=result.value,
            agentHost=getattr(settings, 'API_HOST', 'localhost'),
            action=access_type,
            **extra_fields
        )

        yield audit_record

    except Exception as e:
        logger.error(f"Failed to prepare audit record: {e}")
        raise
    finally:
        try:
            await solr_logger.log_event(audit_record)
            logger.debug(
                f"Audit event logged: user={username}, "
                f"policy={policy_id}, result={result.name}"
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")


async def handle_access_denied(
        username: str,
        bucket: str,
        object_path: str,
        access_type: str,
        policy_id: Optional[str],
        request: Request,
        solr_logger: SolrLoggerClient
) -> None:
    """Обработка отказа в доступе."""
    logger.warning(
        f"Access DENIED: user={username}, bucket={bucket}, "
        f"object={object_path}, access={access_type}, policy={policy_id}"
    )

    async with log_audit_context(
            solr_logger=solr_logger,
            username=username,
            bucket=bucket,
            object_path=object_path,
            access_type=access_type,
            request=request,
            result=AuditResult.DENIED,
            policy_id=policy_id,
    ):
        pass

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "Access denied",
            "user": username,
            "resource": f"{bucket}/{object_path}" if object_path else bucket,
            "action": access_type,
            "policy_id": policy_id
        }
    )


async def handle_access_granted(
        username: str,
        bucket: str,
        object_path: str,
        access_type: str,
        policy_id: Optional[str],
        request: Request,
        solr_logger: SolrLoggerClient
) -> None:
    """Обработка разрешенного доступа."""
    logger.info(
        f"Access GRANTED: user={username}, bucket={bucket}, "
        f"object={object_path}, access={access_type}, policy={policy_id}"
    )

    async with log_audit_context(
            solr_logger=solr_logger,
            username=username,
            bucket=bucket,
            object_path=object_path,
            access_type=access_type,
            request=request,
            result=AuditResult.ALLOWED,
            policy_id=policy_id
    ):
        pass
