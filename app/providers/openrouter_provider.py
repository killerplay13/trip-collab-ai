from app.providers.base import AIProvider
from app.schemas.ai import (
    ItineraryGenerateDraft,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)


class OpenRouterProvider(AIProvider):
    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateDraft:
        # Phase 1 will implement the real OpenRouter call with timeout handling,
        # rate limit handling, quota exceeded handling, invalid JSON recovery,
        # and fallback behavior.
        raise NotImplementedError("OpenRouterProvider is planned for Phase 1.")

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        # Phase 1 will implement the real OpenRouter call with timeout handling,
        # rate limit handling, quota exceeded handling, invalid JSON recovery,
        # and fallback behavior.
        raise NotImplementedError("OpenRouterProvider is planned for Phase 1.")

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        # Phase 1 will implement the real OpenRouter call with timeout handling,
        # rate limit handling, quota exceeded handling, invalid JSON recovery,
        # and fallback behavior.
        raise NotImplementedError("OpenRouterProvider is planned for Phase 1.")
