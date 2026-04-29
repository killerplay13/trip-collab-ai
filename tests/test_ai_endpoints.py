import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.providers.base import AIProvider
from app.schemas.ai import (
    ItineraryGenerateDraft,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)
from app.services.ai_service import AIService


client = TestClient(app)


def test_generate_itinerary_endpoint() -> None:
    response = client.post(
        "/ai/itinerary/generate",
        json={
            "trip_id": "trip_123",
            "destination": "Tokyo",
            "days": 2,
            "preferences": ["food", "museum"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["title"]


def test_explain_settlement_endpoint() -> None:
    response = client.post(
        "/ai/settlement/explain",
        json={
            "trip_id": "trip_123",
            "expenses_summary": {"currency": "TWD", "total": 3000},
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_parse_receipt_endpoint() -> None:
    response = client.post(
        "/ai/receipt/parse",
        json={"raw_text": "Mock receipt text"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


class SlowProvider(AIProvider):
    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateDraft:
        await asyncio.sleep(0.01)
        return ItineraryGenerateDraft(title="Too slow", items=[], explanation="Too slow")

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        await asyncio.sleep(0.01)
        return SettlementExplanation(summary="Too slow", details=[])

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        await asyncio.sleep(0.01)
        return ReceiptParseDraft(confidence=1.0)


class BrokenProvider(AIProvider):
    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateDraft:
        raise RuntimeError("provider failed")

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        raise RuntimeError("provider failed")

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        raise RuntimeError("provider failed")


@pytest.mark.asyncio
async def test_generate_itinerary_timeout_returns_fallback() -> None:
    service = AIService(SlowProvider(), Settings(llm_timeout_seconds=0))
    request = ItineraryGenerateRequest(
        trip_id="trip_123",
        destination="Tokyo",
        days=2,
    )

    result = await service.generate_itinerary(request)

    assert result.title == "Tokyo 行程草稿"
    assert result.items[0]["note"] == "AI provider timeout or failed. This is a safe fallback draft."
    assert "temporarily unavailable" in result.explanation


@pytest.mark.asyncio
async def test_generate_itinerary_provider_exception_returns_fallback() -> None:
    service = AIService(BrokenProvider(), Settings(llm_timeout_seconds=1))
    request = ItineraryGenerateRequest(
        trip_id="trip_123",
        destination="Tokyo",
        days=2,
    )

    result = await service.generate_itinerary(request)

    assert result.title == "Tokyo 行程草稿"
    assert result.items[0]["title"] == "暫時無法產生完整 AI 行程"
    assert "does not write to DB" in result.explanation
