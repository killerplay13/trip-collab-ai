import asyncio
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import app
from app.prompts.itinerary_prompt_builder import build_itinerary_generate_prompt
from app.providers.base import AIProvider
from app.providers.exceptions import (
    AIProviderError,
    ProviderHTTPError,
    ProviderInvalidResponseError,
    ProviderQuotaExceededError,
    ProviderRateLimitError,
)
from app.schemas.ai import (
    ItineraryDraftItem,
    ItineraryGenerateData,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)
from app.services.ai_service import AIService


client = TestClient(app)
app.dependency_overrides[get_settings] = lambda: Settings(ai_provider="mock")


def itinerary_request_payload() -> dict[str, object]:
    return {
        "trip_title": "Tokyo spring trip",
        "destination": "Tokyo",
        "start_date": "2026-05-01",
        "end_date": "2026-05-02",
        "timezone": "Asia/Tokyo",
        "travelers_count": 2,
        "travel_style": "relaxed",
        "budget_level": "medium",
        "interests": ["food", "museum"],
        "must_visit_places": ["Ueno Park"],
        "avoid_places": ["crowded nightlife"],
        "notes": "Prefer public transit.",
        "language": "en",
    }


def test_generate_itinerary_endpoint() -> None:
    response = client.post(
        "/ai/itinerary/generate",
        json=itinerary_request_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert set(body["data"].keys()) == {
        "items",
        "explanation",
        "warnings",
        "source",
        "fallback",
        "fallback_reason",
    }
    assert body["data"]["items"]
    assert body["data"]["source"] == "mock"
    assert body["data"]["fallback"] is False
    assert body["data"]["fallback_reason"] is None


def test_generate_itinerary_rejects_end_date_before_start_date() -> None:
    payload = itinerary_request_payload()
    payload["start_date"] = "2026-05-02"
    payload["end_date"] = "2026-05-01"

    response = client.post("/ai/itinerary/generate", json=payload)

    assert response.status_code == 422


def test_generate_itinerary_rejects_blank_trip_title() -> None:
    payload = itinerary_request_payload()
    payload["trip_title"] = "   "

    response = client.post("/ai/itinerary/generate", json=payload)

    assert response.status_code == 422


def test_generate_itinerary_rejects_blank_destination() -> None:
    payload = itinerary_request_payload()
    payload["destination"] = "   "

    response = client.post("/ai/itinerary/generate", json=payload)

    assert response.status_code == 422


def test_itinerary_draft_item_rejects_zero_sort_order() -> None:
    with pytest.raises(ValidationError):
        ItineraryDraftItem(
            day_date="2026-05-01",
            title="Breakfast",
            sort_order=0,
        )


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
    ) -> ItineraryGenerateData:
        await asyncio.sleep(0.01)
        return ItineraryGenerateData(items=[], explanation="Too slow")

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
    ) -> ItineraryGenerateData:
        raise RuntimeError("provider failed")

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        raise RuntimeError("provider failed")

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        raise RuntimeError("provider failed")


class ProviderErrorProvider(AIProvider):
    def __init__(self, error: AIProviderError) -> None:
        self.error = error

    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateData:
        raise self.error

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        raise self.error

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        raise self.error


@pytest.mark.asyncio
async def test_generate_itinerary_timeout_returns_fallback() -> None:
    service = AIService(SlowProvider(), Settings(llm_timeout_seconds=0))
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    result = await service.generate_itinerary(request)

    assert result.fallback is True
    assert result.fallback_reason == "timeout"
    assert result.items[0].note == "AI provider timeout or failed. This is a safe fallback draft."
    assert "temporarily unavailable" in result.explanation


@pytest.mark.asyncio
async def test_generate_itinerary_provider_exception_returns_fallback() -> None:
    service = AIService(BrokenProvider(), Settings(llm_timeout_seconds=1))
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    result = await service.generate_itinerary(request)

    assert result.fallback is True
    assert result.fallback_reason == "provider_error"
    assert result.items[0].title == "Tokyo fallback draft"
    assert "does not write to DB" in result.explanation


@pytest.mark.asyncio
async def test_timeout_fallback_writes_structured_log(caplog: pytest.LogCaptureFixture) -> None:
    service = AIService(SlowProvider(), Settings(llm_timeout_seconds=0))
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    with caplog.at_level(logging.WARNING, logger="app.services.ai_service"):
        result = await service.generate_itinerary(request)

    assert result.fallback is True
    assert result.fallback_reason == "timeout"
    assert "task_name=itinerary.generate" in caplog.text
    assert "fallback_reason=timeout" in caplog.text


@pytest.mark.asyncio
async def test_provider_error_fallback_writes_structured_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AIService(BrokenProvider(), Settings(llm_timeout_seconds=1))
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    with caplog.at_level(logging.ERROR, logger="app.services.ai_service"):
        result = await service.generate_itinerary(request)

    assert result.fallback is True
    assert result.fallback_reason == "provider_error"
    assert "task_name=itinerary.generate" in caplog.text
    assert "fallback_reason=provider_error" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "fallback_reason"),
    [
        (ProviderInvalidResponseError("invalid response"), "invalid_response"),
        (ProviderRateLimitError("rate limited"), "rate_limited"),
        (ProviderQuotaExceededError("quota exceeded"), "quota_exceeded"),
        (ProviderHTTPError("provider http error"), "provider_http_error"),
    ],
)
async def test_provider_error_type_controls_itinerary_fallback_reason_and_log(
    caplog: pytest.LogCaptureFixture,
    error: AIProviderError,
    fallback_reason: str,
) -> None:
    service = AIService(ProviderErrorProvider(error), Settings(llm_timeout_seconds=1))
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    with caplog.at_level(logging.ERROR, logger="app.services.ai_service"):
        result = await service.generate_itinerary(request)

    assert result.fallback is True
    assert result.fallback_reason == fallback_reason
    assert f"fallback_reason={fallback_reason}" in caplog.text


def test_itinerary_prompt_builder_contains_contract_terms() -> None:
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    prompt = build_itinerary_generate_prompt(request)

    assert "Return JSON only" in prompt
    assert "Do not include markdown" in prompt
    assert "items" in prompt
    assert "day_date" in prompt
    assert "start_time" in prompt
    assert "end_time" in prompt
    assert "sort_order" in prompt
    assert "Tokyo" in prompt
    assert "2026-05-01" in prompt
    assert "2026-05-02" in prompt
