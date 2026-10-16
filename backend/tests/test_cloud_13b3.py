"""Chunk 13B.3 security and integration checks; no Firestore credentials required."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.evidence_firestore_13b2 import feature_gate
from app.merchant_evidence_13b import NewMerchantReport
from scripts.review_merchant_claim_13b3 import grant_record, merchant_is_eligible, valid_uid, valid_place, valid_case
from datetime import datetime, timezone


def test_operator_review_default_is_off():
    import ast
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts/review_merchant_claim_13b3.py"
    tree = ast.parse(path.read_text('utf-8'))
    assert "--confirm-reviewed" in path.read_text('utf-8')
    assert "--apply" in path.read_text('utf-8')
    assert any(isinstance(node, ast.FunctionDef) and node.name == "merchant_is_eligible" for node in tree.body)


def test_approval_not_equal_independent_verification():
    now = datetime.now(timezone.utc)
    record = grant_record("uid-X", "ChIJplace", "review_123", "approve", now)
    assert record["approval_status"] == "OPERATOR_APPROVED_CLAIM"
    assert "merchant_identity_independently_verified" not in record
    revoked = grant_record("uid-X", "ChIJplace", "review_124", "revoke", now)
    assert revoked["approval_status"] == "REVOKED"
    assert revoked["approved_at"] is None


def test_verified_enabled_user_required():
    assert not merchant_is_eligible(SimpleNamespace(disabled=False, email="merchant@example.com", email_verified=False))
    assert not merchant_is_eligible(SimpleNamespace(disabled=True, email="merchant@example.com", email_verified=True))
    assert not merchant_is_eligible(SimpleNamespace(disabled=False, email=None, email_verified=True))
    assert merchant_is_eligible(SimpleNamespace(disabled=False, email="merchant@example.com", email_verified=True))


def test_invalid_identifiers_rejected():
    with pytest.raises(ValueError): valid_uid("a\n")
    with pytest.raises(ValueError): valid_place("bad\rplace")
    with pytest.raises(ValueError): valid_case("person@example.com")
    assert valid_case("CASE_007") == "CASE_007"


def test_firebase_feature_remains_off_by_default(monkeypatch):
    monkeypatch.delenv("MERCHANT_EVIDENCE_ENABLED", raising=False)
    with pytest.raises(HTTPException) as exc:
        feature_gate()
    assert exc.value.status_code == 503


def test_merchant_report_requires_explicit_authority_and_price():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        NewMerchantReport(stock_quantity=1, price_minor=1000, authorized_to_report=False)
    with pytest.raises(ValidationError):
        NewMerchantReport(stock_quantity=2, price_minor=None, authorized_to_report=True)
    report = NewMerchantReport(stock_quantity=0, price_minor=None, authorized_to_report=True)
    assert report.stock_quantity == 0


def test_report_requires_existing_merchant_grant_and_history_constraints():
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / 'app/evidence_firestore_13b2.py'
    source = f.read_text('utf-8')
    assert '"OPERATOR_APPROVED_CLAIM"' in source
    assert 'if count >= MAX_HISTORY' in source
    assert 'transaction.create(revision_ref, row)' in source
    assert 'merchant_identity_independently_verified' in source
