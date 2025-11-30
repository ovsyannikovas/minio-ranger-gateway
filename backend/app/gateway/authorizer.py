"""
Authorization logic for MinIO requests.

- Декодирует ресурсы и HTTP-методы
- Проверяет права по локально-кэшированным политикам Ranger
- Кэширует результат авторизации
"""

import logging
from typing import Any

from app.core.config import settings
from app.gateway.cache import (
    cache_authorization,
    get_cached_authorization,
    get_policies,
)
from app.gateway.policy_parser import PolicyChecker

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


def map_http_method_to_access_type(method: str) -> str:
    """
    Маппинг HTTP-метода в Ranger access type.
    GET/HEAD = read, PUT/POST = write, DELETE = delete, иначе read.
    Может быть скорректировано выше (например, GET bucket → list).
    """
    method_upper = method.upper()
    if method_upper in ("GET", "HEAD"):
        return "read"
    elif method_upper in ("PUT", "POST"):
        return "write"
    elif method_upper == "DELETE":
        return "delete"
    else:
        return "read"


async def check_authorization(
    user: str,
    bucket: str,
    object_path: str | None,
    access_type: str,
    user_groups: list[str] | None = None,
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

    # 2. Париc из кэша политик
    policies = get_policies(service)
    if not policies:
        logger.warning(f"No policies found for service {service}, denying access")
        return False, False, 0

    # 3. Проверяем через PolicyChecker
    is_allowed, is_audited, policy_id = PolicyChecker.check_access(
        policies=policies,
        user=user,
        user_groups=user_groups,
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
    )
    if is_allowed:
        logger.info(f"✔️ Access granted: user={user} bucket={bucket} object={object_path} type={access_type} via policy={policy_id}")
    else:
        logger.info(f"⛔ Access denied: user={user} bucket={bucket} object={object_path} type={access_type}")
    return is_allowed, is_audited, policy_id

