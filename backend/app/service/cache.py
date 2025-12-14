"""Policy cache for Ranger authorization results."""

import hashlib
import json
from typing import Any

from cachetools import TTLCache

from app.core.config import settings

# Cache for policies by service name
# Key: service_name
# Value: list of policy dicts
_policy_cache: dict[str, list[dict[str, Any]]] = {}

_servicedef_cache: dict[str, int] = {}

# TTL cache for authorization results
# Key: (service, user, bucket, object, access_type)
# Value: (is_allowed, is_audited)
_authorization_cache: TTLCache[str, tuple[bool, bool]] = TTLCache(
    maxsize=10000,
    ttl=settings.RANGER_CACHE_TTL,
)


def _make_cache_key(
    service: str,
    user: str,
    bucket: str,
    object_path: str | None,
    access_type: str,
) -> str:
    """Create a cache key from authorization parameters."""
    key_data = {
        "service": service,
        "user": user,
        "bucket": bucket,
        "object": object_path,
        "access_type": access_type,
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()


def get_cached_authorization(
    service: str,
    user: str,
    bucket: str,
    object_path: str | None,
    access_type: str,
) -> tuple[bool, bool] | None:
    """
    Get cached authorization result.

    Returns:
        Tuple of (is_allowed, is_audited) or None if not cached
    """
    cache_key = _make_cache_key(service, user, bucket, object_path, access_type)
    return _authorization_cache.get(cache_key)


def cache_authorization(
    service: str,
    user: str,
    bucket: str,
    object_path: str | None,
    access_type: str,
    is_allowed: bool,
    is_audited: bool,
    policy_id: int,
) -> None:
    """Cache authorization result."""
    cache_key = _make_cache_key(service, user, bucket, object_path, access_type)
    _authorization_cache[cache_key] = (is_allowed, is_audited, policy_id)


def clear_cache() -> None:
    """Clear all cached authorization results."""
    _authorization_cache.clear()


def get_policies(service_name: str) -> list[dict[str, Any]]:
    """Get cached policies for a service."""
    return _policy_cache.get(service_name, [])


def set_policies(service_name: str, policies: list[dict[str, Any]]) -> None:
    """Cache policies for a service."""
    _policy_cache[service_name] = policies


def get_servisedef_id(servicedef_name: str) -> int | None:
    """Get cached servicedef id for a service."""
    return _servicedef_cache.get(servicedef_name)


def set_servisedef_id(servicedef_name: str, servicedef_id: int) -> None:
    """Cache servicedef for a service."""
    _servicedef_cache[servicedef_name] = servicedef_id


def clear_policy_cache() -> None:
    """Clear all cached policies."""
    _policy_cache.clear()


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return {
        "policies_services": len(_policy_cache),
        "authorization_cache_size": len(_authorization_cache),
        "authorization_cache_maxsize": _authorization_cache.maxsize,
        "authorization_cache_ttl": _authorization_cache.ttl,
    }

