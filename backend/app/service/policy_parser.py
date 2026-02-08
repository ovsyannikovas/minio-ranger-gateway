"""Parser for Ranger policies - local authorization check."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PolicyMatcher:
    """Matches resources against policy resource definitions."""

    @staticmethod
    def match_resource(
            resource_value: str,
            policy_values: list[str],
            is_excludes: bool,
            is_recursive: bool,
            bucket_name: str | None = None,  # Добавим bucket для нормализации object paths
    ) -> bool:
        """
        Check if resource matches policy resource values.

        Args:
            resource_value: The resource value to check (e.g., bucket name or object path)
            policy_values: List of policy resource values
            is_excludes: If True, this is an exclude rule (invert match)
            is_recursive: If True, match recursively (for paths)
            bucket_name: Bucket name for normalizing object paths (optional)

        Returns:
            True if resource matches policy
        """
        if not policy_values:
            return False

        # Check each policy value
        for policy_value in policy_values:
            # Normalize object paths
            current_resource = resource_value
            current_policy_value = policy_value

            # Если указан bucket_name и policy_value содержит bucket/
            if bucket_name and '/' in policy_value:
                # Извлекаем bucket часть из policy_value
                parts = policy_value.split('/', 1)
                if len(parts) == 2:
                    policy_bucket, policy_object = parts
                    # Проверяем совпадает ли bucket
                    if policy_bucket == bucket_name:
                        # Используем только object часть для сравнения
                        current_policy_value = policy_object
                    else:
                        # Bucket не совпадает, пропускаем этот pattern
                        continue

            if is_recursive:
                # For recursive matching (e.g., object paths)
                # Check if resource starts with policy value
                if current_resource.startswith(current_policy_value):
                    match = True
                else:
                    # Also check exact match
                    match = current_resource == current_policy_value
            else:
                # Exact match for non-recursive (e.g., bucket names)
                match = current_resource == current_policy_value

            # Wildcard support
            if not match and '*' in current_policy_value:
                import re
                # Convert wildcard pattern to regex
                regex_pattern = re.escape(current_policy_value).replace('\\*', '.*')
                if re.match(f'^{regex_pattern}$', current_resource):
                    match = True

            if match:
                # If this is an exclude rule, return False (deny)
                # Otherwise return True (allow)
                return not is_excludes

        # No match found
        # If this is an exclude rule, return True (not excluded, so allow)
        # Otherwise return False (not in allowed list, so deny)
        return is_excludes

    @staticmethod
    def match_bucket(bucket: str, policy_bucket: dict[str, Any]) -> bool:
        """Match bucket against policy bucket definition."""
        values = policy_bucket.get("values", [])
        is_excludes = policy_bucket.get("isExcludes", False)
        is_recursive = policy_bucket.get("isRecursive", False)

        return PolicyMatcher.match_resource(bucket, values, is_excludes, is_recursive)

    @staticmethod
    def match_object(
            object_path: str | None,
            policy_object: dict[str, Any] | None,
            bucket_name: str | None = None  # Добавляем bucket для нормализации
    ) -> bool:
        """Match object path against policy object definition."""
        if policy_object is None:
            # No object restriction means match any object
            return True

        if object_path is None:
            # Request is for bucket, not object
            # Check if policy allows bucket-level access
            # For object-specific policies without bucket-level access
            return False  # Изменил на False - если политика object-specific, а запрос bucket-level

        values = policy_object.get("values", [])
        is_excludes = policy_object.get("isExcludes", False)
        is_recursive = policy_object.get("isRecursive", True)  # Default True for objects

        return PolicyMatcher.match_resource(
            object_path,
            values,
            is_excludes,
            is_recursive,
            bucket_name  # Передаем bucket для нормализации
        )


class PolicyChecker:
    """Checks authorization against loaded policies."""
    ADMIN_ROLE = "ROLE_SYS_ADMIN"

    @classmethod
    def is_admin(cls, user_roles: list[str]):
        return cls.ADMIN_ROLE in user_roles

    @classmethod
    def check_access(
        cls,
        policies: list[dict[str, Any]],
        user: str,
        user_groups: list[str],
        user_roles: list[str],
        bucket: str,
        object_path: str | None,
        access_type: str,
    ) -> tuple[bool, bool, int]:
        print("HERE", bucket, object_path, access_type, user, user_groups)
        """
        Check if user has access based on policies.

        Args:
            policies: List of policy dictionaries from Ranger
            user: Username
            user_groups: List of user groups
            user_roles: List of user roles
            bucket: Bucket name
            object_path: Object path (optional)
            access_type: Access type (read, write, delete, list)

        Returns:
            Tuple of (is_allowed, is_audited)
        """
        logger.debug(
            f"Starting policy check: user={user}, groups={user_groups}, bucket={bucket}, object={object_path}, access={access_type}")

        policy_id = None
        # Check each policy
        for i, policy in enumerate(policies):
            policy_name = policy.get("name", f"UnnamedPolicy-{i}")
            policy_id = policy.get("id", 0)
            logger.debug(f"Checking policy [{i}]: {policy_name}")

            if not policy.get("isEnabled", True):
                logger.debug(f"Policy {policy_name} is disabled, skipping.")
                continue

            # Check if policy resources match
            policy_resources = policy.get("resources", {})
            policy_bucket = policy_resources.get("bucket")
            policy_object = policy_resources.get("object")

            # Check bucket match FIRST (always required)
            if policy_bucket is not None:
                if not PolicyMatcher.match_bucket(bucket, policy_bucket):
                    logger.debug(f"Bucket '{bucket}' does not match policy {policy_name}.")
                    continue
                logger.debug(f"Bucket '{bucket}' matches policy {policy_name}.")
            else:
                # If policy has no bucket, check if object path contains bucket
                if policy_object is not None:
                    # Extract bucket from object path in policy
                    # Assuming object path format: "bucket/object" or just "object"
                    logger.debug(f"Policy {policy_name} has no bucket resource, checking object path...")
                else:
                    logger.debug(f"Policy {policy_name} has no bucket or object resource, skipping.")
                    continue

            # If object_path is provided, check object match for object-specific policies
            if object_path is not None:
                if policy_object is not None:
                    # Policy has object resource, check if it matches
                    if not PolicyMatcher.match_object(object_path, policy_object, bucket):
                        logger.debug(f"Object '{object_path}' does not match policy {policy_name}.")
                        continue
                    logger.debug(f"Object '{object_path}' matches policy {policy_name}.")
                else:
                    # Policy is bucket-only, allow all objects in bucket
                    logger.debug(f"Policy {policy_name} is bucket-level, allowing access to all objects in bucket.")
            else:
                # Object path not provided (bucket-level operation like list)
                if policy_object is not None:
                    # Policy is object-specific but operation is bucket-level
                    logger.debug(f"Policy {policy_name} is object-specific but operation is bucket-level, skipping.")
                    continue

            # Check if user or group matches
            policy_items = policy.get("policyItems", [])
            logger.debug(f"Policy {policy_name} has {len(policy_items)} policy items.")

            matched = False
            for j, policy_item in enumerate(policy_items):
                policy_users = policy_item.get("users", [])
                policy_groups = policy_item.get("groups", [])

                user_match = user in policy_users if policy_users else False
                group_match = (
                    any(group in policy_groups for group in user_groups)
                    if policy_groups and user_groups
                    else False
                )

                logger.debug(
                    f"Policy item [{j}]: users={policy_users}, groups={policy_groups}, "
                    f"user_match={user_match}, group_match={group_match}"
                )

                if not (user_match or group_match):
                    continue

                is_audited = policy.get("isAuditEnabled", True)

                is_admin = (
                    policy_item.get("delegateAdmin", False)
                    or cls.is_admin(user_roles)
                )
                if is_admin:
                    return True, is_audited, policy_id

                # Check access type
                accesses = policy_item.get("accesses", [])
                logger.debug(f"Checking accesses: {accesses}")

                for k, access in enumerate(accesses):
                    access_type_match = access.get("type") == access_type
                    is_allowed = access.get("isAllowed", False)
                    logger.debug(
                        f"Access [{k}]: type={access.get('type')}, allowed={is_allowed}, "
                        f"type_match={access_type_match}"
                    )

                    if access_type_match and is_allowed:
                        logger.info(
                            f"✅ ACCESS GRANTED by policy '{policy_name}': "
                            f"user={user}, bucket={bucket}, object={object_path}, access={access_type}, audited={is_audited}"
                        )
                        return True, is_audited, policy_id

            if not matched:
                logger.debug(f"No matching access found in policy {policy_name}.")

        logger.warning(
            f"❌ ACCESS DENIED: No matching policy found for "
            f"user={user}, bucket={bucket}, object={object_path}, access={access_type}"
        )
        return False, False, policy_id

