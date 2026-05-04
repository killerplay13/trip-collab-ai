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
        prompt = build_settlement_prompt(request)
        _ = prompt
        is_zh = request.language.startswith("zh")
        member_names = {member.member_id: member.name for member in request.members}

        if not request.transactions:
            if is_zh:
                return SettlementExplanation(
                    summary="本次旅程目前沒有需要轉帳的結算項目。",
                    steps=[],
                    tips=[
                        "帳目已結清，暫時不需要進行轉帳。",
                        "若之後新增費用，請重新產生結算說明。",
                    ],
                )
            return SettlementExplanation(
                summary="No settlement transfers are needed for this trip.",
                steps=[],
                tips=[
                    "All expenses are currently squared up.",
                    "If new expenses are added, generate the explanation again.",
                ],
            )

        steps = [
            (
                f"{member_names.get(transaction.from_, transaction.from_)} 需支付 "
                f"{member_names.get(transaction.to, transaction.to)} "
                f"{transaction.amount:g} {request.currency}。"
                if is_zh
                else (
                    f"{member_names.get(transaction.from_, transaction.from_)} should pay "
                    f"{member_names.get(transaction.to, transaction.to)} "
                    f"{transaction.amount:g} {request.currency}."
                )
            )
            for transaction in request.transactions
        ]
        member_count = request.member_count if request.member_count is not None else len(request.members)
        transaction_count = (
            request.transaction_count
            if request.transaction_count is not None
            else len(request.transactions)
        )

        if request.member_summaries:
            top_payer = max(request.member_summaries, key=lambda summary: summary.paid_total)
            if is_zh:
                summary = (
                    f"本次旅程共 {member_count} 位成員，結算後需完成 "
                    f"{transaction_count} 筆轉帳。{top_payer.name} 是主要代墊者，"
                    f"實付 {top_payer.paid_total:g} {request.currency}，"
                    f"應分攤 {top_payer.owed_total:g} {request.currency}。"
                )
            else:
                summary = (
                    f"This trip has {member_count} member(s). "
                    f"{transaction_count} transfer(s) are needed to settle the balance. "
                    f"{top_payer.name} paid the most upfront: "
                    f"{top_payer.paid_total:g} {request.currency}, while their owed share is "
                    f"{top_payer.owed_total:g} {request.currency}."
                )
        elif is_zh:
            summary = f"本次旅程結算後需完成 {transaction_count} 筆轉帳。"
        else:
            summary = f"This trip needs {transaction_count} transfer(s) to settle the balance."

        tips = (
            [
                "完成以上轉帳後，本次旅程帳目即可結清。",
                "金額依後端結算結果為準，AI 僅提供說明。",
            ]
            if is_zh
            else [
                "Complete the listed payments to settle the trip balance.",
                "Amounts are based on backend settlement results. AI only explains them.",
            ]
        )

        return SettlementExplanation(
            summary=summary,
            steps=steps,
            tips=tips,
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
