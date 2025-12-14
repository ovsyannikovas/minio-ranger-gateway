"""Get user groups from Ranger UserSync."""

import logging
from typing import Any

from cachetools import TTLCache

from app.service.ranger_client import RangerClient

logger = logging.getLogger(__name__)

# Cache for user groups
# Key: username
# Value: list of group names
_user_groups_cache: TTLCache[str, list[str]] = TTLCache(
    maxsize=10000,
    ttl=300,  # 5 minutes
)


async def get_user_groups_roles_from_ranger(
    ranger_client: RangerClient, username: str
) -> tuple[list[str], list[str]]:
    """
    Get user groups and roles from Ranger UserSync.

    Args:
        ranger_client: RangerClient
        username: Username

    Returns:
        Tuple of (groups, roles)
    """
    # Check cache first
    cached = _user_groups_cache.get(username)
    if cached is not None:
        logger.debug(f"Cache hit for user groups/roles: {username}")
        return cached

    # Get user info from Ranger
    result = await ranger_client.get_user(username)
    if result is None:
        # User not found, cache empty lists
        logger.warning(f"User {username} not found in Ranger")
        _user_groups_cache[username] = ([], [])
        return [], []

    groups = []
    roles = []

    if isinstance(result, dict):
        # Извлекаем группы
        group_names = result.get("groupNameList")
        if isinstance(group_names, list):
            groups = [g for g in group_names if isinstance(g, str)]

        # Извлекаем роли
        user_roles = result.get("userRoleList")
        if isinstance(user_roles, list):
            roles = [r for r in user_roles if isinstance(r, str)]

    # Кэшируем
    _user_groups_cache[username] = (groups, roles)

    logger.info(
        f"Loaded {len(groups)} groups and {len(roles)} roles for user {username}"
    )
    return groups, roles


def clear_user_groups_cache() -> None:
    """Clear user groups cache."""
    _user_groups_cache.clear()


def get_user_groups_cache_stats() -> dict[str, Any]:
    """Get user groups cache statistics."""
    return {
        "size": len(_user_groups_cache),
        "maxsize": _user_groups_cache.maxsize,
        "ttl": _user_groups_cache.ttl,
    }

