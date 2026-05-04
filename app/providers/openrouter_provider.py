import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.prompts.itinerary_prompt_builder import build_itinerary_generate_prompt
from app.prompts.settlement_prompt import build_settlement_prompt
from app.providers.base import AIProvider
from app.providers.exceptions import (
    MissingProviderConfigError,
    ProviderHTTPError,
    ProviderInvalidJSONError,
    ProviderInvalidResponseError,
    ProviderQuotaExceededError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.schemas.ai import (
    ItineraryGenerateData,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)


class OpenRouterProvider(AIProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateData:
        if not self.settings.openrouter_api_key.strip():
            raise MissingProviderConfigError("OpenRouter API key is required.")

        prompt = build_itinerary_generate_prompt(request)
        response = await self._post_chat_completion(prompt)
        content = self._extract_content(response)
        payload = self._parse_json_content(content)

        payload["source"] = "openrouter"
        payload["fallback"] = False
        payload["fallback_reason"] = None

        try:
            return ItineraryGenerateData.model_validate(payload)
        except ValidationError as exc:
            raise ProviderInvalidResponseError(
                "OpenRouter response does not match itinerary schema."
            ) from exc

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        if not self.settings.openrouter_api_key.strip():
            raise MissingProviderConfigError("OpenRouter API key is required.")

        prompt = build_settlement_prompt(request)
        response = await self._post_chat_completion(prompt)
        content = self._extract_content(response)
        payload = self._parse_json_content(content)

        try:
            return SettlementExplanation.model_validate(payload)
        except ValidationError as exc:
            raise ProviderInvalidResponseError(
                "OpenRouter response does not match settlement explanation schema."
            ) from exc

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        # Phase 1 will implement the real OpenRouter call with timeout handling,
        # rate limit handling, quota exceeded handling, invalid JSON recovery,
        # and fallback behavior.
        raise NotImplementedError("OpenRouterProvider is planned for Phase 1.")

    async def _post_chat_completion(self, prompt: str) -> dict[str, Any]:
        url = f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a travel assistant AI. "
                        "Follow the user prompt exactly and output JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise ProviderUnavailableError("OpenRouter request failed.") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise self._provider_http_error(exc) from exc

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderInvalidResponseError(
                "OpenRouter returned a non-JSON API response."
            ) from exc

        if not isinstance(data, dict):
            raise ProviderInvalidResponseError("OpenRouter API response must be a JSON object.")

        return data

    def _extract_content(self, response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not choices:
            raise ProviderInvalidResponseError("OpenRouter response choices are empty.")

        if not isinstance(choices, list) or not isinstance(choices[0], dict):
            raise ProviderInvalidResponseError("OpenRouter response choices are invalid.")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderInvalidResponseError("OpenRouter response message is invalid.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderInvalidResponseError("OpenRouter response content is empty.")

        return content

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderInvalidJSONError("OpenRouter returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise ProviderInvalidResponseError("OpenRouter content payload must be a JSON object.")

        return payload

    def _provider_http_error(self, exc: httpx.HTTPStatusError) -> Exception:
        status_code = exc.response.status_code
        response_text = exc.response.text.lower()

        if status_code == 429:
            return ProviderRateLimitError("OpenRouter rate limit exceeded.")
        if status_code in {402, 403} or self._looks_like_quota_error(response_text):
            return ProviderQuotaExceededError("OpenRouter quota or credits exceeded.")

        return ProviderHTTPError(f"OpenRouter HTTP error: {status_code}.")

    def _looks_like_quota_error(self, response_text: str) -> bool:
        quota_terms = ("quota", "credit", "credits", "insufficient", "payment")
        return any(term in response_text for term in quota_terms)
