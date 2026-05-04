import json

from app.schemas.ai import SettlementExplainRequest


def build_settlement_prompt(request: SettlementExplainRequest) -> str:
    input_data = request.model_dump(by_alias=True)
    serialized_input = json.dumps(input_data, ensure_ascii=False, indent=2)

    return f"""You are generating a travel settlement explanation.

The backend has already completed all settlement calculations.
You must not recalculate any balance or amount.
You must not modify any amount.
You must not add any transaction.
You must not infer missing members, payments, or facts that are not present in the input.
You may only explain:
1. who pays whom
2. why this payment is needed
3. how to settle the trip

Return JSON only.
Do not include markdown.
Do not include any extra text.

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
- members, balances, and transactions above are the source of truth from backend.
"""
