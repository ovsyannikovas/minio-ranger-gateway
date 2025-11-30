"""Apache Ranger client for fetching policies."""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RangerClient:
    """Client for Apache Ranger REST API - fetches policies."""

    def __init__(
        self,
        base_url: str = settings.RANGER_HOST,
        username: str = settings.RANGER_USER,
        password: str = settings.RANGER_PASSWORD,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.auth = (username, password)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=self.auth,
            timeout=10.0,
        )

    async def get_policies(self, service_name: str) -> list[dict[str, Any]]:
        """
        Get all policies for a service from Ranger.

        Args:
            service_name: Name of the Ranger service

        Returns:
            List of policy dictionaries
        """
        # Try different possible endpoints
        endpoints = [
            # f"{self.base_url}/plugins/policies?serviceName={service_name}",
            f"{self.base_url}/service/public/v2/api/service/{service_name}/policy",
        ]
        logger.warning(endpoints)

        for url in endpoints:
            try:
                response = await self._client.get(url)
                logger.warning(response.json())
                response.raise_for_status()

                result = response.json()
                # Handle different response formats
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict):
                    # Some APIs return {"policies": [...]} or {"vXPolicies": [...]}
                    if "policies" in result:
                        return result["policies"]
                    elif "vXPolicies" in result:
                        return result["vXPolicies"]
                    elif "data" in result:
                        return result["data"]
                    else:
                        # Return the dict itself if it looks like a policy
                        print("HERE2")
                        return [result] if "policyItems" in result else []
                else:
                    logger.warning(f"Unexpected response format from {url}: {type(result)}")
                    continue
            except httpx.HTTPError as e:
                logger.debug(f"Failed to get policies from {url}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Unexpected error from {url}: {e}")
                continue

        logger.error(f"Failed to get policies for service {service_name} from all endpoints")
        return []

    async def get_user(self, username: str) -> dict[str, Any] | None:
        """
        Get user information including groups from Ranger.

        Args:
            username: Username

        Returns:
            User dictionary with groups or None if not found
        """
        # Try different possible endpoints
        endpoints = [
            f"{self.base_url}/service/xusers/users/userName/{username}",
        ]
        logger.info(endpoints)

        for url in endpoints:
            try:
                logger.warning("before")
                response = await self._client.get(url)
                logger.warning("get_user")
                logger.warning(response.json())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(f"User {username} not found at {url}")
                    continue
                else:
                    logger.warning(f"HTTP error from {url}: {e}")
                    continue
            except httpx.HTTPError as e:
                logger.warning(f"Failed to get user from {url}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error from {url}: {e}")
                continue

        logger.warning(f"Failed to get user {username} from all endpoints")
        return None

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
