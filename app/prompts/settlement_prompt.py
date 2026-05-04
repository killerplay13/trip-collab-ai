import json

from app.schemas.ai import SettlementExplainRequest


def build_settlement_prompt(request: SettlementExplainRequest) -> str:
    input_data = request.model_dump(by_alias=True)
    serialized_input = json.dumps(input_data, ensure_ascii=False, indent=2)
    member_summary_instruction = (
        "If member_summaries is present and non-empty, prioritize it when explaining "
        "paid_total, owed_total, and net_balance differences."
        if request.member_summaries
        else "If member_summaries is empty, use members, balances, and transactions for a basic explanation only."
    )

    return f"""Respond entirely in {request.language}. All text in summary, steps, and tips must be in {request.language}. If the language is zh-TW, use Traditional Chinese.

You are a travel expense settlement explainer.
This is a travel settlement explanation task.

Backend source of truth:
- The backend has already calculated all amounts.
- The AI must not recalculate any balance or amount.
- The AI must not re-derive settlement amounts.
- The AI must not infer a new amount.
- The AI must not modify any amount.
- The AI must not modify transactions.
- The AI must not add any transaction.
- The AI must not add transactions.
- The AI must not infer missing members, payments, or facts that are not present in the input.
- Do not use total_expense or member_summaries to verify or derive new settlement amounts.

Field meanings:
- paid_total = actual amount this member paid.
- owed_total = amount this member should share.
- net_balance = paid_total - owed_total.
- positive net_balance means others owe this member.
- negative net_balance means this member owes others.

Explanation task:
1. who pays whom
2. why this payment is needed
3. how the listed transactions settle the trip
4. if member_summaries exists, explain paid_total / owed_total / net_balance differences
5. if transactions is empty, explain that no transfers are needed and the trip is already settled
6. explain total_expense and transaction_count as context only, without recalculating them

{member_summary_instruction}

Output JSON only.
Return JSON only.
No markdown.
Do not include markdown.
No extra text.
Do not include any extra text.
JSON keys only: summary, steps, tips.

The JSON schema is fixed as:
{{
  "summary": "...",
  "steps": ["..."],
  "tips": ["..."]
}}

Input data:
{serialized_input}

Reminder:
- trip_id: {request.trip_id}
- currency: {request.currency}
- language: {request.language}
- total_expense, member_count, transaction_count, members, balances, transactions, and member_summaries above are backend-provided source data.
- transactions are the settlement source of truth; explain them without changing them.
"""
