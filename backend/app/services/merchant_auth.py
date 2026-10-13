
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    MerchantAccount,
    MerchantLoginSession,
    utc_now,
)

password_hasher = PasswordHash.recommended()

SESSION_HOURS = 12

# A stable dummy hash helps reduce differences in
# processing time for existing vs nonexistent users.
DUMMY_PASSWORD_HASH = password_hasher.hash(
    "unused-dummy-password-for-auth-check"
)


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def authenticate(
    db: Session,
    email: str,
    password: str,
) -> MerchantAccount | None:
    account = db.scalar(
        select(MerchantAccount).where(
            MerchantAccount.email == normalize_email(email)
        )
    )

    stored_hash = (
        account.password_hash
        if account is not None
        else DUMMY_PASSWORD_HASH
    )

    valid = password_hasher.verify(
        password, stored_hash
    )

    return account if account and valid else None


def create_session(
    db: Session,
    account: MerchantAccount,
) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    expires_at = utc_now() + timedelta(
        hours=SESSION_HOURS
    )

    session = MerchantLoginSession(
        merchant_account_id=account.id,
        token_hash=hash_token(token),
        expires_at=expires_at,
    )

    db.add(session)
    db.commit()

    return token, expires_at


def get_account_for_token(
    db: Session,
    token: str,
) -> MerchantAccount | None:
    session = db.scalar(
        select(MerchantLoginSession).where(
            MerchantLoginSession.token_hash
            == hash_token(token)
        )
    )

    if session is None or session.revoked_at is not None:
        return None

    expires_at = session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at <= utc_now():
        return None

    return db.get(
        MerchantAccount,
        session.merchant_account_id,
    )
