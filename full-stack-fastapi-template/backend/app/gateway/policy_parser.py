"""Parser for Ranger policies - local authorization check."""

import logging
import re
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
    ) -> bool:
        """
        Check if resource matches policy resource values.

        Args:
            resource_value: The resource value to check (e.g., bucket name or object path)
            policy_values: List of policy resource values
            is_excludes: If True, this is an exclude rule (invert match)
            is_recursive: If True, match recursively (for paths)

        Returns:
            True if resource matches policy
        """
        if not policy_values:
            return False

        # Check each policy value
        for policy_value in policy_values:
            if is_recursive:
                # For recursive matching (e.g., object paths)
                # Check if resource starts with policy value
                if resource_value.startswith(policy_value):
                    match = True
                else:
                    # Also check exact match
                    match = resource_value == policy_value
            else:
                # Exact match for non-recursive (e.g., bucket names)
                match = resource_value == policy_value

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
    def match_object(object_path: str | None, policy_object: dict[str, Any] | None) -> bool:
        """Match object path against policy object definition."""
        if policy_object is None:
            # No object restriction means match any object
            return True

        if object_path is None:
            # Request is for bucket, not object
            # Check if policy allows bucket-level access
            return True

        values = policy_object.get("values", [])
        is_excludes = policy_object.get("isExcludes", False)
        is_recursive = policy_object.get("isRecursive", True)  # Default True for objects

        return PolicyMatcher.match_resource(object_path, values, is_excludes, is_recursive)


import logging
from typing import Any

logger = logging.getLogger(__name__)

class PolicyChecker:
    """Checks authorization against loaded policies."""

    @staticmethod
    def check_access(
        policies: list[dict[str, Any]],
        user: str,
        user_groups: list[str],
        bucket: str,
        object_path: str | None,
        access_type: str,
    ) -> tuple[bool, bool]:
        """
        Check if user has access based on policies.

        Args:
            policies: List of policy dictionaries from Ranger
            user: Username
            user_groups: List of user groups
            bucket: Bucket name
            object_path: Object path (optional)
            access_type: Access type (read, write, delete, list)

        Returns:
            Tuple of (is_allowed, is_audited)
        """
        logger.debug(f"Starting policy check: user={user}, groups={user_groups}, bucket={bucket}, object={object_path}, access={access_type}")

        # Check each policy
        for i, policy in enumerate(policies):
            policy_name = policy.get("name", f"UnnamedPolicy-{i}")
            logger.debug(f"Checking policy [{i}]: {policy_name}")

            if not policy.get("isEnabled", True):
                logger.debug(f"Policy {policy_name} is disabled, skipping.")
                continue

            # Check if policy resources match
            policy_resources = policy.get("resources", {})
            policy_bucket = policy_resources.get("bucket")
            policy_object = policy_resources.get("object")

            if policy_bucket is None:
                logger.debug(f"Policy {policy_name} has no bucket resource, skipping.")
                continue

            # Check bucket match
            if not PolicyMatcher.match_bucket(bucket, policy_bucket):
                logger.debug(f"Bucket '{bucket}' does not match policy {policy_name}.")
                continue
            else:
                logger.debug(f"Bucket '{bucket}' matches policy {policy_name}.")

            # Check object match (if object_path is provided)
            if object_path is not None:
                if not PolicyMatcher.match_object(object_path, policy_object):
                    logger.debug(f"Object '{object_path}' does not match policy {policy_name}.")
                    continue
                else:
                    logger.debug(f"Object '{object_path}' matches policy {policy_name}.")
            else:
                logger.debug(f"No object path provided. Checking bucket-level access for policy {policy_name}.")

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
                        is_audited = policy.get("isAuditEnabled", True)
                        logger.info(
                            f"✅ ACCESS GRANTED by policy '{policy_name}': "
                            f"user={user}, bucket={bucket}, object={object_path}, access={access_type}, audited={is_audited}"
                        )
                        return True, is_audited

            if not matched:
                logger.debug(f"No matching access found in policy {policy_name}.")

        logger.warning(
            f"❌ ACCESS DENIED: No matching policy found for "
            f"user={user}, bucket={bucket}, object={object_path}, access={access_type}"
        )
        return False, False

