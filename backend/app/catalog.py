"""Formula catalogs (MEDISCA, CompoundingToday) for fast lookup of preparation names.

A catalog lists which formulas a source has (number, title, link), not their
contents. Importing one parses each title into request fields (ingredient,
strength, dosage form, quantity) so picking a catalog formula fills the new
request form without a search or an AI call. The parsing is best effort: the
user reviews the fields before creating the request.
"""

import csv
import io
import re
from dataclasses import dataclass

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import CatalogEntry
from app.services import RuleViolation

# "200 000" and "5,000" are one number; so are "0.5" and "2,5".
_NUM = r"(?:\d{1,3}(?:[ ,]\d{3})+(?![\d.,])(?:\.\d+)?|\d+(?:[.,]\d+)?)"
_UNITS = r"(?:%|mg|mcg|µg|ug|g|grams?|kg|ml|l|units?|iu|kiu|miu|meq|mmol|ppm)"
_UNIT = rf"{_UNITS}(?![a-z])"
_PER = r"(?:ml|g|grams?|mg|l|capsules?|tablets?|doses?|sprays?|actuations?|drops?|units?)(?![a-z])"
STRENGTH = re.compile(
    rf"{_NUM}(?:\s*-\s*{_NUM})?\s*{_UNIT}(?:\s*\((?:w/w|w/v|v/v)\))?(?:\s*(?:/|\bper\b)\s*(?:{_NUM}\s*)?{_PER})?",
    re.I,
)
# CompoundingToday writes "10-mg/mL"; only a hyphen between a number and a unit is a space.
_NUM_UNIT_HYPHEN = re.compile(rf"(?<=\d)-(?={_UNITS}(?![a-z]))", re.I)
_TRAILING_PAREN = re.compile(r"\(([^()]*)\)\s*$")
_BRACKET = re.compile(r"\s*\[[^\]]*\]\s*$")
# Dosage-form words looked for in free-text titles (CompoundingToday), most specific first.
_FORMS = [
    "suspension", "solution", "syrup", "emulsion", "cream", "ointment", "gel", "lotion", "paste", "foam",
    "capsules", "capsule", "tablets", "tablet", "troches", "troche", "lozenges", "lozenge", "suppositories",
    "suppository", "injection", "spray", "drops", "shampoo", "stick", "films", "film", "powder", "toothgel",
    "mouthwash", "rinse", "enema", "lip balm", "serum", "pessary",
]
_ROUTES = ["oral", "topical", "transdermal", "rectal", "vaginal", "ophthalmic", "otic", "nasal", "sublingual",
           "buccal", "dental", "parenteral", "intravitreal", "inhalation"]
_LIQUID_KINDS = {"solution", "suspension", "emulsion", "syrup", "elixir"}
SOURCES = ("MEDISCA", "CompoundingToday")
MEDISCA_URL = "https://www.medisca.com/formulas/library?q={}"


def normalize(text: str) -> str:
    """Lower-case, drop ™/®, and write CompoundingToday's "10-mg/mL" as "10 mg/ml"."""
    return _display(re.sub(r"[™®©]", "", text)).lower()


def _search_words(text: str) -> str:
    """Stored and queried form: normalized words, brackets and commas as spaces, with
    a leading space so " word" matches only at the start of a word."""
    return " " + re.sub(r"\s+", " ", re.sub(r"[()\[\],;]", " ", normalize(text))).strip()


def _display(text: str) -> str:
    return re.sub(r"\s+", " ", _NUM_UNIT_HYPHEN.sub(" ", text)).strip()


def _ingredients_and_strengths(text: str) -> tuple[str, str, int]:
    """"Ketoconazole 2%, Minoxidil 7%" -> ("Ketoconazole, Minoxidil", "2%, 7%", end of last strength)."""
    names, strengths, pos = [], [], 0
    for m in STRENGTH.finditer(text):
        name = re.sub(r"^(?:[,;.&+/]|and\b)\s*", "", text[pos:m.start()].strip(), flags=re.I).strip(" ,;.")
        if re.search(r"[A-Za-z]", name):
            names.append(name)
        strengths.append(m.group(0).strip())
        pos = m.end()
    return ", ".join(names), ", ".join(strengths), pos


@dataclass
class Parsed:
    active_ingredient: str = ""
    strength: str = ""
    dosage_form: str = ""
    final_quantity: str = ""


def parse_medisca(title: str, route: str, form: str) -> Parsed:
    """"Levetiracetam 300 mg/5 mL Oral Liquid (Solution, 100 mL)" with route "Oral", form "Liquid"."""
    out = Parsed()
    head, kind = title, ""
    paren = _TRAILING_PAREN.search(title)
    if paren:
        head = title[:paren.start()].strip()
        parts = [p.strip() for p in paren.group(1).split(",")]
        quantities = [p for p in parts if re.search(r"\d", p)]
        out.final_quantity = quantities[-1] if quantities else ""
        kind = next((p for p in parts if p and not re.search(r"\d", p)), "")
    cut = len(head)
    for word in (route, form):
        if word:
            idx = head.lower().rfind(" " + word.lower())
            if idx > 0:
                cut = min(cut, idx)
    api = head[:cut]
    out.active_ingredient, out.strength, _ = _ingredients_and_strengths(api)
    if not out.active_ingredient:
        out.active_ingredient = api.strip(" ,")
    # "Liquid (Suspension, ...)" -> "suspension"; other notes such as "(MAZ)" are not a form.
    shape = kind if form.lower() == "liquid" and kind.lower() in _LIQUID_KINDS else form
    out.dosage_form = " ".join(x for x in (route, shape.lower()) if x).strip()
    return out


def parse_compounding_today(title: str) -> Parsed:
    """"Baclofen 10-mg/mL in Ora-Plus™ and Ora-Sweet™ [Paddock Perrigo]" and similar free text."""
    out = Parsed()
    text = _display(_BRACKET.sub("", title))
    out.active_ingredient, out.strength, end = _ingredients_and_strengths(text)
    if not out.active_ingredient:
        out.active_ingredient = re.split(r",\s*(?:preserved|preservative-free|human|veterinary)\b", text, flags=re.I)[0]
    low = normalize(text)
    # The product's form is usually the last form word ("Coal Tar Solution ... Lotion").
    found = [(m.start(), f) for f in _FORMS for m in re.finditer(rf"\b{f}\b", low)]
    form = max(found)[1] if found else ""
    route = next((r for r in _ROUTES if re.search(rf"\b{r}\b", low)), "")
    out.dosage_form = f"{route.title()} {form}" if route and form else (form.title() or route.title())
    return out


def _rows(data: bytes) -> tuple[str, list[dict]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuleViolation("The catalog file must be UTF-8 CSV.") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])
    if {"Formula Number", "API(s) & Strength"} <= headers:
        source = "MEDISCA"
    elif {"CompoundingToday ID", "Formula title"} <= headers:
        source = "CompoundingToday"
    else:
        raise RuleViolation("Unrecognised catalog: expected the MEDISCA or CompoundingToday CSV export.")
    return source, list(reader)


def import_csv(db: Session, data: bytes) -> dict:
    """Replace the whole catalog of the file's source. Requests keep their own copy
    of the catalog formula they were created from, so re-importing is safe."""
    source, rows = _rows(data)
    entries, seen = [], set()
    now = utcnow()
    for r in rows:
        if source == "MEDISCA":
            fid, title = (r.get("Formula Number") or "").strip(), (r.get("API(s) & Strength") or "").strip()
            route, form = (r.get("Route of Delivery") or "").strip(), (r.get("Dosage Form") or "").strip()
            base = (r.get("Base") or "").strip()
            # MEDISCA has no page per formula; its library filtered to the number is the closest.
            url = MEDISCA_URL.format(fid) if re.fullmatch(r"[A-Z]\d{6}", fid) else ""
            parsed = parse_medisca(title, route, form)
        else:
            fid, title = (r.get("CompoundingToday ID") or "").strip(), (r.get("Formula title") or "").strip()
            route, form, base = "", "", ""
            url = (r.get("Catalog URL") or "").strip()
            if url and not url.startswith("https://compoundingtoday.com/"):
                url = ""
            parsed = parse_compounding_today(title)
        if not title or (fid, title) in seen:
            continue
        seen.add((fid, title))
        entries.append(CatalogEntry(
            source=source, source_formula_id=fid[:64], title=title[:1000], route=route[:100], base=base[:500],
            url=url[:2000], active_ingredient=parsed.active_ingredient[:1000], strength=parsed.strength[:500],
            dosage_form=parsed.dosage_form[:200], final_quantity=parsed.final_quantity[:200],
            search_text=_search_words(" ".join((title, fid, route, form, base))), imported_at=now,
        ))
    if not entries:
        raise RuleViolation("The catalog file has no formulas.")
    db.execute(delete(CatalogEntry).where(CatalogEntry.source == source))
    db.add_all(entries)
    db.flush()
    return {"source": source, "count": len(entries)}


def search(db: Session, q: str, *, source: str | None = None, limit: int = 12) -> list[CatalogEntry]:
    """Every query word must start a word of the entry ("diaz 5" finds "Diazepam 5 mg/mL");
    titles starting with the first word come first, then shorter titles."""
    words = _search_words(q).split()[:6]
    if not words:
        return []
    stmt = select(CatalogEntry)
    for w in words:
        stmt = stmt.where(CatalogEntry.search_text.contains(" " + w, autoescape=True))
    if source:
        stmt = stmt.where(CatalogEntry.source == source)
    starts = case((CatalogEntry.search_text.startswith(" " + words[0], autoescape=True), 0), else_=1)
    return list(db.scalars(stmt.order_by(starts, func.length(CatalogEntry.title), CatalogEntry.id).limit(limit)))


def summary(db: Session) -> list[dict]:
    rows = db.execute(
        select(CatalogEntry.source, func.count(), func.max(CatalogEntry.imported_at)).group_by(CatalogEntry.source)
    ).all()
    found = {s: (n, at) for s, n, at in rows}
    return [{"source": s, "count": found.get(s, (0, None))[0],
             "imported_at": found[s][1].isoformat() if s in found and found[s][1] else None} for s in SOURCES]
