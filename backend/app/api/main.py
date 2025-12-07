from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.routes import check_ranger_access

api_router = APIRouter()

@api_router.get("/utils/health-check/", tags=["utils"])
def health_check():
    """Health-check endpoint for Docker Compose/monitoring"""
    return JSONResponse(content={"status": "ok"})

api_router.include_router(check_ranger_access.router)
