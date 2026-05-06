from datetime import date, time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExistingItineraryItem(BaseModel):
    day_date: date
    title: str
    location_name: Optional[str] = None
    note: Optional[str] = None


class ItineraryGenerateRequest(BaseModel):
    trip_title: str
    destination: str
    start_date: date
    end_date: date
    timezone: str = "Asia/Taipei"
    travelers_count: int = Field(default=1, ge=1, le=50)
    travel_style: Optional[str] = None
    budget_level: Optional[str] = None
    interests: list[str] = Field(default_factory=list)
    must_visit_places: list[str] = Field(default_factory=list)
    avoid_places: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    language: str = "zh-TW"
    existing_itinerary: list[ExistingItineraryItem] = Field(default_factory=list)
    avoid_duplicate_places: bool = True

    @field_validator("trip_title", "destination", "timezone", "language")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_date_range(self) -> "ItineraryGenerateRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


class ItineraryDraftItem(BaseModel):
    day_date: date
    title: str
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location_name: Optional[str] = None
    map_url: Optional[str] = None
    note: Optional[str] = None
    sort_order: int = Field(ge=1)


class ItineraryQualityChecks(BaseModel):
    has_out_of_scope_place: bool = False
    has_unrealistic_transport: bool = False
    has_time_conflict: bool = False
    has_duplicate_place: bool = False
    needs_user_review: bool = False


class ItineraryGenerateData(BaseModel):
    items: list[ItineraryDraftItem]
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    source: str = "mock"
    fallback: bool = False
    fallback_reason: Optional[str] = None
    quality_checks: Optional[ItineraryQualityChecks] = None


class SettlementMember(BaseModel):
    member_id: str
    name: str


class SettlementBalance(BaseModel):
    member_id: str
    net_balance: float


class SettlementTransaction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    amount: float


class SettlementMemberSummary(BaseModel):
    member_id: str
    name: str
    paid_total: float
    owed_total: float
    net_balance: float


class SettlementExplainRequest(BaseModel):
    trip_id: str
    currency: str
    members: list[SettlementMember]
    balances: list[SettlementBalance]
    transactions: list[SettlementTransaction]
    language: str = Field(default="en")
    total_expense: float | None = Field(default=None)
    member_count: int | None = Field(default=None)
    transaction_count: int | None = Field(default=None)
    member_summaries: list[SettlementMemberSummary] = Field(default_factory=list)

    @field_validator("language", mode="before")
    @classmethod
    def default_blank_language(cls, value: object) -> str:
        if value is None:
            return "en"
        if isinstance(value, str) and not value.strip():
            return "en"
        return str(value)


class SettlementExplanation(BaseModel):
    summary: str
    steps: list[str]
    tips: list[str]


class ExpenseInsightRequest(BaseModel):
    trip_id: str
    language: str = "zh-TW"
    budget_amount: float | None = None
    remaining_days: int | None = None

    @field_validator("language", mode="before")
    @classmethod
    def default_blank_language(cls, value: object) -> str:
        if value is None:
            return "zh-TW"
        if isinstance(value, str) and not value.strip():
            return "zh-TW"
        return str(value)


class ExpenseInsightData(BaseModel):
    summary: str
    highlights: list[str]
    warnings: list[str]
    suggestions: list[str]
    fallback: bool = False
    fallbackReason: str | None = None


class ReceiptParseRequest(BaseModel):
    image_url: str | None = None
    raw_text: str | None = None


class ReceiptParseDraft(BaseModel):
    merchant: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float
