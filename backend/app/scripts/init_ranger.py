#!/usr/bin/env python3
import logging
import time

import requests
from requests.auth import HTTPBasicAuth

ranger_url = 'http://ranger-admin:6080'
auth = HTTPBasicAuth('admin', 'rangerR0cks!')

logger = logging.getLogger(__name__)


def wait_for_ranger():
    """Wait for Ranger to be ready"""
    max_retries = 30
    retry_interval = 5


    for i in range(max_retries):
        try:
            response = requests.get(ranger_url, auth=auth, timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass

        if i < max_retries - 1:
            time.sleep(retry_interval)

    return False


def init_ranger():
    """Initialize Ranger with service definitions and policies"""

    print("Init ranger started")

    base_url = f"{ranger_url}/service/public/v2/api"

    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }

    # 1. Create service definition
    service_def = {
        "name": "minio-service-def",
        "label": "MinIO",
        "description": "Custom service definition for controlling access to MinIO via Apache Ranger",
        "resources": [
            {
                "itemId": 1,
                "name": "bucket",
                "type": "string",
                "level": 1,
                "isExcludesSupported": True,
                "isRecursiveSupported": False,
                "matcher": "org.apache.ranger.plugin.resourcematcher.RangerDefaultResourceMatcher",
                "validationRegEx": "^[a-zA-Z0-9_.-]+$",
                "validationMessage": "Bucket name should contain only letters, numbers, dots, underscores and hyphens",
                "uiHint": "Bucket name",
                "label": "Bucket"
            },
            {
                "itemId": 2,
                "name": "object",
                "type": "string",
                "level": 2,
                "isExcludesSupported": True,
                "isRecursiveSupported": True,
                "matcher": "org.apache.ranger.plugin.resourcematcher.RangerDefaultResourceMatcher",
                "validationRegEx": ".*",
                "validationMessage": "Any valid object key or prefix",
                "uiHint": "Object path",
                "label": "Object"
            }
        ],
        "accessTypes": [
            {"itemId": 1, "name": "read", "label": "Read", "impliedGrants": []},
            {"itemId": 2, "name": "write", "label": "Write", "impliedGrants": []},
            {"itemId": 3, "name": "delete", "label": "Delete", "impliedGrants": []},
            {"itemId": 4, "name": "list", "label": "List", "impliedGrants": []}
        ],
        "isEnabled": True
    }

    user2_id = None
    group_id = None

    # Make API calls with retry logic
    for endpoint, data, _description in [
        (f"{base_url}/servicedef", service_def, "service definition"),
        (f"{base_url}/service", {
            "name": "minio-service",
            "type": "minio-service-def",
            "configs": {"minioEndpoint": "http://minio:9000"},
            "description": "MinIO authorization policies"
        }, "service"),
        (f"{ranger_url}/service/xusers/secure/users", {
            "name": "user1",
            "firstName": "User",
            "lastName": "One",
            "password": "rangerR0cks!",
            "userRoleList": ["ROLE_USER"],
            "status": 1,
        }, "user1"),
        (f"{ranger_url}/service/xusers/secure/users", {
            "name": "user2",
            "firstName": "User",
            "lastName": "Two",
            "password": "rangerR0cks!",
            "userRoleList": ["ROLE_USER"],
            "status": 1,
        }, "user2"),
        (f"{ranger_url}/service/xusers/secure/users", {
            "name": "user3",
            "firstName": "User",
            "lastName": "Three",
            "password": "rangerR0cks!",
            "userRoleList": ["ROLE_USER"],
            "status": 1,
        }, "user3"),
        (f"{ranger_url}/service/xusers/groups", {
            "name": "analytics",
        }, "group"),
        (f"{ranger_url}/service/xusers/groupusers", {
            "name": "analytics",
        }, "groupusers"),
        (f"{base_url}/policy", {
            "name": "minio-bucket-policy1",
            "description": "Access to entire bucket",
            "service": "minio-service",
            "isEnabled": True,
            "resources": {
                "bucket": {"values": ["analytics"], "isExcludes": False, "isRecursive": False}
            },
            "policyItems": [
                {
                    "groups": ["analytics"],
                    "accesses": [
                        {"type": "list", "isAllowed": True}
                    ]
                }
            ]
        }, "policy1"),
        (f"{base_url}/policy", {
            "name": "minio-bucket-policy2",
            "description": "Access to entire bucket",
            "service": "minio-service",
            "isEnabled": True,
            "resources": {
                "object": {"values": ["analytics/file.txt"], "isExcludes": False, "isRecursive": False}
            },
            "policyItems": [
                {
                    "users": ["user1"],
                    "accesses": [
                        {"type": "read", "isAllowed": True}
                    ]
                }
            ]
        }, "policy2")
    ]:
        max_retries = 5

        if user2_id and _description == "groupusers":
            data["userId"] = user2_id

        if group_id and _description == "groupusers":
            data["parentGroupId"] = group_id

        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1}/{max_retries} for {_description}")
            try:
                response = requests.post(f"{endpoint}", auth=auth, json=data, headers=headers, timeout=10)
                print(f"Response status code: {response.status_code}")
                if response.status_code in [200, 201]:
                    print(f"✓ Successfully created {_description}: {response.status_code}")
                    print(f"Response: {response.text[:200]}...")
                    response_json = response.json()
                    if _description == "user2":
                        user2_id = response_json["id"]
                    if _description == "group":
                        group_id = response_json["id"]
                    break
                elif response.status_code in [400, 404]:
                    print(f"Response: {response.text[:200]}...")
                    break
                else:
                    pass
            except requests.exceptions.RequestException:
                pass

            if attempt < max_retries - 1:
                time.sleep(3)
        else:
            pass


if __name__ == "__main__":
    if wait_for_ranger():
        init_ranger()
