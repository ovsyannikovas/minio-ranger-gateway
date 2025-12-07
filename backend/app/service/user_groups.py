"""Get user groups from Ranger UserSync."""

import logging
from typing import Any

from cachetools import TTLCache

from app.core.config import settings

from app.service.ranger_client import RangerClient

logger = logging.getLogger(__name__)

# Cache for user groups
# Key: username
# Value: list of group names
_user_groups_cache: TTLCache[str, list[str]] = TTLCache(
    maxsize=10000,
    ttl=300,  # 5 minutes
)


async def get_user_groups_from_ranger(ranger_client: RangerClient, username: str) -> list[str]:
    """
    Get user groups from Ranger UserSync.

    Args:
        ranger_client: RangerClient
        username: Username

    Returns:
        List of group names
    """
    # Check cache first
    cached_groups = _user_groups_cache.get(username)
    if cached_groups is not None:
        logger.debug(f"Cache hit for user groups: {username}")
        return cached_groups

    # Get user info from Ranger
    result = await ranger_client.get_user(username)
    if result is None:
        # User not found, cache empty list
        logger.warning(f"User {username} not found in Ranger")
        _user_groups_cache[username] = []
        return []

    # Extract groups from user info
    groups = []

    # Handle different response formats
    if isinstance(result, dict):
        # Try to extract groups from various possible fields
        if "groups" in result:
            groups_data = result["groups"]
            if isinstance(groups_data, list):
                # List of group objects or group names
                for group in groups_data:
                    if isinstance(group, dict):
                        # Group object with name field
                        group_name = group.get("name") or group.get("groupName")
                        if group_name:
                            groups.append(group_name)
                    elif isinstance(group, str):
                        # Direct group name
                        groups.append(group)
            elif isinstance(groups_data, str):
                # Comma-separated string
                groups = [g.strip() for g in groups_data.split(",") if g.strip()]

        elif "groupList" in result:
            # Alternative field name
            groups_data = result["groupList"]
            if isinstance(groups_data, list):
                for group in groups_data:
                    if isinstance(group, dict):
                        group_name = group.get("name") or group.get("groupName")
                        if group_name:
                            groups.append(group_name)
                    elif isinstance(group, str):
                        groups.append(group)

        elif "userGroups" in result:
            # Another alternative
            groups_data = result["userGroups"]
            if isinstance(groups_data, list):
                for group in groups_data:
                    if isinstance(group, dict):
                        group_name = group.get("name") or group.get("groupName")
                        if group_name:
                            groups.append(group_name)
                    elif isinstance(group, str):
                        groups.append(group)

    # Cache the result (even if empty)
    _user_groups_cache[username] = groups
    if groups:
        logger.info(f"Loaded {len(groups)} groups for user {username}: {groups}")
    else:
        logger.debug(f"No groups found for user {username}")
    return groups


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

