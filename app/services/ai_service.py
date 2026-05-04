import asyncio
import logging
import time
from collections.abc import Callable
from typing import Awaitable, TypeVar
from uuid import uuid4

from app.config import Settings
from app.providers.base import AIProvider
from app.providers.exceptions import AIProviderError
from app.schemas.ai import (
    ItineraryDraftItem,
    ItineraryGenerateData,
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
    ) -> ItineraryGenerateData:
        return await self._execute_with_fallback(
            "itinerary.generate",
            self.provider.generate_itinerary(request),
            lambda fallback_reason: self._itinerary_fallback(request, fallback_reason),
        )

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        return await self._execute_with_fallback(
            "settlement.explain",
            self.provider.explain_settlement(request),
            lambda fallback_reason: self._settlement_fallback(request.language),
        )

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        return await self._execute_with_fallback(
            "receipt.parse",
            self.provider.parse_receipt(request),
            lambda fallback_reason: self._receipt_fallback(),
        )

    async def _execute_with_fallback(
        self,
        task_name: str,
        provider_call: Awaitable[T],
        fallback_factory: Callable[[str], T],
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
            return fallback_factory("timeout")
        except AIProviderError as exc:
            fallback_reason = self._fallback_reason_from_exception(exc)
            duration_ms = self._duration_ms(started_at)
            logger.exception(
                "ai_execution task_name=%s provider_name=%s request_id=%s "
                "success=false fallback=true fallback_reason=%s duration_ms=%s",
                task_name,
                provider_name,
                request_id,
                fallback_reason,
                duration_ms,
            )
            return fallback_factory(fallback_reason)
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
            return fallback_factory("provider_error")

    def _duration_ms(self, started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

    def _fallback_reason_from_exception(self, exc: AIProviderError) -> str:
        return getattr(exc, "fallback_reason", "provider_error")

    def _itinerary_fallback(
        self, request: ItineraryGenerateRequest, fallback_reason: str
    ) -> ItineraryGenerateData:
        return ItineraryGenerateData(
            items=[
                ItineraryDraftItem(
                    day_date=request.start_date,
                    title=f"{request.destination} fallback draft",
                    start_time=None,
                    end_time=None,
                    location_name=None,
                    map_url=None,
                    note="AI provider timeout or failed. This is a safe fallback draft.",
                    sort_order=1,
                )
            ],
            explanation=(
                "AI service is temporarily unavailable. "
                "This fallback draft does not write to DB."
            ),
            warnings=["AI provider failed or timed out."],
            source="fallback",
            fallback=True,
            fallback_reason=fallback_reason,
        )

    def _settlement_fallback(self, language: str = "en") -> SettlementExplanation:
        if language.startswith("zh"):
            return SettlementExplanation(
                summary="AI 說明暫時無法取得",
                steps=["請參考後端結算結果進行轉帳"],
                tips=["AI 服務暫時失敗或逾時，請稍後再試"],
            )

        return SettlementExplanation(
            summary="AI explanation temporarily unavailable",
            steps=["Please refer to backend settlement result"],
            tips=["AI service failed or timed out"],
        )

    def _receipt_fallback(self) -> ReceiptParseDraft:
        return ReceiptParseDraft(
            merchant=None,
            total_amount=None,
            currency=None,
            items=[],
            confidence=0.0,
        )
