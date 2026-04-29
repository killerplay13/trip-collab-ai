import asyncio
from typing import Awaitable, TypeVar

from app.config import Settings
from app.providers.base import AIProvider
from app.schemas.ai import (
    ItineraryGenerateDraft,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)


T = TypeVar("T")


class AIService:
    def __init__(self, provider: AIProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings

    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateDraft:
        return await self._run_with_fallback(
            self.provider.generate_itinerary(request),
            self._itinerary_fallback(request),
        )

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        return await self._run_with_fallback(
            self.provider.explain_settlement(request),
            self._settlement_fallback(),
        )

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        return await self._run_with_fallback(
            self.provider.parse_receipt(request),
            self._receipt_fallback(),
        )

    async def _run_with_fallback(self, awaitable: Awaitable[T], fallback: T) -> T:
        try:
            return await asyncio.wait_for(
                awaitable,
                timeout=self.settings.llm_timeout_seconds,
            )
        except (asyncio.TimeoutError, Exception):
            return fallback

    def _itinerary_fallback(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateDraft:
        return ItineraryGenerateDraft(
            title=f"{request.destination} 行程草稿",
            items=[
                {
                    "day": 1,
                    "title": "暫時無法產生完整 AI 行程",
                    "note": "AI provider timeout or failed. This is a safe fallback draft.",
                }
            ],
            explanation=(
                "AI service is temporarily unavailable. "
                "This fallback draft does not write to DB."
            ),
        )

    def _settlement_fallback(self) -> SettlementExplanation:
        return SettlementExplanation(
            summary="AI explanation is temporarily unavailable.",
            details=[
                "Settlement calculation should still be handled by Spring Boot.",
                "This fallback only explains that AI provider failed or timed out.",
            ],
        )

    def _receipt_fallback(self) -> ReceiptParseDraft:
        return ReceiptParseDraft(
            merchant=None,
            total_amount=None,
            currency=None,
            items=[],
            confidence=0.0,
        )
