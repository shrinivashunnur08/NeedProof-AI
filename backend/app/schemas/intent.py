
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class IntentRequest(BaseModel):
    text: str = Field(min_length=8, max_length=2000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 8:
            raise ValueError("Enter a meaningful shopping request.")

        return value


class ExtractedIntent(BaseModel):
    language: str = Field(
        min_length=2, max_length=80,
        description="Language of the original request."
    )

    product_category: str | None = None
    requested_product: str = Field(
        min_length=2, max_length=200,
        description="Product requested by the customer."
    )

    budget_amount: int | None = Field(default=None, ge=0)
    budget_currency: str | None = None

    delivery_deadline_text: str | None = None
    delivery_location: str | None = None

    required_specifications: list[str] = Field(
        default_factory=list, max_length=15
    )

    preferred_specifications: list[str] = Field(
        default_factory=list, max_length=15
    )

    missing_information: list[str] = Field(
        default_factory=list, max_length=15
    )

    clarification_questions: list[str] = Field(
        default_factory=list, max_length=8
    )

    compatibility_needs_verification: bool = True

    @field_validator("budget_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if len(value) != 3 or not value.isascii() or not value.isalpha():
            raise ValueError("Currency must be a three-letter ISO code")
        return value

    @field_validator("required_specifications", "preferred_specifications",
                     "missing_information", "clarification_questions")
    @classmethod
    def validate_items(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            value = value.strip()
            if not value or len(value) > 180:
                raise ValueError("List entries must be non-empty and at most 180 characters")
            if value not in result:
                result.append(value)
        return result


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


class IntentAnalysisResponse(BaseModel):
    source: Literal["vertex_ai"]
    model: str
    status: Literal["extracted_unverified"]
    intent: ExtractedIntent
    processing_ms: int
    usage: TokenUsage | None = None
