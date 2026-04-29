from fastapi import FastAPI

from app.config import get_settings
from app.logging_config import setup_logging
from app.routers import ai, health


settings = get_settings()
setup_logging(settings)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(ai.router)
