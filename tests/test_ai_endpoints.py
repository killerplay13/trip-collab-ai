import asyncio
import logging
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import app
from app.prompts.itinerary_prompt_builder import build_itinerary_generate_prompt
from app.prompts.settlement_prompt import build_settlement_prompt
from app.providers.base import AIProvider
from app.providers.exceptions import (
    AIProviderError,
    ProviderHTTPError,
    ProviderInvalidJSONError,
    ProviderInvalidResponseError,
    ProviderQuotaExceededError,
    ProviderRateLimitError,
)
from app.schemas.ai import (
    ExistingItineraryItem,
    ExpenseInsightRequest,
    ItineraryDraftItem,
    ItineraryGenerateData,
    ItineraryGenerateRequest,
    ItineraryQualityChecks,
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


def settlement_request_payload() -> dict[str, object]:
    return {
        "trip_id": "trip_123",
        "currency": "TWD",
        "members": [
            {"member_id": "alice", "name": "Alice"},
            {"member_id": "bob", "name": "Bob"},
        ],
        "balances": [
            {"member_id": "alice", "net_balance": -300.0},
            {"member_id": "bob", "net_balance": 300.0},
        ],
        "transactions": [
            {"from": "alice", "to": "bob", "amount": 300.0},
        ],
    }


def settlement_request_with_member_summaries() -> dict[str, object]:
    payload = settlement_request_payload()
    payload.update(
        {
            "language": "en",
            "total_expense": 900.0,
            "member_count": 2,
            "transaction_count": 1,
            "member_summaries": [
                {
                    "member_id": "alice",
                    "name": "Alice",
                    "paid_total": 900.0,
                    "owed_total": 450.0,
                    "net_balance": 450.0,
                },
                {
                    "member_id": "bob",
                    "name": "Bob",
                    "paid_total": 0.0,
                    "owed_total": 450.0,
                    "net_balance": -450.0,
                },
            ],
        }
    )
    return payload


def expense_insight_request_payload() -> dict[str, object]:
    return {
        "trip_id": "trip_123",
        "language": "zh-TW",
        "currency": "TWD",
        "totalAmount": 12800,
        "expenseCount": 18,
        "memberCount": 4,
        "dailyTotals": [
            {"date": "2026-05-04", "amount": 5200},
            {"date": "2026-05-05", "amount": 7600},
        ],
        "topExpenses": [
            {"title": "Hotel", "amount": 6000, "date": "2026-05-04"},
            {"title": "Dinner", "amount": 1800, "date": "2026-05-05"},
        ],
        "memberBalances": [
            {"memberName": "Alice", "paidAmount": 5000, "shareAmount": 3200, "balance": 1800},
            {"memberName": "Bob", "paidAmount": 2500, "shareAmount": 4300, "balance": -1800},
        ],
        "budgetAmount": 20000,
        "remainingDays": 2,
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
        "quality_checks",
    }
    assert body["data"]["items"]
    assert body["data"]["source"] == "mock"
    assert body["data"]["fallback"] is False
    assert body["data"]["fallback_reason"] is None


def test_itinerary_generate_data_accepts_quality_checks() -> None:
    data = ItineraryGenerateData(
        items=[
            ItineraryDraftItem(
                day_date="2026-05-01",
                title="Draft",
                sort_order=1,
            )
        ],
        explanation="Draft.",
        quality_checks=ItineraryQualityChecks(
            has_out_of_scope_place=True,
            has_unrealistic_transport=True,
            needs_user_review=True,
        ),
    )

    assert data.quality_checks is not None
    assert data.quality_checks.has_out_of_scope_place is True
    assert data.quality_checks.has_unrealistic_transport is True
    assert data.quality_checks.has_time_conflict is False
    assert data.quality_checks.needs_user_review is True


def test_generate_itinerary_request_accepts_existing_context_defaults() -> None:
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    assert request.existing_itinerary == []
    assert request.avoid_duplicate_places is True


def test_generate_itinerary_request_accepts_existing_context() -> None:
    payload = itinerary_request_payload()
    payload["existing_itinerary"] = [
        {
            "day_date": "2026-05-01",
            "title": "Ueno Park",
            "location_name": "Ueno Park",
            "note": "Already planned.",
        }
    ]
    payload["avoid_duplicate_places"] = True

    request = ItineraryGenerateRequest(**payload)

    assert request.existing_itinerary == [
        ExistingItineraryItem(
            day_date="2026-05-01",
            title="Ueno Park",
            location_name="Ueno Park",
            note="Already planned.",
        )
    ]
    assert request.avoid_duplicate_places is True


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
        json=settlement_request_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"]
    assert isinstance(body["data"]["steps"], list)
    assert isinstance(body["data"]["tips"], list)
    assert "Alice should pay Bob 300 TWD." in body["data"]["steps"]


def test_explain_settlement_old_request_backward_compatible() -> None:
    response = client.post(
        "/ai/settlement/explain",
        json=settlement_request_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"]
    assert isinstance(body["data"]["steps"], list)


def test_explain_settlement_with_language_zh_tw() -> None:
    payload = settlement_request_payload()
    payload["language"] = "zh-TW"

    response = client.post("/ai/settlement/explain", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "1" in body["data"]["summary"]
    assert "Alice" in body["data"]["steps"][0]


def test_explain_settlement_with_language_en() -> None:
    payload = settlement_request_payload()
    payload["language"] = "en"

    response = client.post("/ai/settlement/explain", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "should pay" in body["data"]["steps"][0]


def test_explain_settlement_with_member_summaries() -> None:
    response = client.post(
        "/ai/settlement/explain",
        json=settlement_request_with_member_summaries(),
    )

    assert response.status_code == 200
    body = response.json()
    summary = body["data"]["summary"]
    assert body["success"] is True
    assert "Alice" in summary
    assert "paid the most upfront" in summary
    assert len(summary) > len("Settlement explanation generated successfully.")


def test_explain_settlement_empty_transactions_all_settled() -> None:
    payload = settlement_request_payload()
    payload["transactions"] = []

    response = client.post("/ai/settlement/explain", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["steps"] == []
    assert "No settlement transfers are needed" in body["data"]["summary"]


def test_parse_receipt_endpoint() -> None:
    response = client.post(
        "/ai/receipt/parse",
        json={"raw_text": "Mock receipt text"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_expense_insight_endpoint_returns_mock_data() -> None:
    response = client.post(
        "/ai/expenses/insight",
        json=expense_insight_request_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert "18" in body["data"]["summary"]
    assert "12,800 TWD" in body["data"]["summary"]
    assert "Hotel" in body["data"]["highlights"][0]
    assert "2026-05-05" in body["data"]["highlights"][1]
    assert "Alice" in body["data"]["highlights"][2]
    assert body["data"]["warnings"]
    assert "7,200 TWD" in body["data"]["suggestions"][0]
    assert body["data"]["fallback"] is False
    assert body["data"]["fallbackReason"] is None


def test_expense_insight_endpoint_returns_empty_context_template() -> None:
    response = client.post(
        "/ai/expenses/insight",
        json={
            "trip_id": "trip_123",
            "language": "en",
            "currency": "TWD",
            "totalAmount": 0,
            "expenseCount": 0,
            "memberCount": 0,
            "dailyTotals": [],
            "topExpenses": [],
            "memberBalances": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"] == "There are no expenses to analyze yet."
    assert body["data"]["highlights"] == []
    assert body["data"]["warnings"] == []
    assert "Add a few expenses" in body["data"]["suggestions"][0]
    assert body["data"]["fallback"] is False

def test_expense_insight_request_defaults_blank_language() -> None:
    request = ExpenseInsightRequest(
        trip_id="trip_123",
        language="  ",
    )

    assert request.language == "zh-TW"
    assert request.budget_amount is None
    assert request.remaining_days is None


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
        return SettlementExplanation(summary="Too slow", steps=[], tips=[])

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


@pytest.fixture(autouse=True)
def reset_settings_override() -> Callable[[], None]:
    app.dependency_overrides[get_settings] = lambda: Settings(ai_provider="mock")
    yield
    app.dependency_overrides[get_settings] = lambda: Settings(ai_provider="mock")


@pytest.mark.asyncio
async def test_generate_itinerary_timeout_returns_fallback() -> None:
    service = AIService(SlowProvider(), Settings(llm_timeout_seconds=0))
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    result = await service.generate_itinerary(request)

    assert result.fallback is True
    assert result.fallback_reason == "timeout"
    assert result.quality_checks is not None
    assert result.quality_checks.needs_user_review is True
    assert result.items[0].note == "AI provider timeout or failed. This is a safe fallback draft."
    assert "temporarily unavailable" in result.explanation


@pytest.mark.asyncio
async def test_generate_itinerary_provider_exception_returns_fallback() -> None:
    service = AIService(BrokenProvider(), Settings(llm_timeout_seconds=1))
    request = ItineraryGenerateRequest(**itinerary_request_payload())

    result = await service.generate_itinerary(request)

    assert result.fallback is True
    assert result.fallback_reason == "provider_error"
    assert result.quality_checks is not None
    assert result.quality_checks.needs_user_review is True
    assert result.items[0].title == "Tokyo fallback draft"
    assert "does not write to DB" in result.explanation


def test_explain_settlement_timeout_returns_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.providers.mock_provider import MockAIProvider

    async def slow_explain(
        self: MockAIProvider, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        await asyncio.sleep(0.01)
        return SettlementExplanation(summary="Too slow", steps=[], tips=[])

    monkeypatch.setattr(MockAIProvider, "explain_settlement", slow_explain)
    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="mock",
        llm_timeout_seconds=0,
    )

    response = client.post("/ai/settlement/explain", json=settlement_request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"] == "AI explanation temporarily unavailable"
    assert body["data"]["steps"] == ["Please refer to backend settlement result"]
    assert body["data"]["tips"] == ["AI service failed or timed out"]


def test_explain_settlement_exception_returns_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.providers.mock_provider import MockAIProvider

    async def broken_explain(
        self: MockAIProvider, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        raise Exception("provider failed")

    monkeypatch.setattr(MockAIProvider, "explain_settlement", broken_explain)

    response = client.post("/ai/settlement/explain", json=settlement_request_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"] == "AI explanation temporarily unavailable"
    assert body["data"]["steps"] == ["Please refer to backend settlement result"]
    assert body["data"]["tips"] == ["AI service failed or timed out"]


def test_explain_settlement_timeout_fallback_zh_tw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.providers.mock_provider import MockAIProvider

    async def slow_explain(
        self: MockAIProvider, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        await asyncio.sleep(0.01)
        return SettlementExplanation(summary="Too slow", steps=[], tips=[])

    monkeypatch.setattr(MockAIProvider, "explain_settlement", slow_explain)
    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="mock",
        llm_timeout_seconds=0,
    )
    payload = settlement_request_payload()
    payload["language"] = "zh-TW"

    response = client.post("/ai/settlement/explain", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"].startswith("AI ")
    assert body["data"]["steps"]
    assert body["data"]["tips"]


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
        (ProviderInvalidJSONError("invalid json"), "invalid_json"),
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
    assert "quality_checks" in prompt
    assert "has_out_of_scope_place" in prompt
    assert "has_unrealistic_transport" in prompt
    assert "has_time_conflict" in prompt
    assert "has_duplicate_place" in prompt
    assert "needs_user_review" in prompt
    assert "Tokyo" in prompt
    assert "2026-05-01" in prompt
    assert "2026-05-02" in prompt
    assert "unreasonable places" in prompt
    assert "geographically incompatible" in prompt
    assert "warnings" in prompt
    assert "Do not force impossible places" in prompt
    assert "unrealistic transportation" in prompt
    assert "check whether requested places are compatible with destination" in prompt
    assert "outside the destination area" in prompt
    assert "over-packed schedules" in prompt
    assert "warnings and explanation must not contain internal field names" in prompt


def test_settlement_prompt_builder_contains_json_only_contract() -> None:
    request = SettlementExplainRequest(**settlement_request_payload())

    prompt = build_settlement_prompt(request)

    assert "travel settlement explanation" in prompt
    assert "must not recalculate any balance or amount" in prompt
    assert "must not modify any amount" in prompt
    assert "must not add any transaction" in prompt
    assert "Return JSON only" in prompt
    assert "Do not include markdown" in prompt
    assert '"summary"' in prompt
    assert '"steps"' in prompt
    assert '"tips"' in prompt
    assert '"trip_id": "trip_123"' in prompt


def test_settlement_prompt_contains_language_instruction() -> None:
    payload = settlement_request_payload()
    payload["language"] = "zh-TW"
    request = SettlementExplainRequest(**payload)

    prompt = build_settlement_prompt(request)

    assert "Respond entirely in zh-TW" in prompt
    assert "Traditional Chinese" in prompt


def test_settlement_prompt_contains_member_summaries() -> None:
    request = SettlementExplainRequest(**settlement_request_with_member_summaries())

    prompt = build_settlement_prompt(request)

    assert "member_summaries" in prompt
    assert "paid_total" in prompt
    assert "owed_total" in prompt
    assert "net_balance" in prompt


def test_settlement_prompt_still_forbids_recalculation() -> None:
    request = SettlementExplainRequest(**settlement_request_with_member_summaries())

    prompt = build_settlement_prompt(request)

    assert "must not recalculate" in prompt
    assert "must not" in prompt
    assert "derive" in prompt
    assert "Do not use total_expense" in prompt


def test_itinerary_prompt_builder_contains_existing_context_terms() -> None:
    payload = itinerary_request_payload()
    payload["existing_itinerary"] = [
        {
            "day_date": "2026-05-01",
            "title": "Ueno Park",
            "location_name": "Ueno Park",
            "note": "Already arranged for day one.",
        }
    ]
    payload["avoid_duplicate_places"] = True
    request = ItineraryGenerateRequest(**payload)

    prompt = build_itinerary_generate_prompt(request)

    assert "Existing itinerary:" in prompt
    assert "avoid_duplicate_places: True" in prompt
    assert "Avoid recommending places or activities already listed in existing_itinerary" in prompt
    assert "must_visit_place already exists" in prompt
    assert "Ueno Park" in prompt
    assert "Already arranged for day one." in prompt
    assert "user-friendly warnings" in prompt
    assert "Do not mention internal field names" in prompt
    assert "avoid_duplicate_places" in prompt
    assert "existing_itinerary" in prompt
