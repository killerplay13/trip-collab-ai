from fastapi import FastAPI

from app.config import get_settings
from app.routers import ai, health


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(ai.router)
