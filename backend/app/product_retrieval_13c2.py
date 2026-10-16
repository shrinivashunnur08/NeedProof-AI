"""NeedProof 13C.2: bounded, deterministic retrieval over user-supplied excerpts.

NO network calls, crawling, URL trust, automatic purchasing, or external model calls.
Supplied sources remain unverified. Optional Gemini explanation is client initiated.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from math import log
import re
from pydantic import BaseModel, Field, model_validator

from app.product_grounding_13c1 import ReviewInput, SourceFact, SuppliedDocument, review_product

_WORDS = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_PD = re.compile(r"\b(?:USB\s+PD|power\s+delivery)\s+(?:is\s+)?(not\s+)?supported\b", re.IGNORECASE)
_PROFILE = re.compile(r"\b(?:output(?:\s+profile)?\s*[:\-]?\s*)?([5-9]|[1-4][0-9])\s*V\s*/\s*(\d{3,4})\s*mA\b", re.IGNORECASE)
_CABLE = re.compile(r"\bcable\b[^.\n]{0,50}?\b([35])\s*A\b", re.IGNORECASE)


class RetrievalInput(BaseModel):
    query: str = Field(min_length=5, max_length=180)
    review: ReviewInput

    @model_validator(mode="after")
    def has_sources(self):
        if not self.review.sources:
            raise ValueError("Provide at least one excerpt; retrieval is not an online search")
        return self


def _tokens(text: str) -> list[str]:
    return _WORDS.findall(text.casefold())


def _trigrams(text: str) -> set[str]:
    compact = " ".join(_tokens(text))
    return {compact[i:i+3] for i in range(max(len(compact) - 2, 0))}


def _passages(source: SuppliedDocument) -> list[dict]:
    text = source.excerpt
    # Split on sentence endings/newlines; cap individual passages without losing exact offsets.
    spans = []
    for m in re.finditer(r"[^\n.!?]+(?:[.!?]+|$)", text):
        a, b = m.span()
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b-1].isspace():
            b -= 1
        while a < b:
            end = min(a + 350, b)
            if end < b and " " in text[a:end]:
                end = text.rfind(" ", a, end) + 1
            quote = text[a:end].strip()
            if quote:
                position = text.find(quote, a, end + 5)
                spans.append({"source_id": source.source_id, "title": source.title,
                              "url": str(source.url) if source.url else None,
                              "quote": quote, "start": position, "end": position + len(quote),
                              "source_sha256": sha256(text.encode("utf-8")).hexdigest(),
                              "captured_at": source.captured_at.astimezone(timezone.utc).isoformat()})
            a = end
    return spans[:40]


def _extract_facts(source: SuppliedDocument) -> list[SourceFact]:
    # Recognize only explicit, narrow specification forms. No inferred facts or text generation.
    found: list[SourceFact] = list(source.facts)
    seen = {(f.kind, f.value.casefold(), f.quote.casefold()) for f in found}
    for kind, pattern in (("USB_PD_SUPPORT", _PD), ("OUTPUT_PROFILE", _PROFILE), ("CABLE_CURRENT_RATING", _CABLE)):
        for m in pattern.finditer(source.excerpt):
            if kind == "USB_PD_SUPPORT":
                value = "false" if m.group(1) else "true"
            elif kind == "OUTPUT_PROFILE":
                value = f"{int(m.group(1))}V/{int(m.group(2))}mA"
            else:
                value = f"{m.group(1)}A"
            quote = m.group(0).strip()
            signature = (kind, value.casefold(), quote.casefold())
            if signature in seen:
                continue
            try:
                f = SourceFact(kind=kind, quote=quote, value=value)
            except ValueError:
                continue
            found.append(f)
            seen.add(signature)
            if len(found) >= 12:
                return found[:12]
    return found


def retrieve_and_review(payload: RetrievalInput) -> dict:
    sources = payload.review.sources
    passages = [p for source in sources for p in _passages(source)]
    if not passages:
        raise ValueError("No retrievable text found in supplied excerpts")
    query = f"{payload.query} {payload.review.product_label} output voltage usb pd cable specification"
    terms = set(_tokens(query))
    grams = _trigrams(query)
    frequencies = [Counter(_tokens(p["quote"] + " " + p["title"])) for p in passages]
    document_freq = Counter(token for f in frequencies for token in f)
    lengths = [sum(f.values()) for f in frequencies]
    avg_len = max(sum(lengths) / len(lengths), 1)
    for i, p in enumerate(passages):
        freq = frequencies[i]
        score = 0.0
        for word in terms:
            n = document_freq.get(word, 0)
            if not n:
                continue
            idf = log(1 + (len(passages) - n + 0.5) / (n + 0.5))
            tf = freq[word]
            if tf:
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * lengths[i] / avg_len))
        piece_grams = _trigrams(p["quote"] + " " + p["title"])
        similarity = len(grams & piece_grams) / len(grams | piece_grams) if grams and piece_grams else 0
        p["retrieval_score"] = round(score + 1.5 * similarity, 5)
        p["citation_id"] = f'{p["source_id"]}:{p["start"]}'
    ranked = sorted(passages, key=lambda p: (-p["retrieval_score"], p["source_id"], p["start"]))[:6]

    enhanced_sources = [source.model_copy(update={"facts": _extract_facts(source)}) for source in sources]
    review = review_product(payload.review.model_copy(update={"sources": enhanced_sources}))
    now = datetime.now(timezone.utc)
    stale = [s.source_id for s in sources if (now - s.captured_at.astimezone(timezone.utc)).days > 180]
    return {
        "retrieval_method": "LOCAL_BM25_CHAR_TRIGRAM_NO_EMBEDDINGS",
        "passages": ranked,
        "review": review,
        "documents_supplied": len(sources),
        "stale_source_ids": stale,
        "sources_verified": False,
        "gemini_used": False,
        "purchase_allowed": False,
        "notice": "Retrieved text comes only from user-supplied, unverified excerpts. URLs were not fetched. AI-generated or quoted information is not merchant stock verification or purchase approval.",
    }
