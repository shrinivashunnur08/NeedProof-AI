"""Chunk 13C.1: review *user-supplied* evidence with citations.

This is intentionally NOT a web crawler or an independently verified catalog.
It never fetches URLs or treats user-submitted quotations as authoritative facts.
13C.2 may later ingest an approved, traceable product-document corpus.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator
from app.algorithms.compatibility import CompatibilityInput, PowerProfile, evaluate_compatibility

FactKind = Literal["USB_PD_SUPPORT", "OUTPUT_PROFILE", "CABLE_CURRENT_RATING"]


class SourceFact(BaseModel):
    kind: FactKind
    quote: str = Field(min_length=5, max_length=400)
    # One of: "true"/"false", "20V/3250mA", or "3A"/"5A".
    value: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def value_must_match_quote(self):
        import re
        canonical = _canonical(self.kind, self.value)
        quote = self.quote.casefold()
        if self.kind == "USB_PD_SUPPORT":
            if not ("usb pd" in quote or "power delivery" in quote):
                raise ValueError("USB PD evidence quote must identify the standard")
            negated = bool(re.search(r"\b(not|no|unsupported|doesn't|does not)\b", quote))
            if canonical == negated:
                raise ValueError("USB PD claim does not agree with quoted excerpt")
        elif self.kind == "OUTPUT_PROFILE":
            volts, milliamps = canonical
            if not re.search(rf"\b{volts}\s*v\s*/\s*{milliamps}\s*ma\b", quote):
                raise ValueError("Output profile value is not found in the claim quote")
        elif self.kind == "CABLE_CURRENT_RATING":
            if not re.search(rf"\b{canonical}\s*a\b", quote) or "cable" not in quote:
                raise ValueError("Cable current rating must be stated in its quote")
        return self


class SuppliedDocument(BaseModel):
    source_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{2,32}$")
    title: str = Field(min_length=3, max_length=160)
    url: HttpUrl | None = None
    captured_at: datetime
    excerpt: str = Field(min_length=10, max_length=2000)
    facts: list[SourceFact] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def quote_is_present(self):
        text = " ".join(self.excerpt.casefold().split())
        for fact in self.facts:
            if " ".join(fact.quote.casefold().split()) not in text:
                raise ValueError("Every quoted claim must occur in its source excerpt")
        return self


class ReviewInput(BaseModel):
    product_label: str = Field(min_length=3, max_length=150)
    device_model: str = Field(min_length=2, max_length=120)
    device_supports_usb_pd: bool | None = None
    required_power_w: int = Field(ge=1, le=240)
    required_voltage_v: int = Field(ge=5, le=48)
    sources: list[SuppliedDocument] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def unique_sources(self):
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source identifiers")
        return self


def _canonical(kind: FactKind, value: str):
    import re
    value = value.strip().casefold()
    if kind == "USB_PD_SUPPORT":
        if value in {"true", "yes"}:
            return True
        if value in {"false", "no"}:
            return False
    if kind == "OUTPUT_PROFILE":
        m = re.fullmatch(r"(\d{1,2})v\s*/\s*(\d{3,4})ma", value)
        if m:
            voltage, current = map(int, m.groups())
            if 5 <= voltage <= 48 and 100 <= current <= 5000:
                return (voltage, current)
    if kind == "CABLE_CURRENT_RATING":
        if value in {"3a", "5a"}:
            return int(value[0])
    raise ValueError(f"Unsupported or invalid {kind} value")


def review_product(payload: ReviewInput) -> dict:
    """Evaluate cited, *unverified* input; fail closed on missing/conflicting facts."""
    observations: dict[str, list[dict]] = defaultdict(list)
    for source in payload.sources:
        for fact in source.facts:
            try:
                canonical = _canonical(fact.kind, fact.value)
            except ValueError as exc:
                # Pydantic validates input structure; a bad fact never becomes proof.
                raise ValueError(str(exc)) from exc
            observations[fact.kind].append({
                "value": canonical, "source_id": source.source_id, "title": source.title,
                "url": str(source.url) if source.url else None,
                "quote": fact.quote, "captured_at": source.captured_at.astimezone(timezone.utc).isoformat(),
            })

    issues = []
    references = []
    accepted = {}
    needed_current_ma = (payload.required_power_w * 1000 + payload.required_voltage_v - 1) // payload.required_voltage_v
    mandatory = {"USB_PD_SUPPORT", "OUTPUT_PROFILE"}
    if needed_current_ma > 3000:
        mandatory.add("CABLE_CURRENT_RATING")
    for kind in ("USB_PD_SUPPORT", "OUTPUT_PROFILE", "CABLE_CURRENT_RATING"):
        items = observations[kind]
        if not items:
            if kind in mandatory:
                issues.append({"kind": kind, "reason": "MISSING_SOURCE_FACT"})
            continue
        # Keep every quoted source visible even when sources disagree.
        for item in items:
            references.append({"kind": kind, "source_id": item["source_id"], "title": item["title"],
                               "url": item["url"], "quote": item["quote"], "captured_at": item["captured_at"]})
        variants = {repr(item["value"]) for item in items}
        conflicts = len(variants) > 1 if kind != "OUTPUT_PROFILE" else False
        if kind == "OUTPUT_PROFILE":
            # Multiple voltage profiles are normal. Conflicting currents for the SAME voltage need review.
            per_voltage = defaultdict(set)
            for item in items:
                voltage, current = item["value"]
                per_voltage[voltage].add(current)
            conflicts = any(len(currents) > 1 for currents in per_voltage.values())
        if conflicts:
            issues.append({"kind": kind, "reason": "CONTRADICTORY_SOURCE_FACTS"})
            continue
        accepted[kind] = [item["value"] for item in items]

    # A source excerpt is not independent verification. Even a conditional match is NOT a purchase approval.
    if not issues and "USB_PD_SUPPORT" in accepted and "OUTPUT_PROFILE" in accepted:
        compatibility = evaluate_compatibility(CompatibilityInput(
            device_model=payload.device_model,
            device_supports_usb_pd=payload.device_supports_usb_pd,
            device_required_power_w=payload.required_power_w,
            device_required_voltage_v=payload.required_voltage_v,
            charger_supports_usb_pd=accepted["USB_PD_SUPPORT"][0],
            charger_profiles=[PowerProfile(voltage_v=v, current_ma=c) for v, c in dict.fromkeys(accepted["OUTPUT_PROFILE"])],
            cable_current_rating_a=accepted.get("CABLE_CURRENT_RATING", [None])[0],
        ))
    else:
        compatibility = {
            "status": "INSUFFICIENT_SOURCE_EVIDENCE",
            "reasons": [f'{issue["kind"]}: {issue["reason"]}' for issue in issues],
            "recommended_next_action": "Obtain noncontradictory source excerpts for missing specification claims.",
            "purchase_allowed": False,
            "specification_source_verified": False,
        }

    return {
        "product_label": payload.product_label,
        "status": compatibility["status"],
        "source_count": len(payload.sources),
        "cited_facts": references,
        "evidence_gaps": issues,
        "compatibility": compatibility,
        "provenance": "USER_SUPPLIED_EXCERPTS_NOT_INDEPENDENTLY_VERIFIED",
        "purchase_allowed": False,
        "notice": "Quotes and URLs were provided by the user and have not been fetched or independently authenticated. Product, seller, stock and safety remain unverified.",
    }
