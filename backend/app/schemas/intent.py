
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
        description="Language of the original request."
    )

    product_category: str | None = None
    requested_product: str = Field(
        description="Product requested by the customer."
    )

    budget_amount: int | None = Field(default=None, ge=0)
    budget_currency: str | None = None

    delivery_deadline_text: str | None = None
    delivery_location: str | None = None

    required_specifications: list[str] = Field(
        default_factory=list
    )

    preferred_specifications: list[str] = Field(
        default_factory=list
    )

    missing_information: list[str] = Field(
        default_factory=list
    )

    clarification_questions: list[str] = Field(
        default_factory=list
    )

    compatibility_needs_verification: bool = True


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
