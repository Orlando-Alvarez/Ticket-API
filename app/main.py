from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_application()
