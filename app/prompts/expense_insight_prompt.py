import json
from typing import Any

from app.schemas.ai import ExpenseInsightRequest


def build_expense_insight_prompt(request: ExpenseInsightRequest) -> str:
    input_data = _expense_context(request)
    serialized_input = json.dumps(input_data, ensure_ascii=False, indent=2)
    language_instruction = (
        "Respond entirely in zh-TW. Use Traditional Chinese."
        if request.language.startswith("zh")
        else "Respond entirely in en. Use English."
    )

    return f"""{language_instruction}

You are a travel expense insight assistant for Trip-Collab.
Spring Boot context is the only source of truth.

Source-of-truth rules:
- Spring Boot context is the only source of truth.
- Do not recalculate totalAmount, dailyTotals, or memberBalances.
- Do not modify currency, amount, or date values.
- Do not invent expenses or members.
- Do not infer missing payments, members, dates, categories, or budgets.
- Do not verify or correct backend totals.
- AI only explains, summarizes, highlights risks, and gives suggestions.
- If data is limited, say the insight is based on limited data.

Output rules:
- Return JSON only.
- Do not include markdown.
- Do not include extra text.
- Do not return fallback or fallbackReason.
- JSON keys only: summary, highlights, warnings, suggestions.

Return exactly this JSON shape:
{{
  "summary": "...",
  "highlights": ["..."],
  "warnings": ["..."],
  "suggestions": ["..."]
}}

Input expense context:
{serialized_input}

Field meanings:
- totalAmount is the backend-provided total trip expense amount.
- dailyTotals are backend-provided totals grouped by expense date.
- topExpenses are backend-provided largest expenses.
- memberBalances are backend-provided paid/share/balance values.
- budgetAmount and remainingDays are user-provided planning context when present.
""".strip()


def _expense_context(request: ExpenseInsightRequest) -> dict[str, Any]:
    return {
        "trip_id": request.trip_id,
        "language": request.language,
        "currency": request.currency,
        "totalAmount": request.total_amount,
        "expenseCount": request.expense_count,
        "memberCount": request.member_count,
        "dailyTotals": [
            {
                "date": item.date.isoformat(),
                "amount": item.amount,
            }
            for item in request.daily_totals
        ],
        "topExpenses": [
            {
                "title": item.title,
                "amount": item.amount,
                "date": item.date.isoformat() if item.date else None,
            }
            for item in request.top_expenses
        ],
        "memberBalances": [
            {
                "memberName": item.member_name,
                "paidAmount": item.paid_amount,
                "shareAmount": item.share_amount,
                "balance": item.balance,
            }
            for item in request.member_balances
        ],
        "budgetAmount": request.budget_amount,
        "remainingDays": request.remaining_days,
    }
