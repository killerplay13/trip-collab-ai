from abc import ABC, abstractmethod

from app.schemas.ai import (
    ItineraryGenerateData,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)


class AIProvider(ABC):
    @abstractmethod
    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateData:
        raise NotImplementedError

    @abstractmethod
    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        raise NotImplementedError

    @abstractmethod
    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        raise NotImplementedError
