from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.common import ApiResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[dict[str, str]])
async def health(settings: Settings = Depends(get_settings)) -> ApiResponse[dict[str, str]]:
    return ApiResponse(
        success=True,
        data={
            "status": "ok",
            "service": settings.app_name,
            "env": settings.app_env,
            "provider": settings.ai_provider,
        },
        error=None,
    )
