from fastapi import APIRouter

from app.api.routes import gateway

api_router = APIRouter()

api_router.include_router(gateway.router)
