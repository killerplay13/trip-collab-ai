from typing import Any

from pydantic import BaseModel, Field


class ItineraryGenerateRequest(BaseModel):
    trip_id: str
    destination: str
    days: int = Field(ge=1, le=30)
    preferences: list[str] = Field(default_factory=list)


class ItineraryGenerateDraft(BaseModel):
    title: str
    items: list[dict[str, Any]]
    explanation: str


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
