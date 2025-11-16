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
        # Check each policy
        for policy in policies:
            if not policy.get("isEnabled", True):
                continue

            # Check if policy resources match
            policy_resources = policy.get("resources", {})
            policy_bucket = policy_resources.get("bucket")
            policy_object = policy_resources.get("object")

            if policy_bucket is None:
                continue

            # Check bucket match
            if not PolicyMatcher.match_bucket(bucket, policy_bucket):
                continue

            # Check object match (if object_path is provided)
            if object_path is not None:
                if not PolicyMatcher.match_object(object_path, policy_object):
                    continue
            else:
                # For bucket-level operations, object policy should not restrict
                # (or should be None/empty)
                if policy_object and policy_object.get("values"):
                    # Policy has object restrictions, but request is bucket-level
                    # This might be a mismatch, but we'll allow if bucket matches
                    pass

            # Check if user or group matches
            policy_items = policy.get("policyItems", [])
            for policy_item in policy_items:
                # Check users
                policy_users = policy_item.get("users", [])
                user_match = user in policy_users if policy_users else False

                # Check groups
                policy_groups = policy_item.get("groups", [])
                # If policy has groups and user has groups, check if any match
                if policy_groups and user_groups:
                    group_match = any(group in policy_groups for group in user_groups)
                else:
                    group_match = False

                # User must match either by name OR by group membership
                if not (user_match or group_match):
                    continue

                # Check access type
                accesses = policy_item.get("accesses", [])
                for access in accesses:
                    if access.get("type") == access_type and access.get("isAllowed", False):
                        # Match found! Check if audited
                        is_audited = policy.get("isAuditEnabled", True)
                        return True, is_audited

        # No matching policy found - deny by default
        return False, False

