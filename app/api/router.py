from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.tickets import router as tickets_router
from app.core.config import settings

api_router = APIRouter(prefix=settings.api_v1_prefix)
api_router.include_router(health_router, tags=["health"])
api_router.include_router(tickets_router, tags=["tickets"])
