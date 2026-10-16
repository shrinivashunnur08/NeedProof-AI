"""Chunk 13B.2: Google Cloud Firestore evidence persistence.

Uses the existing free-tier Firestore (default) in needproof-ai-showcase.
Disabled by default; only the authenticated Cloud Run API writes data.
Business listings NEVER establish stock or product availability.
Merchant grants require independent operator review (13B.3 workflow).
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from app.db.models import utc_now
from app.merchant_evidence_13b import NewInquiry, NewMerchantReport, _decision, require_customer, require_merchant

router = APIRouter(prefix="/api/v1/evidence", tags=["Merchant Evidence (Firestore)"])

PROJECT = "needproof-ai-showcase"
COL = "np_evidence_inquiries_13b"
GRANTS = "np_merchant_grants_13b"
USAGE = "np_evidence_usage_13b"
DEDUP = "np_evidence_dedup_13b"
MAX_DAILY = 10
MAX_HISTORY = 30


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1e".join(parts).encode("utf-8")).hexdigest()


def feature_gate() -> None:
    if os.getenv("MERCHANT_EVIDENCE_ENABLED", "false").lower().strip() != "true":
        raise HTTPException(503, "Merchant evidence tracking is disabled")
    if os.getenv("MERCHANT_EVIDENCE_STORAGE", "").lower().strip() != "firestore":
        raise HTTPException(503, "Firestore evidence storage is not selected")
    if os.getenv("MERCHANT_EVIDENCE_FIRESTORE_PROJECT", "").strip() != PROJECT:
        raise HTTPException(503, "Expected evidence Firestore project is not configured")
    # A backend must authenticate users with exactly the same Firebase project.
    if os.getenv("FIREBASE_PROJECT_ID", "").strip() != PROJECT:
        raise HTTPException(503, "Firebase Auth and evidence Firestore project must match")


@lru_cache(maxsize=1)
def _client():
    from google.cloud import firestore
    return firestore.Client(project=PROJECT, database="(default)")


def _store_error(exc: Exception) -> HTTPException:
    logging.warning("Evidence Firestore unavailable (%s)", type(exc).__name__)
    return HTTPException(503, "Evidence persistence is temporarily unavailable")


def _serialize(row_id: str, row: dict) -> dict:
    return {
        "revision_id": row_id,
        "stock_quantity": row["stock_quantity"], "price_minor": row.get("price_minor"),
        "currency": "INR", "specification_notes": row.get("specification_notes"),
        "delivery_available": row.get("delivery_available"),
        "recorded_at": _utc(row["recorded_at"]).isoformat(),
        "source": "MERCHANT_REPORTED_UNVERIFIED",
        "merchant_identity_independently_verified": False,
    }


def _detail(db, record_id: str, row: dict) -> dict:
    try:
        raw = list(db.collection(COL).document(record_id).collection("revisions")
                   .order_by("recorded_at", direction="DESCENDING").limit(MAX_HISTORY).stream())
    except Exception as exc:
        raise _store_error(exc) from exc
    revisions = [_serialize(s.id, s.to_dict()) for s in raw]
    current = raw[0].to_dict() if raw else None
    current_obj = SimpleNamespace(**current) if current else None
    if current_obj is not None:
        current_obj.recorded_at = _utc(current_obj.recorded_at)
    inquiry = SimpleNamespace(place_id=row["place_id"], product_query=row["product_query"], budget_minor=row.get("budget_minor"))
    return {
        "inquiry_id": record_id, "place_id": row["place_id"], "product_query": row["product_query"],
        "status": "REPORTED_UNVERIFIED" if current else ("EXPIRED" if _utc(row["expires_at"]) <= utc_now() else "AWAITING_MERCHANT"),
        "merchant_contacted": False,
        "created_at": _utc(row["created_at"]).isoformat(), "expires_at": _utc(row["expires_at"]).isoformat(),
        "current_report": revisions[0] if revisions else None,
        "history": revisions,
        "replanning": _decision(inquiry, current_obj),
        "notice": "An inquiry does not contact a merchant. Reports are merchant-submitted and unverified; no purchase is authorized.",
    }


def _fetch(db, inquiry_id: str):
    try:
        UUID(inquiry_id)
    except (ValueError, TypeError):
        raise HTTPException(404, "Inquiry not found")
    try:
        doc = db.collection(COL).document(inquiry_id).get()
        if not doc.exists:
            raise HTTPException(404, "Inquiry not found")
        return doc.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        raise _store_error(exc) from exc


@router.post("/inquiries", status_code=201, dependencies=[Depends(feature_gate)])
def create_inquiry(payload: NewInquiry, response: Response, uid: str = Depends(require_customer)):
    response.headers["Cache-Control"] = "no-store"
    db = _client()
    from google.cloud import firestore
    now = utc_now()
    identifier = str(uuid4())
    doc_ref = db.collection(COL).document(identifier)
    dedup_ref = db.collection(DEDUP).document(_hash(uid, payload.place_id, payload.product_query.casefold()))
    usage_ref = db.collection(USAGE).document(_hash(uid, now.strftime("%Y-%m-%d")))
    row = {
        "requester_uid": uid, "place_id": payload.place_id,
        "product_query": payload.product_query, "budget_minor": payload.budget_minor,
        "created_at": now, "expires_at": now + timedelta(days=7), "revision_count": 0,
    }
    try:
        tx = db.transaction()

        @firestore.transactional
        def write(transaction):
            # Reads must precede writes inside Firestore transactions.
            old = dedup_ref.get(transaction=transaction)
            usage = usage_ref.get(transaction=transaction)
            prior = old.to_dict() if old.exists else None
            if prior and _utc(prior["created_at"]) > now - timedelta(minutes=10):
                return str(prior["inquiry_id"]), True
            count = int((usage.to_dict() or {}).get("count", 0)) if usage.exists else 0
            if count >= MAX_DAILY:
                raise HTTPException(429, "Daily evidence inquiry limit reached")
            transaction.create(doc_ref, row)
            transaction.set(dedup_ref, {"inquiry_id": identifier, "created_at": now})
            transaction.set(usage_ref, {"count": count + 1, "day": now.strftime("%Y-%m-%d")})
            return identifier, False

        found_id, was_existing = write(tx)
        if was_existing:
            response.status_code = 200
            return _detail(db, found_id, _fetch(db, found_id))
        return _detail(db, identifier, row)
    except HTTPException:
        raise
    except Exception as exc:
        raise _store_error(exc) from exc


@router.get("/inquiries/{inquiry_id}", dependencies=[Depends(feature_gate)])
def get_inquiry(inquiry_id: str, response: Response, uid: str = Depends(require_customer)):
    response.headers["Cache-Control"] = "no-store"
    db = _client()
    row = _fetch(db, inquiry_id)
    if row["requester_uid"] != uid:
        raise HTTPException(404, "Inquiry not found")
    return _detail(db, inquiry_id, row)


@router.get("/merchant/inquiries", dependencies=[Depends(feature_gate)])
def merchant_inquiries(response: Response, uid: str = Depends(require_merchant)):
    response.headers["Cache-Control"] = "no-store"
    db = _client()
    try:
        # Bounded reads; no requester UID ever included in response.
        claims = list(db.collection(GRANTS).where("merchant_uid", "==", uid).limit(15).stream())
        places = [s.to_dict()["place_id"] for s in claims if s.to_dict().get("approval_status") == "OPERATOR_APPROVED_CLAIM"][:5]
        now = utc_now()
        rows = []
        for place_id in places:
            matches = db.collection(COL).where("place_id", "==", place_id).limit(25).stream()
            for item in matches:
                row = item.to_dict()
                if _utc(row["expires_at"]) > now:
                    rows.append({"inquiry_id": item.id, "place_id": row["place_id"], "product_query": row["product_query"],
                                 "created_at": _utc(row["created_at"]).isoformat(), "expires_at": _utc(row["expires_at"]).isoformat()})
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return {"inquiries": rows[:25], "notice": "Inquiries are not confirmed customer orders."}
    except Exception as exc:
        raise _store_error(exc) from exc


@router.post("/merchant/inquiries/{inquiry_id}/reports", status_code=201, dependencies=[Depends(feature_gate)])
def report_evidence(inquiry_id: str, payload: NewMerchantReport, response: Response, uid: str = Depends(require_merchant)):
    response.headers["Cache-Control"] = "no-store"
    db = _client()
    from google.cloud import firestore
    try:
        UUID(inquiry_id)
    except (TypeError, ValueError):
        raise HTTPException(404, "Inquiry not found")
    inquiry_ref = db.collection(COL).document(inquiry_id)
    revision_id = str(uuid4())
    revision_ref = inquiry_ref.collection("revisions").document(revision_id)
    now = utc_now()
    row = {"merchant_uid": uid, "stock_quantity": payload.stock_quantity, "price_minor": payload.price_minor,
           "specification_notes": payload.specification_notes, "delivery_available": payload.delivery_available, "recorded_at": now}
    try:
        tx = db.transaction()

        @firestore.transactional
        def write(transaction):
            inquiry_doc = inquiry_ref.get(transaction=transaction)
            if not inquiry_doc.exists:
                raise HTTPException(404, "Inquiry not found")
            inquiry = inquiry_doc.to_dict()
            grant_ref = db.collection(GRANTS).document(_hash(uid, inquiry["place_id"]))
            grant_doc = grant_ref.get(transaction=transaction)
            if not grant_doc.exists or grant_doc.to_dict().get("approval_status") != "OPERATOR_APPROVED_CLAIM":
                raise HTTPException(404, "Inquiry not found")
            if _utc(inquiry["expires_at"]) <= now:
                raise HTTPException(410, "Inquiry has expired")
            count = int(inquiry.get("revision_count", 0))
            if count >= MAX_HISTORY:
                raise HTTPException(429, "Report history limit reached")
            transaction.create(revision_ref, row)
            transaction.update(inquiry_ref, {"revision_count": count + 1})

        write(tx)
        return _detail(db, inquiry_id, _fetch(db, inquiry_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise _store_error(exc) from exc
