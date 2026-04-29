from app.providers.base import AIProvider
from app.schemas.ai import (
    ItineraryGenerateDraft,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)


class MockAIProvider(AIProvider):
    async def generate_itinerary(
        self, request: ItineraryGenerateRequest
    ) -> ItineraryGenerateDraft:
        preferences = ", ".join(request.preferences) if request.preferences else "general"

        return ItineraryGenerateDraft(
            title=f"Draft itinerary for {request.destination}",
            items=[
                {
                    "day": day,
                    "title": f"{request.destination} day {day}",
                    "activities": [
                        "Morning landmark visit",
                        "Local lunch",
                        "Afternoon free exploration",
                    ],
                    "note": "Draft only. Spring Boot must validate permissions and persist approved changes.",
                }
                for day in range(1, request.days + 1)
            ],
            explanation=(
                "This mock AI response only creates an itinerary draft and does not write to DB. "
                f"Trip {request.trip_id} preferences considered: {preferences}."
            ),
        )

    async def explain_settlement(
        self, request: SettlementExplainRequest
    ) -> SettlementExplanation:
        return SettlementExplanation(
            summary=(
                "Draft settlement explanation only. The AI service does not write to DB or apply transfers."
            ),
            details=[
                f"Trip {request.trip_id} expenses summary was received for explanation.",
                "Spring Boot remains responsible for permissions, business rules, and persistence.",
                "This mock result is safe to display as guidance before user confirmation.",
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
