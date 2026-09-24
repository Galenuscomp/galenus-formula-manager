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
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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

_base = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=_base["BodyText"], fontName=FONT, fontSize=9.5, leading=13, textColor=SLATE)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
H1 = ParagraphStyle("h1", parent=BODY, fontName=FONT_BOLD, fontSize=16, leading=20, textColor=colors.black)
H2 = ParagraphStyle(
    "h2", parent=BODY, fontName=FONT_BOLD, fontSize=11, leading=14, textColor=TEAL, spaceBefore=10, spaceAfter=4
)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName=FONT_BOLD)


def _line(text: str) -> str:
    text = get_display(text) if _RTL.search(text) else text
    return escape(text)


def para(text: Any, style: ParagraphStyle = BODY) -> Paragraph:
    lines = str(text or "").strip().splitlines() or [""]
    return Paragraph("<br/>".join(_line(line) for line in lines) or "&nbsp;", style)


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


def _section(title: str, body: Any) -> list[Any]:
    if not str(body or "").strip():
        return [Paragraph(escape(title), H2), para("Not specified", SMALL)]
    return [Paragraph(escape(title), H2), para(body)]


def render_formula_pdf(
    draft: Draft,
    request: SearchRequest,
    documents: list[SourceDocument],
    approval: Decision | None,
    content_sha256: str,
) -> bytes:
    c = draft.content or {}
    buf = io.BytesIO()
    width = A4[0] - 30 * mm
    watermark = None if approval else "DRAFT — NOT APPROVED"

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

    story: list[Any] = [
        para(c.get("proposed_formula_name") or request.active_ingredient, H1),
        para(
            f"Master formula {draft.number} · version {draft.version} · status: {draft.status} · request {request.number}",
            SMALL,
        ),
        Spacer(1, 6),
        _table(
            [
                [para("Active ingredient", CELL_B), para(c.get("active_ingredient"), CELL),
                 para("Strength", CELL_B), para(c.get("strength"), CELL)],
                [para("Dosage form", CELL_B), para(c.get("dosage_form"), CELL),
                 para("Final quantity", CELL_B), para(c.get("final_quantity"), CELL)],
            ],
            [width * 0.18, width * 0.32, width * 0.18, width * 0.32],
            header=False,
        ),
    ]

    ais = c.get("active_ingredients") or []
    if ais:
        rows = [[para(h, CELL_B) for h in ("Active ingredient", "Strength", "Quantity", "Included")]]
        for a in ais:
            name = " ".join(x for x in (a.get("ingredient_name") or a.get("name"), a.get("salt_form")) if x)
            inc = a.get("included_in_local_formula", True) is not False
            rows.append([
                para(name, CELL),
                para(f"{a.get('strength_value', '')} {a.get('strength_unit', '')}".strip(), CELL),
                para(f"{a.get('quantity_value', '')} {a.get('quantity_unit', '')}".strip(), CELL),
                para("Yes" if inc else f"No — {a.get('exclusion_reason', '')}", CELL),
            ])
        story.append(KeepTogether([Paragraph("Active ingredients", H2),
                                   _table(rows, [width * 0.4, width * 0.2, width * 0.2, width * 0.2])]))

    for key, title in [
        ("ingredients", "Composition"),
        ("preparation_method", "Preparation method"),
        ("equipment", "Equipment"),
        ("packaging", "Packaging"),
        ("storage_conditions", "Storage conditions"),
        ("bud", "Beyond-use date (BUD)"),
        ("labelling_instructions", "Labelling instructions"),
        ("warnings", "Warnings and precautions"),
        ("references", "References"),
        ("local_adaptation_notes", "Local adaptation notes"),
    ]:
        story += _section(title, c.get(key))

    if documents:
        rows = [[para(h, CELL_B) for h in ("Source", "Reference", "Title / file", "File SHA-256")]]
        for d in documents:
            rows.append([
                para(d.source_name, CELL),
                para(d.source_formula_id, CELL),
                para(d.title or d.file_name, CELL),
                para((d.file_sha256 or "")[:16] + "…", CELL),
            ])
        story.append(KeepTogether([Paragraph("Source documents", H2),
                                   _table(rows, [width * 0.2, width * 0.18, width * 0.42, width * 0.2])]))

    if approval:
        rows = [
            [para("Prepared / submitted by", CELL_B),
             para(f"{approval.preparer_name or '—'} (licence {approval.preparer_licence or '—'})", CELL)],
            [para("Approved by", CELL_B), para(f"{approval.actor_name} (licence {approval.actor_licence or '—'})", CELL)],
            [para("Approval date (UTC)", CELL_B), para(approval.created_at.strftime("%Y-%m-%d %H:%M"), CELL)],
            [para("Approval notes", CELL_B), para(approval.notes or "—", CELL)],
            [para("Approved content SHA-256", CELL_B), para(approval.content_sha256, CELL)],
        ]
        story += [
            KeepTogether([Paragraph("Approval record", H2), _table(rows, [width * 0.3, width * 0.7], header=False)]),
            Spacer(1, 6),
            para(
                "This record identifies the logged-in user who approved the formula. It is not a qualified "
                "electronic signature.",
                SMALL,
            ),
        ]

    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
        title=str(c.get("proposed_formula_name") or draft.number), author="Formula Manager",
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
