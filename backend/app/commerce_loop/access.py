"""Role-based access for the commerce loop.

Roles: shopper, shopkeeper (bound to one shop), business (area/brand manager), admin (operator/jury).
The browser sends X-NeedProof-Role and X-NeedProof-Shop; the server checks every write and every
shop-private read against them. Enforcement is on when LOOP_ENFORCE_ROLES=true (the deployed app).

Honest scope: these headers are a demo identity chosen from the role dropdown, not authentication.
Production would put Firebase Authentication / Identity Platform in front and derive role and shop from
the verified token; the checks below stay the same.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.commerce_loop.providers import setting

ROLES = {"shopper", "shopkeeper", "business", "admin"}


@dataclass(frozen=True)
class Identity:
    role: str
    shop_id: str | None


def enforced() -> bool:
    return setting("LOOP_ENFORCE_ROLES", "false").lower() == "true"


def identity(request: Request) -> Identity:
    role = (request.headers.get("x-needproof-role") or "").strip().lower()
    shop = (request.headers.get("x-needproof-shop") or "").strip() or None
    if role not in ROLES:
        role = "shopper" if enforced() else "admin"
    return Identity(role, shop)


def require(request: Request, *roles: str, shop_id: str | None = None) -> Identity:
    """Allow admin always; a shopkeeper only for their own shop when shop_id is given."""
    who = identity(request)
    if not enforced() or who.role == "admin":
        return who
    if who.role not in roles:
        raise HTTPException(status_code=403, detail=f"The {who.role} role cannot do this. Switch role in the header.")
    if who.role == "shopkeeper" and shop_id is not None and who.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Shopkeepers can only act for their own shop.")
    return who
