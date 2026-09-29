"""Server-side master formula PDF.

Approved PDFs are generated once at approval, stored content-addressed and their
SHA-256 recorded on the approval decision. Draft previews carry a watermark.
"""

import io
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from bidi import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Decision, Draft, SearchRequest, SourceDocument

_FONT_DIRS = [Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu")]
FONT, FONT_BOLD = "Helvetica", "Helvetica-Bold"
for _d in _FONT_DIRS:
    if (_d / "DejaVuSans.ttf").exists():
        pdfmetrics.registerFont(TTFont("DejaVu", str(_d / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_d / "DejaVuSans-Bold.ttf")))
        FONT, FONT_BOLD = "DejaVu", "DejaVu-Bold"
        break

TEAL = colors.HexColor("#0d9488")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
BORDER = colors.HexColor("#e2e8f0")

_RTL = re.compile(r"[֐-׿؀-ۿ]")
_LTR = re.compile(r"[A-Za-zÀ-ɏ]")
_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")

_base = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=_base["BodyText"], fontName=FONT, fontSize=9.5, leading=13, textColor=SLATE)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
H1 = ParagraphStyle("h1", parent=BODY, fontName=FONT_BOLD, fontSize=16, leading=20, textColor=colors.black)
H2 = ParagraphStyle(
    "h2", parent=BODY, fontName=FONT_BOLD, fontSize=11, leading=14, textColor=TEAL, spaceBefore=10, spaceAfter=4
)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName=FONT_BOLD)
CELL_PAD = 12  # table cell left + right padding
_rtl_styles: dict[str, ParagraphStyle] = {}


def _rtl(style: ParagraphStyle) -> ParagraphStyle:
    if style.name not in _rtl_styles:
        _rtl_styles[style.name] = ParagraphStyle(f"{style.name}-rtl", parent=style, alignment=TA_RIGHT)
    return _rtl_styles[style.name]


def _directions(text: str) -> list[str | None]:
    """Strong direction of each character for bracket resolution (UAX #9): letters are L or R,
    digits follow the preceding letter (W7: numbers after Latin text are L), the rest None."""
    out: list[str | None] = []
    last = None
    for ch in text:
        if _RTL.match(ch):
            last = "R"
            out.append("R")
        elif _LTR.match(ch):
            last = "L"
            out.append("L")
        elif ch.isdigit():
            out.append("L" if last == "L" else "R")
        else:
            out.append(None)
    return out


def _base_direction(text: str) -> str:
    """Like dir="auto": the first letter decides the line's direction."""
    for ch in text:
        if _RTL.match(ch):
            return "R"
        if _LTR.match(ch):
            return "L"
    return "R"


def _mirror_brackets(text: str, base: str = "R") -> str:
    """python-bidi reorders but does not mirror, so "(BUD)" would print as ")BUD(". Resolve each
    bracket pair's direction as UAX #9 rule N0 does, and swap the right-to-left ones before
    reordering so they come out facing the right way."""
    dirs = _directions(text)
    chars = list(text)
    stack: list[int] = []
    for i, ch in enumerate(chars):
        if ch in _OPEN:
            stack.append(i)
        elif ch in _CLOSE and stack and _OPEN.index(chars[stack[-1]]) == _CLOSE.index(ch):
            start = stack.pop()
            inside = {d for d in dirs[start + 1:i] if d}
            before = next((d for d in reversed(dirs[:start]) if d), base)
            if base in inside:
                direction = base
            elif inside:  # only the opposite direction inside: it wins if the text before agrees
                direction = before if before != base else base
            else:  # empty or neutral content: like neighbouring text (N1), else the base (N2)
                after = next((d for d in dirs[i + 1:] if d), base)
                direction = before if before == after else base
            if direction == "R":
                chars[start] = chars[start].translate(_MIRROR)
                chars[i] = chars[i].translate(_MIRROR)
            if direction != base:
                # A direction mark after the closing bracket keeps it with its pair when reordering
                # ("(USP <795>)" in a Hebrew line); the marks are removed after reordering.
                chars[i] += _MARK[direction]
    return "".join(chars)


_OPEN, _CLOSE = "([{<", ")]}>"
_MARK = {"L": "‎", "R": "‏"}


def _visual(line: str, base: str) -> str:
    return get_display(line, base_dir=base).replace("‎", "").replace("‏", "")


def _wrap(text: str, width: float, font: str, size: float) -> list[str]:
    """Break a logical-order line to the width. Wrapping must happen before bidi reordering,
    otherwise a long Hebrew paragraph prints its lines bottom-up."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}" if cur else word
        if cur and stringWidth(trial, font, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    return lines


def para(text: Any, style: ParagraphStyle = BODY, width: float | None = None) -> Paragraph:
    """A paragraph; text with Hebrew is right-aligned and wrapped to `width` before reordering."""
    lines = str(text or "").strip().splitlines() or [""]
    if not any(_RTL.search(line) for line in lines):
        return Paragraph("<br/>".join(escape(line) for line in lines) or "&nbsp;", style)
    out = []
    for line in lines:
        if not _RTL.search(line):
            out.append(escape(line))
            continue
        base = _base_direction(line)
        mirrored = _mirror_brackets(line, base)
        wrapped = _wrap(mirrored, width * 0.96, style.fontName, style.fontSize) if width else [mirrored]
        out += [escape(_visual(w, base)) for w in wrapped]
    return Paragraph("<br/>".join(out) or "&nbsp;", _rtl(style))


def _table(rows: list[list[Any]], widths: list[float], header: bool = True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")))
    t.setStyle(TableStyle(style))
    return t


LABELS = {
    "en": {
        "active_ingredient": "Active ingredient", "strength": "Strength", "dosage_form": "Dosage form",
        "final_quantity": "Final quantity", "active_ingredients": "Active ingredients", "quantity": "Quantity",
        "included": "Included", "yes": "Yes", "no": "No", "not_specified": "Not specified",
        "ingredients": "Composition", "preparation_method": "Preparation method", "equipment": "Equipment",
        "packaging": "Packaging", "storage_conditions": "Storage conditions", "bud": "Beyond-use date (BUD)",
        "labelling_instructions": "Labelling instructions", "warnings": "Warnings and precautions",
        "references": "References", "local_adaptation_notes": "Local adaptation notes",
        "source_documents": "Source documents", "source": "Source", "reference": "Reference",
        "title_file": "Title / file", "approval_record": "Approval record",
        "prepared_by": "Prepared / submitted by", "approved_by": "Approved by", "licence": "licence",
        "approval_date": "Approval date (UTC)", "approval_notes": "Approval notes",
        "content_hash": "Approved content SHA-256",
        "subtitle": "Master formula {number} · version {version} · status: {status} · request {request}",
        "disclaimer": "This record identifies the logged-in user who approved the formula. It is not a qualified "
                      "electronic signature.",
    },
    "he": {
        "active_ingredient": "חומר פעיל", "strength": "חוזק", "dosage_form": "צורת מינון",
        "final_quantity": "כמות סופית", "active_ingredients": "חומרים פעילים", "quantity": "כמות",
        "included": "כלול", "yes": "כן", "no": "לא", "not_specified": "לא צוין",
        "ingredients": "הרכב", "preparation_method": "שיטת הכנה", "equipment": "ציוד",
        "packaging": "אריזה", "storage_conditions": "תנאי אחסון", "bud": "תאריך שימוש אחרון (BUD)",
        "labelling_instructions": "הוראות סימון", "warnings": "אזהרות ואמצעי זהירות",
        "references": "מקורות", "local_adaptation_notes": "הערות התאמה מקומית",
        "source_documents": "מסמכי מקור", "source": "מקור", "reference": "אסמכתה",
        "title_file": "כותרת / קובץ", "approval_record": "רשומת אישור",
        "prepared_by": "הוכן / הוגש על ידי", "approved_by": "אושר על ידי", "licence": "רישיון",
        "approval_date": "תאריך אישור (UTC)", "approval_notes": "הערות אישור",
        "content_hash": "טביעת התוכן המאושר (SHA-256)",
        "subtitle": "מאסטר פורמולה {number} · גרסה {version} · סטטוס: {status} · בקשה {request}",
        "disclaimer": "רשומה זו מזהה את המשתמש המחובר שאישר את הפורמולה. אין זו חתימה אלקטרונית מאושרת.",
    },
}
_PROSE = ("proposed_formula_name", "dosage_form", "ingredients", "preparation_method", "equipment", "packaging",
          "storage_conditions", "bud", "labelling_instructions", "warnings", "local_adaptation_notes")


def language(content: dict[str, Any]) -> str:
    """Hebrew layout when the draft's prose was written or translated in Hebrew."""
    return "he" if any(_RTL.search(str(content.get(k) or "")) for k in _PROSE) else "en"


def _pharmacy_header(pharmacy: dict[str, Any], width: float, rtl: bool) -> list[Any]:
    """Logo, name and address of the pharmacy the master formula belongs to."""
    lines = [para(pharmacy.get("name"), H1, width * 0.7)]
    details = " · ".join(x for x in (pharmacy.get("address"), pharmacy.get("phone")) if x)
    if details:
        lines.append(para(details, SMALL, width * 0.7))
    text = Table([[line] for line in lines], colWidths=[width * 0.72])
    text.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                              ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    logo: Any = ""
    path = pharmacy.get("logo_path")
    if path and Path(path).exists():
        try:
            reader = ImageReader(str(path))
            iw, ih = reader.getSize()
            scale = min(38 * mm / iw, 20 * mm / ih)
            logo = Image(str(path), width=iw * scale, height=ih * scale)
        except Exception:
            logo = ""
    # Logo on the left in both layouts (as on Israeli letterheads); the text aligns itself.
    header = Table([[logo, text]], colWidths=[width * 0.28, width * 0.72])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, TEAL),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [header, Spacer(1, 8)]


def render_formula_pdf(
    draft: Draft,
    request: SearchRequest,
    documents: list[SourceDocument],
    approval: Decision | None,
    content_sha256: str,
    pharmacy: dict[str, Any] | None = None,
) -> bytes:
    c = draft.content or {}
    buf = io.BytesIO()
    width = A4[0] - 30 * mm
    watermark = None if approval else "DRAFT — NOT APPROVED"
    lang = language(c)
    rtl = lang == "he"
    L = LABELS[lang]

    def row(cells: list[Any]) -> list[Any]:
        return list(reversed(cells)) if rtl else cells

    def cols(widths: list[float]) -> list[float]:
        return list(reversed(widths)) if rtl else widths

    def heading(key: str) -> Paragraph:
        return para(L[key], H2, width)

    def section(key: str, body: Any) -> list[Any]:
        if not str(body or "").strip():
            return [heading(key), para(L["not_specified"], SMALL, width)]
        return [heading(key), para(body, BODY, width)]

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 10 * mm, f"{draft.number} · v{draft.version} · content {content_sha256[:16]}")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        if watermark:
            canvas.setFont(FONT_BOLD, 44)
            canvas.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.12))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, watermark)
        canvas.restoreState()

    def cell(text: Any, w: float, bold: bool = False) -> Paragraph:
        return para(text, CELL_B if bold else CELL, w - CELL_PAD)

    story: list[Any] = _pharmacy_header(pharmacy, width, rtl) if pharmacy and pharmacy.get("name") else []
    story += [
        para(c.get("proposed_formula_name") or request.active_ingredient, H1, width),
        para(L["subtitle"].format(number=draft.number, version=draft.version, status=draft.status,
                                  request=request.number), SMALL, width),
        Spacer(1, 6),
    ]
    w4 = [width * 0.18, width * 0.32, width * 0.18, width * 0.32]
    story.append(_table(
        [
            row([cell(L["active_ingredient"], w4[0], True), cell(c.get("active_ingredient"), w4[1]),
                 cell(L["strength"], w4[2], True), cell(c.get("strength"), w4[3])]),
            row([cell(L["dosage_form"], w4[0], True), cell(c.get("dosage_form"), w4[1]),
                 cell(L["final_quantity"], w4[2], True), cell(c.get("final_quantity"), w4[3])]),
        ],
        cols(w4),
        header=False,
    ))

    ais = c.get("active_ingredients") or []
    if ais:
        wa = [width * 0.4, width * 0.2, width * 0.2, width * 0.2]
        rows = [row([cell(L[h], w, True) for h, w in zip(("active_ingredient", "strength", "quantity", "included"), wa)])]
        for a in ais:
            name = " ".join(x for x in (a.get("ingredient_name") or a.get("name"), a.get("salt_form")) if x)
            inc = a.get("included_in_local_formula", True) is not False
            rows.append(row([
                cell(name, wa[0]),
                cell(f"{a.get('strength_value', '')} {a.get('strength_unit', '')}".strip(), wa[1]),
                cell(f"{a.get('quantity_value', '')} {a.get('quantity_unit', '')}".strip(), wa[2]),
                cell(L["yes"] if inc else f"{L['no']} — {a.get('exclusion_reason', '')}", wa[3]),
            ]))
        story.append(KeepTogether([heading("active_ingredients"), _table(rows, cols(wa))]))

    for key in ("ingredients", "preparation_method", "equipment", "packaging", "storage_conditions", "bud",
                "labelling_instructions", "warnings", "references", "local_adaptation_notes"):
        story += section(key, c.get(key))

    if documents:
        wd = [width * 0.2, width * 0.18, width * 0.42, width * 0.2]
        rows = [row([cell(L[h], w, True) for h, w in zip(("source", "reference", "title_file"), wd)]
                    + [cell("SHA-256", wd[3], True)])]
        for d in documents:
            rows.append(row([
                cell(d.source_name, wd[0]),
                cell(d.source_formula_id, wd[1]),
                cell(d.title or d.file_name, wd[2]),
                cell((d.file_sha256 or "")[:16] + "…", wd[3]),
            ]))
        story.append(KeepTogether([heading("source_documents"), _table(rows, cols(wd))]))

    if approval:
        wr = [width * 0.3, width * 0.7]
        lic = L["licence"]
        rows = [
            row([cell(L["prepared_by"], wr[0], True),
                 cell(f"{approval.preparer_name or '—'} ({lic} {approval.preparer_licence or '—'})", wr[1])]),
            row([cell(L["approved_by"], wr[0], True),
                 cell(f"{approval.actor_name} ({lic} {approval.actor_licence or '—'})", wr[1])]),
            row([cell(L["approval_date"], wr[0], True), cell(approval.created_at.strftime("%Y-%m-%d %H:%M"), wr[1])]),
            row([cell(L["approval_notes"], wr[0], True), cell(approval.notes or "—", wr[1])]),
            row([cell(L["content_hash"], wr[0], True), cell(approval.content_sha256, wr[1])]),
        ]
        story += [
            KeepTogether([heading("approval_record"), _table(rows, cols(wr), header=False)]),
            Spacer(1, 6),
            para(L["disclaimer"], SMALL, width),
        ]

    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
        title=str(c.get("proposed_formula_name") or draft.number), author="Formula Manager",
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
