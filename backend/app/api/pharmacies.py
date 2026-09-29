"""A pharmacist's pharmacies (branches): name, address, phone and logo for the
master formula PDF header. An admin sets how many each pharmacist may have."""

from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app import audit
from app.api.deps import DB, CurrentUser, Pharmacist
from app.api.schemas import PharmacyIn
from app.models import Pharmacy
from app.services import RuleViolation
from app.storage import LOGO_TYPES, MAX_LOGO_BYTES, InvalidFile, logo_path, store_logo

router = APIRouter(prefix="/api/pharmacies", tags=["pharmacies"])


def view(p: Pharmacy) -> dict[str, Any]:
    return {"id": p.id, "name": p.name, "address": p.address, "phone": p.phone,
            "has_logo": bool(p.logo_sha256), "logo_version": (p.logo_sha256 or "")[:12]}


def snapshot(p: Pharmacy) -> dict[str, Any]:
    """What an approval records about the pharmacy (kept even if the pharmacy changes later)."""
    return {"id": p.id, "name": p.name, "address": p.address, "phone": p.phone,
            "logo_sha256": p.logo_sha256, "logo_type": p.logo_type}


def for_pdf(snap: dict[str, Any] | None) -> dict[str, Any] | None:
    if not snap:
        return None
    path = logo_path(snap["logo_sha256"], snap["logo_type"]) if snap.get("logo_sha256") else None
    return {**snap, "logo_path": path}


def _own(db, user, pharmacy_id: str) -> Pharmacy:
    p = db.get(Pharmacy, pharmacy_id)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Pharmacy not found")
    return p


def mine(db, user) -> list[Pharmacy]:
    return list(db.scalars(select(Pharmacy).where(Pharmacy.owner_id == user.id).order_by(Pharmacy.created_at)))


@router.get("")
def list_pharmacies(user: CurrentUser, db: DB):
    return {"items": [view(p) for p in mine(db, user)], "max": user.max_pharmacies if user.role == "pharmacist" else 0}


@router.post("", status_code=201)
def create_pharmacy(body: PharmacyIn, user: Pharmacist, db: DB):
    count = db.scalar(select(func.count()).select_from(Pharmacy).where(Pharmacy.owner_id == user.id))
    if count >= user.max_pharmacies:
        raise RuleViolation(f"You can have up to {user.max_pharmacies} pharmacies. Ask the administrator for more.")
    p = Pharmacy(owner_id=user.id, name=body.name.strip(), address=body.address.strip(), phone=body.phone.strip())
    db.add(p)
    db.flush()
    audit.record(db, user.id, "pharmacy_created", "pharmacy", p.id)
    db.commit()
    return view(p)


@router.patch("/{pharmacy_id}")
def update_pharmacy(pharmacy_id: str, body: PharmacyIn, user: Pharmacist, db: DB):
    p = _own(db, user, pharmacy_id)
    p.name, p.address, p.phone = body.name.strip(), body.address.strip(), body.phone.strip()
    audit.record(db, user.id, "pharmacy_updated", "pharmacy", p.id)
    db.commit()
    return view(p)


@router.delete("/{pharmacy_id}")
def delete_pharmacy(pharmacy_id: str, user: Pharmacist, db: DB):
    p = _own(db, user, pharmacy_id)
    db.delete(p)  # approved PDFs keep their own copy of the pharmacy details
    audit.record(db, user.id, "pharmacy_deleted", "pharmacy", pharmacy_id)
    db.commit()
    return {"ok": True}


@router.post("/{pharmacy_id}/logo")
async def upload_logo(pharmacy_id: str, user: Pharmacist, db: DB, file: Annotated[UploadFile, File()]):
    p = _own(db, user, pharmacy_id)
    try:
        p.logo_sha256, p.logo_type = store_logo(await file.read(MAX_LOGO_BYTES + 1))
    except InvalidFile as exc:
        raise RuleViolation(str(exc)) from exc
    audit.record(db, user.id, "pharmacy_logo_changed", "pharmacy", p.id)
    db.commit()
    return view(p)


@router.delete("/{pharmacy_id}/logo")
def remove_logo(pharmacy_id: str, user: Pharmacist, db: DB):
    p = _own(db, user, pharmacy_id)
    p.logo_sha256 = p.logo_type = None
    db.commit()
    return view(p)


@router.get("/{pharmacy_id}/logo")
def get_logo(pharmacy_id: str, _: CurrentUser, db: DB):
    p = db.get(Pharmacy, pharmacy_id)
    if p is None or not p.logo_sha256:
        raise HTTPException(404, "No logo")
    return FileResponse(logo_path(p.logo_sha256, p.logo_type), media_type=LOGO_TYPES[p.logo_type],
                        headers={"Cache-Control": "private, max-age=86400"})
