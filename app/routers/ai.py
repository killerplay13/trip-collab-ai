from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.providers.base import AIProvider
from app.providers.mock_provider import MockAIProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.schemas.ai import (
    ExpenseInsightData,
    ExpenseInsightRequest,
    ItineraryGenerateData,
    ItineraryGenerateRequest,
    ReceiptParseDraft,
    ReceiptParseRequest,
    SettlementExplainRequest,
    SettlementExplanation,
)
from app.schemas.common import ApiResponse
from app.services.ai_service import AIService


router = APIRouter(prefix="/ai", tags=["ai"])


def get_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    provider = settings.ai_provider.lower()

    if provider == "mock":
        return MockAIProvider()
    if provider == "openrouter":
        return OpenRouterProvider(settings)

    raise HTTPException(status_code=500, detail=f"Unsupported AI provider: {settings.ai_provider}")


def get_ai_service(
    provider: AIProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings),
) -> AIService:
    return AIService(provider, settings)


@router.post(
    "/itinerary/generate",
    response_model=ApiResponse[ItineraryGenerateData],
)
async def generate_itinerary(
    request: ItineraryGenerateRequest,
    service: AIService = Depends(get_ai_service),
) -> ApiResponse[ItineraryGenerateData]:
    draft = await service.generate_itinerary(request)
    return ApiResponse(success=True, data=draft, error=None)


@router.post(
    "/settlement/explain",
    response_model=ApiResponse[SettlementExplanation],
)
async def explain_settlement(
    request: SettlementExplainRequest,
    service: AIService = Depends(get_ai_service),
) -> ApiResponse[SettlementExplanation]:
    explanation = await service.explain_settlement(request)
    return ApiResponse(success=True, data=explanation, error=None)


@router.post(
    "/expenses/insight",
    response_model=ApiResponse[ExpenseInsightData],
)
async def expense_insight(
    request: ExpenseInsightRequest,
) -> ApiResponse[ExpenseInsightData]:
    currency = request.currency or "TWD"
    total_amount = request.total_amount or 0
    expense_count = request.expense_count or 0

    if expense_count == 0:
        insight = ExpenseInsightData(
            summary="There are no expenses to analyze yet.",
            highlights=[],
            warnings=[],
            suggestions=["Add a few expenses, then check the spending trend again."],
            fallback=False,
            fallbackReason=None,
        )
        return ApiResponse(success=True, data=insight, error=None)

    highlights: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []

    summary = f"{expense_count} expenses total {total_amount:,.0f} {currency} across {request.member_count} members."

    if request.top_expenses:
        top_expense = request.top_expenses[0]
        highlights.append(f"The largest expense is {top_expense.title} at {top_expense.amount:,.0f} {currency}.")
        if total_amount > 0 and top_expense.amount / total_amount >= 0.4:
            share = top_expense.amount / total_amount
            warnings.append(
                f"{top_expense.title} is about {share:.0%} of total spending; review this large expense."
            )

    if request.daily_totals:
        peak_day = max(request.daily_totals, key=lambda item: item.amount)
        highlights.append(
            f"The highest daily spend is {peak_day.date.isoformat()} at {peak_day.amount:,.0f} {currency}."
        )

    positive_balances = [balance for balance in request.member_balances if balance.balance > 0]
    if positive_balances:
        payer = max(positive_balances, key=lambda balance: balance.balance)
        highlights.append(
            f"{payer.member_name} has paid more upfront, with a net balance of {payer.balance:,.0f} {currency}."
        )

    if request.budget_amount is not None:
        remaining_budget = request.budget_amount - total_amount
        if remaining_budget < 0:
            warnings.append(f"Current spending is {abs(remaining_budget):,.0f} {currency} over budget.")
        elif request.remaining_days and request.remaining_days > 0:
            daily_budget = remaining_budget / request.remaining_days
            suggestions.append(
                f"Remaining budget is about {remaining_budget:,.0f} {currency}; spend up to "
                f"{daily_budget:,.0f} {currency} per day for the next {request.remaining_days} days."
            )

    if not suggestions:
        suggestions.append("Review large lodging and transport items first to catch issues before settlement.")

    insight = ExpenseInsightData(
        summary=summary,
        highlights=highlights,
        warnings=warnings,
        suggestions=suggestions,
        fallback=False,
        fallbackReason=None,
    )
    return ApiResponse(success=True, data=insight, error=None)


@router.post(
    "/receipt/parse",
    response_model=ApiResponse[ReceiptParseDraft],
)
async def parse_receipt(
    request: ReceiptParseRequest,
    service: AIService = Depends(get_ai_service),
) -> ApiResponse[ReceiptParseDraft]:
    draft = await service.parse_receipt(request)
    return ApiResponse(success=True, data=draft, error=None)
