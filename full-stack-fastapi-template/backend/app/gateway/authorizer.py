"""Authorization logic for MinIO requests."""

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
    Extract bucket and object from S3 path.

    Args:
        path: S3 path like "/bucket/object/key" or "/bucket"

    Returns:
        Tuple of (bucket, object_path or None)
    """
    # Remove leading slash
    path = path.lstrip("/")
    if not path:
        return "", None

    parts = path.split("/", 1)
    bucket = parts[0]
    object_path = parts[1] if len(parts) > 1 else None

    return bucket, object_path


def map_http_method_to_access_type(method: str) -> str:
    """
    Map HTTP method to Ranger access type.

    Args:
        method: HTTP method (GET, PUT, POST, DELETE, etc.)

    Returns:
        Ranger access type (read, write, delete, list)
    """
    method_upper = method.upper()
    if method_upper in ("GET", "HEAD"):
        # Need to distinguish between list and read
        # This will be handled by checking if it's a bucket or object request
        return "read"  # Default, will be adjusted if needed
    elif method_upper in ("PUT", "POST"):
        return "write"
    elif method_upper == "DELETE":
        return "delete"
    else:
        return "read"  # Default


async def check_authorization(
    user: str,
    bucket: str,
    object_path: str | None,
    access_type: str,
    user_groups: list[str] | None = None,
    service_name: str | None = None,
) -> tuple[bool, bool]:
    """
    Check authorization for MinIO operation using locally cached policies.

    Args:
        user: Username
        bucket: Bucket name
        object_path: Object path (optional)
        access_type: Access type (read, write, delete, list)
        user_groups: Optional list of user groups
        service_name: Ranger service name (defaults to config)

    Returns:
        Tuple of (is_allowed, is_audited)
    """
    service = service_name or settings.RANGER_SERVICE_NAME
    user_groups = user_groups or []

    # Check authorization result cache first
    cached_result = get_cached_authorization(service, user, bucket, object_path, access_type)
    if cached_result is not None:
        logger.debug(f"Cache hit for {user} {bucket}/{object_path} {access_type}")
        return cached_result

    # Get policies from cache
    policies = get_policies(service)
    if not policies:
        logger.warning(f"No policies found for service {service}, denying access")
        # Deny by default if no policies
        return False, False

    # Check access using policy parser
    is_allowed, is_audited = PolicyChecker.check_access(
        policies=policies,
        user=user,
        user_groups=user_groups,
        bucket=bucket,
        object_path=object_path,
        access_type=access_type,
    )

    # Cache the result
    cache_authorization(
        service,
        user,
        bucket,
        object_path,
        access_type,
        is_allowed,
        is_audited,
    )

    return is_allowed, is_audited

