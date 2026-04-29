from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.providers.base import AIProvider
from app.providers.mock_provider import MockAIProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.schemas.ai import (
    ItineraryGenerateData,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)
from app.schemas.common import ApiResponse
from app.services.ai_service import AIService


router = APIRouter(prefix="/ai", tags=["ai"])


def get_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    provider = settings.ai_provider.lower()

    if provider == "mock":
        return MockAIProvider()
    if provider == "openrouter":
        return OpenRouterProvider(settings)

    raise HTTPException(status_code=500, detail=f"Unsupported AI provider: {settings.ai_provider}")


def get_ai_service(
    provider: AIProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings),
) -> AIService:
    return AIService(provider, settings)


@router.post(
    "/itinerary/generate",
    response_model=ApiResponse[ItineraryGenerateData],
)
async def generate_itinerary(
    request: ItineraryGenerateRequest,
    service: AIService = Depends(get_ai_service),
) -> ApiResponse[ItineraryGenerateData]:
    draft = await service.generate_itinerary(request)
    return ApiResponse(success=True, data=draft, error=None)


@router.post(
    "/settlement/explain",
    response_model=ApiResponse[SettlementExplanation],
)
async def explain_settlement(
    request: SettlementExplainRequest,
    service: AIService = Depends(get_ai_service),
) -> ApiResponse[SettlementExplanation]:
    explanation = await service.explain_settlement(request)
    return ApiResponse(success=True, data=explanation, error=None)


@router.post(
    "/receipt/parse",
    response_model=ApiResponse[ReceiptParseDraft],
)
async def parse_receipt(
    request: ReceiptParseRequest,
    service: AIService = Depends(get_ai_service),
) -> ApiResponse[ReceiptParseDraft]:
    draft = await service.parse_receipt(request)
    return ApiResponse(success=True, data=draft, error=None)
