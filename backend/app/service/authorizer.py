"""
Authorization logic for MinIO requests.

- Декодирует ресурсы и HTTP-методы
- Проверяет права по локально-кэшированным политикам Ranger
- Кэширует результат авторизации
"""

import logging

from app.core.config import settings
from app.service.cache import (
    cache_authorization,
    get_cached_authorization,
    get_policies,
)
from app.service.constants import S3AccessType
from app.service.policy_parser import PolicyChecker

logger = logging.getLogger(__name__)


def extract_resource_from_path(path: str) -> tuple[str, str | None]:
    """
    Достает имя bucket и object-ключ из входного пути.
    Args:
        path: str - Пример '/bucket/object/key'
    Returns:
        (bucket, object_key or None)
    """
    path = path.lstrip("/")
    if not path:
        return "", None
    parts = path.split("/", 1)
    bucket = parts[0]
    object_path = parts[1] if len(parts) > 1 else None
    return bucket, object_path


S3_READ_ACTIONS = [
    's3:GetObject',
    's3:GetObjectAcl',
    's3:GetObjectTagging',
    's3:GetObjectVersion',
    's3:GetObjectVersionAcl',
    's3:GetObjectVersionTagging',
    's3:GetBucketAcl',
    's3:GetBucketCORS',
    's3:GetBucketLocation',
    's3:GetBucketLogging',
    's3:GetBucketNotification',
    's3:GetBucketPolicy',
    's3:GetBucketRequestPayment',
    's3:GetBucketTagging',
    's3:GetBucketVersioning',
    's3:GetBucketWebsite',
    's3:GetLifecycleConfiguration',
    's3:GetReplicationConfiguration',
]

S3_LIST_ACTIONS = [
    's3:ListBucket',
    's3:ListBucketVersions',
    's3:ListAllMyBuckets',
    's3:ListMultipartUploadParts',
    's3:ListBucketMultipartUploads',
    's3:ListObjectsV2',
    's3:ListBucket',
    's3:ListBucketVersions',
    's3:ListAllMyBuckets',
    's3:ListMultipartUploadParts',
]

S3_WRITE_ACTIONS = [
    's3:PutObject',
    's3:PutObjectAcl',
    's3:PutObjectTagging',
    's3:PutObjectVersionAcl',
    's3:PutObjectVersionTagging',
    's3:PutBucketAcl',
    's3:PutBucketCORS',
    's3:PutBucketLogging',
    's3:PutBucketNotification',
    's3:PutBucketPolicy',
    's3:PutBucketRequestPayment',
    's3:PutBucketTagging',
    's3:PutBucketVersioning',
    's3:PutBucketWebsite',
    's3:PutLifecycleConfiguration',
    's3:PutReplicationConfiguration',
    's3:RestoreObject',
    's3:CreateBucket',
]

S3_DELETE_ACTIONS = [
    's3:DeleteObject',
    's3:DeleteObjectVersion',
    's3:DeleteBucket',
    's3:DeleteObjectTagging',
    's3:DeleteObjectVersionTagging',
    's3:AbortMultipartUpload',
]


def map_action_to_access_type(action: str) -> S3AccessType:
    """
    Маппинг HTTP-метода в Ranger access type.
    GET/HEAD = read, PUT/POST = write, DELETE = delete, иначе read.
    Может быть скорректировано выше (например, GET bucket → list).
    """
    if action in S3_READ_ACTIONS:
        return S3AccessType.READ
    elif action in S3_WRITE_ACTIONS:
        return S3AccessType.WRITE
    elif action in S3_DELETE_ACTIONS:
        return S3AccessType.DELETE
    elif action in S3_LIST_ACTIONS:
        return S3AccessType.LIST
    else:
        return S3AccessType.ADMIN


async def check_authorization(
    user: str,
    bucket: str,
    object_path: str | None,
    access_type: str,
    user_groups: list[str] | None = None,
    user_roles: list[str] | None = None,
    service_name: str | None = None,
) -> tuple[bool, bool, int]:
    """
    Проверяет авторизацию MinIO-запроса по загруженным политикам.
    Args:
        user (str): логин
        bucket (str): имя бакета
        object_path (str|None): путь (если объект)
        access_type (str): тип (read/write/delete/list)
        user_groups (list[str]|None): группы
        user_roles (list[str]|None): роли
        service_name (str): Сервис в Ranger (по-умолчанию — config)
    Return:
        (is_allowed: bool, is_audited: bool, policy_id: int)
    """
    service = service_name or settings.RANGER_SERVICE_NAME
    user_groups = user_groups or []

    # 1. Быстрый путь: берем кэш-результат
    cached_result = get_cached_authorization(service, user, bucket, object_path, access_type)
    if cached_result is not None:
        logger.debug(f"Cache hit for {user} {bucket}/{object_path} {access_type}")
        return cached_result

    # 2. Политики из кэша политик
    policies = get_policies(service)
    if not policies:
        logger.warning(f"No policies found for service {service}, denying access")
        return False, False, 0

    # 3. Проверяем через PolicyChecker
    is_allowed, is_audited, policy_id = PolicyChecker.check_access(
        policies=policies,
        user=user,
        user_groups=user_groups,
        user_roles=user_roles,
        bucket=bucket,
        object_path=object_path,
        access_type=access_type,
    )
    # 4. Кэшируем результат
    cache_authorization(
        service,
        user,
        bucket,
        object_path,
        access_type,
        is_allowed,
        is_audited,
        policy_id,
    )
    if is_allowed:
        logger.info(f"✔️ Access granted: user={user} bucket={bucket} object={object_path} type={access_type} via policy={policy_id}")
    else:
        logger.info(f"⛔ Access denied: user={user} bucket={bucket} object={object_path} type={access_type}")
    return is_allowed, is_audited, policy_id

