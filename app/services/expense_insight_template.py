from app.schemas.ai import ExpenseInsightData, ExpenseInsightRequest


def build_expense_insight_template(
    request: ExpenseInsightRequest,
    fallback: bool = False,
    fallback_reason: str | None = None,
) -> ExpenseInsightData:
    language = request.language or "zh-TW"
    is_zh = language.startswith("zh")
    currency = request.currency or "TWD"
    total_amount = request.total_amount or 0
    expense_count = request.expense_count or 0

    if expense_count == 0:
        if is_zh:
            return ExpenseInsightData(
                summary="目前還沒有可分析的花費資料。",
                highlights=[],
                warnings=[],
                suggestions=["新增幾筆支出後，再回來查看花費趨勢。"],
                fallback=fallback,
                fallbackReason=fallback_reason,
            )

        return ExpenseInsightData(
            summary="There are no expenses to analyze yet.",
            highlights=[],
            warnings=[],
            suggestions=["Add a few expenses, then check the spending trend again."],
            fallback=fallback,
            fallbackReason=fallback_reason,
        )

    highlights: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []

    if is_zh:
        summary = (
            f"目前共記錄 {expense_count} 筆花費，總額 {total_amount:,.0f} {currency}，"
            f"涵蓋 {request.member_count} 位成員。"
        )
        _append_zh_insight(request, currency, total_amount, highlights, warnings, suggestions)
    else:
        summary = f"{expense_count} expenses total {total_amount:,.0f} {currency} across {request.member_count} members."
        _append_en_insight(request, currency, total_amount, highlights, warnings, suggestions)

    return ExpenseInsightData(
        summary=summary,
        highlights=highlights,
        warnings=warnings,
        suggestions=suggestions,
        fallback=fallback,
        fallbackReason=fallback_reason,
    )


def _append_zh_insight(
    request: ExpenseInsightRequest,
    currency: str,
    total_amount: float,
    highlights: list[str],
    warnings: list[str],
    suggestions: list[str],
) -> None:
    if request.top_expenses:
        top_expense = request.top_expenses[0]
        highlights.append(f"最大筆支出是 {top_expense.title}，金額 {top_expense.amount:,.0f} {currency}。")
        if total_amount > 0 and top_expense.amount / total_amount >= 0.4:
            share = top_expense.amount / total_amount
            warnings.append(f"{top_expense.title} 佔總花費約 {share:.0%}，建議確認這筆大額支出是否符合預期。")

    if request.daily_totals:
        peak_day = max(request.daily_totals, key=lambda item: item.amount)
        highlights.append(f"單日花費最高是 {peak_day.date.isoformat()}，共 {peak_day.amount:,.0f} {currency}。")

    positive_balances = [balance for balance in request.member_balances if balance.balance > 0]
    if positive_balances:
        payer = max(positive_balances, key=lambda balance: balance.balance)
        highlights.append(f"{payer.member_name} 目前墊付較多，淨額為 {payer.balance:,.0f} {currency}。")

    if request.budget_amount is not None:
        remaining_budget = request.budget_amount - total_amount
        if remaining_budget < 0:
            warnings.append(f"目前已超出預算 {abs(remaining_budget):,.0f} {currency}。")
        elif request.remaining_days and request.remaining_days > 0:
            daily_budget = remaining_budget / request.remaining_days
            suggestions.append(
                f"剩餘預算約 {remaining_budget:,.0f} {currency}，"
                f"接下來 {request.remaining_days} 天平均每日可用 {daily_budget:,.0f} {currency}。"
            )

    if not suggestions:
        suggestions.append("可優先檢查住宿、交通等大額項目，避免結算前才發現異常。")


def _append_en_insight(
    request: ExpenseInsightRequest,
    currency: str,
    total_amount: float,
    highlights: list[str],
    warnings: list[str],
    suggestions: list[str],
) -> None:
    if request.top_expenses:
        top_expense = request.top_expenses[0]
        highlights.append(f"The largest expense is {top_expense.title} at {top_expense.amount:,.0f} {currency}.")
        if total_amount > 0 and top_expense.amount / total_amount >= 0.4:
            share = top_expense.amount / total_amount
            warnings.append(f"{top_expense.title} is about {share:.0%} of total spending; review this large expense.")

    if request.daily_totals:
        peak_day = max(request.daily_totals, key=lambda item: item.amount)
        highlights.append(f"The highest daily spend is {peak_day.date.isoformat()} at {peak_day.amount:,.0f} {currency}.")

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
