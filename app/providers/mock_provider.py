from datetime import timedelta

from app.providers.base import AIProvider
from app.prompts.settlement_prompt import build_settlement_prompt
from app.schemas.ai import (
    ItineraryDraftItem,
    ItineraryGenerateData,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)


class MockAIProvider(AIProvider):
    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateData:
        interests = ", ".join(request.interests) if request.interests else "general"
        day_count = max((request.end_date - request.start_date).days + 1, 1)

        return ItineraryGenerateData(
            items=[
                ItineraryDraftItem(
                    day_date=request.start_date + timedelta(days=day_index),
                    title=f"{request.destination} day {day_index + 1}",
                    start_time=None,
                    end_time=None,
                    location_name=request.destination,
                    map_url=None,
                    note="Draft only. Spring Boot must validate permissions and persist approved changes.",
                    sort_order=1,
                )
                for day_index in range(day_count)
            ],
            explanation=(
                "This mock AI response only creates an itinerary draft and does not write to DB. "
                f"Trip {request.trip_title} interests considered: {interests}."
            ),
            warnings=[],
            source="mock",
            fallback=False,
            fallback_reason=None,
        )

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        _ = build_settlement_prompt(request)
        member_names = {member.member_id: member.name for member in request.members}
        steps = [
            (
                f"{member_names.get(transaction.from_, transaction.from_)} should pay "
                f"{member_names.get(transaction.to, transaction.to)} "
                f"{transaction.amount:g} {request.currency}."
            )
            for transaction in request.transactions
        ]

        return SettlementExplanation(
            summary="Settlement explanation generated successfully.",
            steps=steps,
            tips=[
                "Complete the listed payments to settle the trip balance.",
                "Amounts are based on backend settlement results.",
            ],
        )

    async def parse_receipt(self, request: ReceiptParseRequest) -> ReceiptParseDraft:
        source = "image_url" if request.image_url else "raw_text" if request.raw_text else "empty input"

        return ReceiptParseDraft(
            merchant="Mock Merchant",
            total_amount=123.45,
            currency="TWD",
            items=[
                {
                    "name": "Mock item",
                    "amount": 123.45,
                    "note": "Parsed draft only. Spring Boot decides whether and how to save it.",
                }
            ],
            confidence=0.8,
        )
