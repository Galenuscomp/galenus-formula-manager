from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile

from app import audit, catalog
from app.api.deps import DB, Admin, CurrentUser
from app.models import CatalogEntry
from app.services import RuleViolation

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

MAX_CATALOG_BYTES = 20 * 1024 * 1024


def _entry(e: CatalogEntry) -> dict:
    return {
        "id": e.id,
        "source": e.source,
        "formula_id": e.source_formula_id,
        "title": e.title,
        "url": e.url,
        "route": e.route,
        "base": e.base,
        "active_ingredient": e.active_ingredient,
        "strength": e.strength,
        "dosage_form": e.dosage_form,
        "final_quantity": e.final_quantity,
    }


@router.get("/search")
def search_catalog(
    _: CurrentUser,
    db: DB,
    q: Annotated[str, Query(max_length=200)] = "",
    source: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
):
    if len(q.strip()) < 2:
        return []
    return [_entry(e) for e in catalog.search(db, q, source=source, limit=limit)]


@router.get("/summary")
def catalog_summary(_: Admin, db: DB):
    return catalog.summary(db)


@router.post("/import")
async def import_catalog(actor: Admin, db: DB, file: Annotated[UploadFile, File()]):
    data = await file.read(MAX_CATALOG_BYTES + 1)
    if len(data) > MAX_CATALOG_BYTES:
        raise RuleViolation("The catalog file is larger than 20 MB.")
    result = catalog.import_csv(db, data)
    audit.record(db, actor.id, "catalog_imported", "catalog", result["source"], count=result["count"])
    db.commit()
    return result
