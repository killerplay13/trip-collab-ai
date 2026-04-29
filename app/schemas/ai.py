from datetime import date, time
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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


class ItineraryGenerateData(BaseModel):
    items: list[ItineraryDraftItem]
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    source: str = "mock"
    fallback: bool = False
    fallback_reason: Optional[str] = None


class SettlementExplainRequest(BaseModel):
    trip_id: str
    expenses_summary: dict[str, Any]


class SettlementExplanation(BaseModel):
    summary: str
    details: list[str]


class ReceiptParseRequest(BaseModel):
    image_url: str | None = None
    raw_text: str | None = None


class ReceiptParseDraft(BaseModel):
    merchant: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float
