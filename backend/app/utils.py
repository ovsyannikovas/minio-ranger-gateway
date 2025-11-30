import re
from fastapi import Request, HTTPException


async def get_user_from_access_key(request: Request, redis_client) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    match = re.search(r"Credential=([^/]+)/", auth_header)
    if not match:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    access_key = match.group(1)
    user = await redis_client.get(access_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid access key")
    return user.decode("utf-8")
