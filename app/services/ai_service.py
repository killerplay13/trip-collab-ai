import asyncio
import logging
import time
from collections.abc import Callable
from typing import Awaitable, TypeVar
from uuid import uuid4

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
logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, provider: AIProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings

    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateDraft:
        return await self._execute_with_fallback(
            "itinerary.generate",
            self.provider.generate_itinerary(request),
            lambda: self._itinerary_fallback(request),
        )

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        return await self._execute_with_fallback(
            "settlement.explain",
            self.provider.explain_settlement(request),
            self._settlement_fallback,
        )

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        return await self._execute_with_fallback(
            "receipt.parse",
            self.provider.parse_receipt(request),
            self._receipt_fallback,
        )

    async def _execute_with_fallback(
        self,
        task_name: str,
        provider_call: Awaitable[T],
        fallback_factory: Callable[[], T],
    ) -> T:
        request_id = str(uuid4())
        provider_name = self.provider.__class__.__name__
        started_at = time.perf_counter()

        try:
            result = await asyncio.wait_for(
                provider_call,
                timeout=self.settings.llm_timeout_seconds,
            )
            duration_ms = self._duration_ms(started_at)
            logger.info(
                "ai_execution task_name=%s provider_name=%s request_id=%s "
                "success=true fallback=false fallback_reason=none duration_ms=%s",
                task_name,
                provider_name,
                request_id,
                duration_ms,
            )
            return result
        except asyncio.TimeoutError:
            duration_ms = self._duration_ms(started_at)
            logger.warning(
                "ai_execution task_name=%s provider_name=%s request_id=%s "
                "success=false fallback=true fallback_reason=timeout duration_ms=%s",
                task_name,
                provider_name,
                request_id,
                duration_ms,
            )
            return fallback_factory()
        except Exception:
            duration_ms = self._duration_ms(started_at)
            logger.exception(
                "ai_execution task_name=%s provider_name=%s request_id=%s "
                "success=false fallback=true fallback_reason=provider_error duration_ms=%s",
                task_name,
                provider_name,
                request_id,
                duration_ms,
            )
            return fallback_factory()

    def _duration_ms(self, started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

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
