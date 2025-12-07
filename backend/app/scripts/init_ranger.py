#!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth
import time
import os
import sys

ranger_url = 'http://ranger-admin:6080'
auth = HTTPBasicAuth('admin', 'rangerR0cks!')


def wait_for_ranger():
    """Wait for Ranger to be ready"""
    max_retries = 30
    retry_interval = 5

    print(f"Waiting for Ranger at {ranger_url}...")

    for i in range(max_retries):
        try:
            response = requests.get(ranger_url, auth=auth, timeout=5)
            if response.status_code == 200:
                print("Ranger is ready!")
                return True
        except requests.exceptions.RequestException:
            pass

        if i < max_retries - 1:
            print(f"Attempt {i + 1}/{max_retries} failed, retrying in {retry_interval}s...")
            time.sleep(retry_interval)

    print("ERROR: Ranger is not ready after maximum retries")
    return False


def init_ranger():
    """Initialize Ranger with service definitions and policies"""

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

    # Make API calls with retry logic
    for endpoint, data, description in [
        (f"{base_url}/servicedef", service_def, "service definition"),
        (f"{base_url}/service", {
            "name": "minio-service",
            "type": "minio-service-def",
            "configs": {"minioEndpoint": "http://minio:9000"},
            "description": "MinIO authorization policies"
        }, "service"),
        (f"{ranger_url}/service/xusers/users", {
            "name": "user1",
            "firstName": "User",
            "lastName": "One",
            "password": "rangerR0cks!",
            "userRoleList": ["ROLE_USER"],
            "status": 1,
        }, "user"),
        (f"{base_url}/policy", {
            "name": "minio-bucket-policy",
            "description": "Access to entire bucket",
            "service": "minio-service",
            "isEnabled": True,
            "resources": {
                "bucket": {"values": ["analytics"], "isExcludes": False, "isRecursive": False}
            },
            "policyItems": [
                {
                    "users": ["user1"],
                    "accesses": [
                        {"type": "write", "isAllowed": True},
                        {"type": "list", "isAllowed": True}
                    ]
                },
                {
                    "users": ["admin"],
                    "delegateAdmin": True,
                    "accesses": [
                        {"type": "read", "isAllowed": True},
                        {"type": "write", "isAllowed": True},
                        {"type": "list", "isAllowed": True},
                        {"type": "delete", "isAllowed": True},
                    ]
                }
            ]
        }, "policy")
    ]:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(f"{endpoint}", auth=auth, json=data, headers=headers, timeout=10)
                if response.status_code in [200, 201]:
                    print(f"✓ Successfully created {description}")
                    break
                elif response.status_code in [400, 404]:
                    print(f"✓ {description} already exists")
                    break
                else:
                    print(f"✗ Failed to create {description} (HTTP {response.status_code})")
            except requests.exceptions.RequestException as e:
                print(f"✗ Request failed for {description}: {e}")

            if attempt < max_retries - 1:
                time.sleep(3)
        else:
            print(f"ERROR: Failed to create {description} after {max_retries} attempts")


if __name__ == "__main__":
    if wait_for_ranger():
        init_ranger()
        print("Initialization completed!")

        # Start FastAPI app
        print("Starting FastAPI application...")
