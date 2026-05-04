import json
from collections.abc import Callable

import httpx
import pytest

from app.config import Settings
from app.providers import openrouter_provider
from app.providers.exceptions import (
    MissingProviderConfigError,
    ProviderHTTPError,
    ProviderInvalidJSONError,
    ProviderInvalidResponseError,
    ProviderQuotaExceededError,
    ProviderRateLimitError,
)
from app.providers.openrouter_provider import OpenRouterProvider
from app.schemas.ai import ItineraryGenerateRequest, SettlementExplainRequest


def itinerary_request() -> ItineraryGenerateRequest:
    return ItineraryGenerateRequest(
        trip_title="Tokyo spring trip",
        destination="Tokyo",
        start_date="2026-05-01",
        end_date="2026-05-02",
        timezone="Asia/Tokyo",
        travelers_count=2,
        interests=["food", "museum"],
        language="en",
    )


def openrouter_settings(api_key: str = "test-key") -> Settings:
    return Settings(
        ai_provider="openrouter",
        openrouter_api_key=api_key,
        openrouter_model="test-model",
        openrouter_base_url="https://openrouter.test",
    )


def settlement_request() -> SettlementExplainRequest:
    return SettlementExplainRequest(
        trip_id="trip_123",
        currency="TWD",
        members=[
            {"member_id": "alice", "name": "Alice"},
            {"member_id": "bob", "name": "Bob"},
        ],
        balances=[
            {"member_id": "alice", "net_balance": -300.0},
            {"member_id": "bob", "net_balance": 300.0},
        ],
        transactions=[
            {"from": "alice", "to": "bob", "amount": 300.0},
        ],
    )


def valid_content() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "day_date": "2026-05-01",
                    "title": "Tokyo food walk",
                    "start_time": "09:00:00",
                    "end_time": None,
                    "location_name": "Tokyo",
                    "map_url": None,
                    "note": "Start with local breakfast.",
                    "sort_order": 1,
                }
            ],
            "explanation": "A short Tokyo itinerary.",
            "warnings": [],
        }
    )


def valid_settlement_content() -> str:
    return json.dumps(
        {
            "summary": "Alice needs to pay Bob to settle the trip.",
            "steps": ["Alice should pay Bob 300 TWD."],
            "tips": ["Amounts are based on backend settlement results."],
        }
    )


def install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[httpx.Request]:
    requests: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: _record_and_handle(request, requests, handler))
    real_async_client = httpx.AsyncClient

    class MockAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.client = real_async_client(transport=transport)

        async def __aenter__(self) -> httpx.AsyncClient:
            return self.client

        async def __aexit__(self, *args: object) -> None:
            await self.client.aclose()

    monkeypatch.setattr(openrouter_provider.httpx, "AsyncClient", MockAsyncClient)
    return requests


def _record_and_handle(
    request: httpx.Request,
    requests: list[httpx.Request],
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.Response:
    requests.append(request)
    return handler(request)


@pytest.mark.asyncio
async def test_generate_itinerary_parses_valid_response_and_sends_expected_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": valid_content()}}]},
        )

    requests = install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    result = await provider.generate_itinerary(itinerary_request())

    assert result.source == "openrouter"
    assert result.fallback is False
    assert result.fallback_reason is None
    assert result.items[0].title == "Tokyo food walk"

    request = requests[0]
    assert str(request.url).endswith("/chat/completions")
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["Content-Type"] == "application/json"

    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert body["temperature"] == 0.4
    assert body["messages"][0] == {
        "role": "system",
        "content": "你是旅遊行程規劃 AI，只能輸出 JSON",
    }
    assert body["messages"][1]["role"] == "user"
    assert "Tokyo" in body["messages"][1]["content"]


@pytest.mark.asyncio
async def test_generate_itinerary_invalid_json_raises_provider_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
        )

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderInvalidResponseError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_generate_itinerary_schema_invalid_raises_provider_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        invalid_content = json.dumps({"items": [], "warnings": []})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": invalid_content}}]},
        )

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderInvalidResponseError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_generate_itinerary_empty_choices_raises_provider_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderInvalidResponseError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_generate_itinerary_empty_content_raises_provider_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "   "}}]},
        )

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderInvalidResponseError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_generate_itinerary_rate_limit_raises_provider_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderRateLimitError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_generate_itinerary_quota_response_raises_provider_quota_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": "insufficient credits"})

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderQuotaExceededError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_generate_itinerary_http_500_raises_provider_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "provider failed"})

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderHTTPError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_generate_itinerary_missing_api_key_raises_missing_config() -> None:
    provider = OpenRouterProvider(openrouter_settings(api_key="   "))

    with pytest.raises(MissingProviderConfigError):
        await provider.generate_itinerary(itinerary_request())


@pytest.mark.asyncio
async def test_explain_settlement_parses_valid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": valid_settlement_content()}}]},
        )

    requests = install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    result = await provider.explain_settlement(settlement_request())

    assert result.summary == "Alice needs to pay Bob to settle the trip."
    assert result.steps == ["Alice should pay Bob 300 TWD."]
    assert result.tips == ["Amounts are based on backend settlement results."]

    request = requests[0]
    body = json.loads(request.content)
    assert body["messages"][1]["role"] == "user"
    assert "travel settlement explanation" in body["messages"][1]["content"]
    assert '"summary"' in body["messages"][1]["content"]
    assert '"transactions"' in body["messages"][1]["content"]


@pytest.mark.asyncio
async def test_explain_settlement_invalid_json_raises_provider_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
        )

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderInvalidJSONError):
        await provider.explain_settlement(settlement_request())


@pytest.mark.asyncio
async def test_explain_settlement_schema_invalid_raises_provider_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        invalid_content = json.dumps({"summary": "ok", "steps": []})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": invalid_content}}]},
        )

    install_mock_transport(monkeypatch, handler)
    provider = OpenRouterProvider(openrouter_settings())

    with pytest.raises(ProviderInvalidResponseError):
        await provider.explain_settlement(settlement_request())
