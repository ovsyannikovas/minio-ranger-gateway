"""MinIO Gateway routes - proxy requests to MinIO with Ranger authorization."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
import httpx

from app.core.config import settings
from app.gateway.authorizer import (
    check_authorization,
    extract_resource_from_path,
    map_http_method_to_access_type,
)
from app.gateway.user_groups import get_user_groups_from_ranger

logger = logging.getLogger(__name__)

router = APIRouter()

# HTTP client for proxying to MinIO
_minio_client: httpx.AsyncClient | None = None


def get_minio_client() -> httpx.AsyncClient:
    """Get or create MinIO HTTP client."""
    global _minio_client
    if _minio_client is None:
        _minio_client = httpx.AsyncClient(
            base_url=settings.MINIO_ENDPOINT,
            timeout=60.0,
        )
    return _minio_client


@router.api_route("/{path:path}", methods=["GET", "PUT", "POST", "DELETE", "HEAD"])
async def proxy_to_minio(
    request: Request,
    path: str,
) -> Response:
    """
    Proxy S3 requests to MinIO with Ranger authorization.

    This endpoint:
    1. Extracts user, bucket, and object from the request
    2. Checks authorization with Ranger
    3. If allowed, proxies the request to MinIO
    4. Returns the response from MinIO
    """
    # Extract user from request (for now, from header or query param)
    # TODO: Implement proper authentication (AWS Signature, JWT, etc.)
    user = request.headers.get("X-User", "admin")
    
    # Get user groups from Ranger UserSync
    # Fallback to header if Ranger is unavailable or user not found
    user_groups = await get_user_groups_from_ranger(user)
    if not user_groups:
        # Fallback: try to get from header if provided
        user_groups_str = request.headers.get("X-User-Groups", "")
        user_groups = [g.strip() for g in user_groups_str.split(",") if g.strip()] if user_groups_str else []

    # Extract bucket and object from path
    bucket, object_path = extract_resource_from_path(path)

    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bucket name is required",
        )

    # Map HTTP method to access type
    access_type = map_http_method_to_access_type(request.method)

    # For bucket-only requests (list), adjust access type
    if object_path is None and request.method.upper() == "GET":
        access_type = "list"

    # Check authorization
    is_allowed, is_audited = await check_authorization(
        user=user,
        bucket=bucket,
        object_path=object_path,
        access_type=access_type,
        user_groups=user_groups,
    )

    if not is_allowed:
        logger.warning(
            f"Access denied: user={user}, bucket={bucket}, "
            f"object={object_path}, access={access_type}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied by policy",
        )

    # Log audit if required
    if is_audited:
        logger.info(
            f"Audit: user={user}, bucket={bucket}, "
            f"object={object_path}, access={access_type}, allowed={is_allowed}"
        )

    # Proxy request to MinIO
    try:
        minio_client = get_minio_client()

        # Prepare request to MinIO
        url = f"/{path}"
        headers = dict(request.headers)
        # Remove gateway-specific headers
        headers.pop("host", None)
        headers.pop("X-User", None)
        headers.pop("X-User-Groups", None)

        # Get request body if present
        body = await request.body() if request.method in ("PUT", "POST") else None

        # Forward request to MinIO
        response = await minio_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )

        # Return response from MinIO
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )
    except httpx.HTTPError as e:
        logger.error(f"Error proxying to MinIO: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error connecting to MinIO",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

