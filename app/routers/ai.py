from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.providers.base import AIProvider
from app.providers.mock_provider import MockAIProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.schemas.ai import (
    ItineraryGenerateDraft,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)
from app.schemas.common import ApiResponse


router = APIRouter(prefix="/ai", tags=["ai"])


def get_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    provider = settings.ai_provider.lower()

    if provider == "mock":
        return MockAIProvider()
    if provider == "openrouter":
        return OpenRouterProvider()

    raise HTTPException(status_code=500, detail=f"Unsupported AI provider: {settings.ai_provider}")


@router.post(
    "/itinerary/generate",
    response_model=ApiResponse[ItineraryGenerateDraft],
)
async def generate_itinerary(
    request: ItineraryGenerateRequest,
    provider: AIProvider = Depends(get_provider),
) -> ApiResponse[ItineraryGenerateDraft]:
    draft = await provider.generate_itinerary(request)
    return ApiResponse(success=True, data=draft, error=None)


@router.post(
    "/settlement/explain",
    response_model=ApiResponse[SettlementExplanation],
)
async def explain_settlement(
    request: SettlementExplainRequest,
    provider: AIProvider = Depends(get_provider),
) -> ApiResponse[SettlementExplanation]:
    explanation = await provider.explain_settlement(request)
    return ApiResponse(success=True, data=explanation, error=None)


@router.post(
    "/receipt/parse",
    response_model=ApiResponse[ReceiptParseDraft],
)
async def parse_receipt(
    request: ReceiptParseRequest,
    provider: AIProvider = Depends(get_provider),
) -> ApiResponse[ReceiptParseDraft]:
    draft = await provider.parse_receipt(request)
    return ApiResponse(success=True, data=draft, error=None)
