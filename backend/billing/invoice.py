"""LT PVM sąskaita-faktūra (VAT invoice) generator — W3 Phase 6 Task 13.

Two responsibilities, split so the money logic is unit-testable without parsing
PDF bytes:

  - `build_invoice_fields(user, item, number, issued_at) -> dict` — PURE. Reads
    the supplier block from `PATHON_COMPANY_*` env, the buyer block from the user
    row, computes sum/VAT/total per the LT reverse-charge rules, and returns a
    flat dict. No I/O, no reportlab — trivially assertable.
  - `render_pvm_invoice_pdf(fields) -> bytes` — renders that dict to a valid PDF
    via reportlab and returns the raw bytes.

VAT logic (docs/pricing.md §4 — reverse-charge reality for our B2B LT buyers):
  1. Buyer is VAT-registered (non-empty `pvm_code`) → **reverse charge**: Pathon
     adds no VAT, the buyer self-accounts (PVMĮ 96 str.). total == sum.
  2. Buyer not registered AND Pathon not registered (no `PATHON_COMPANY_PVM`,
     under the €45k threshold at launch) → **not a VAT payer**: no VAT line.
     total == sum.
  3. Buyer not registered AND Pathon registered → **standard**: add 21% PVM.
     total == sum + vat.
"""
from __future__ import annotations

import io
import os

VAT_RATE = 0.21

_REVERSE_CHARGE_NOTE = (
    "Atvirkštinis PVM (PVMĮ 96 str.). PVM apskaičiuoja ir sumoka pirkėjas."
)
_NOT_VAT_PAYER_NOTE = "Pardavėjas nėra PVM mokėtojas."
_STANDARD_NOTE = "PVM 21%."


def _supplier_from_env() -> dict:
    """Assemble the supplier (Pathon) block from PATHON_COMPANY_* env vars.

    Every field defaults to "" so a partially-configured environment never
    raises — the invoice simply omits what is unset. `pvm_code` empty means
    Pathon is not VAT-registered (under the €45k threshold), which drives the
    not-vat-payer branch below."""
    return {
        "name": os.environ.get("PATHON_COMPANY_NAME", "") or "",
        "code": os.environ.get("PATHON_COMPANY_CODE", "") or "",
        "pvm_code": os.environ.get("PATHON_COMPANY_PVM", "") or "",
        "address": os.environ.get("PATHON_COMPANY_ADDRESS", "") or "",
        "iban": os.environ.get("PATHON_COMPANY_IBAN", "") or "",
        "email": os.environ.get("PATHON_COMPANY_EMAIL", "") or "",
    }


def _buyer_from_user(user: dict) -> dict:
    """Assemble the buyer block from the user row. Prefer company_name (the legal
    invoice name) over the personal name; fall back to the personal name."""
    user = user or {}
    name = (user.get("company_name") or user.get("name") or "") or ""
    return {
        "name": name,
        "company_code": (user.get("company_code") or "") or "",
        "pvm_code": (user.get("pvm_code") or "") or "",
        "email": (user.get("email") or "") or "",
    }


def build_invoice_fields(user: dict, item: dict, number: str,
                         issued_at: str) -> dict:
    """PURE assembly of every field a PVM sąskaita-faktūra needs. See module doc
    for the VAT branch logic. `item` = {description, qty, unit_price_eur}."""
    supplier = _supplier_from_env()
    buyer = _buyer_from_user(user)

    item = item or {}
    qty = item.get("qty", 1) or 0
    unit_price = item.get("unit_price_eur", 0) or 0
    sum_eur = round(float(qty) * float(unit_price), 2)

    buyer_registered = bool(buyer["pvm_code"])
    supplier_registered = bool(supplier["pvm_code"])

    vat_eur: float | None = None
    if buyer_registered:
        # Reverse charge — Pathon collects no VAT; buyer self-accounts.
        vat_mode = "reverse_charge"
        vat_note = _REVERSE_CHARGE_NOTE
        total_eur = sum_eur
    elif not supplier_registered:
        # Pathon under the VAT threshold → not a VAT payer → no VAT line.
        vat_mode = "not_vat_payer"
        vat_note = _NOT_VAT_PAYER_NOTE
        total_eur = sum_eur
    else:
        # Supplier registered, buyer not → standard 21% PVM.
        vat_mode = "standard"
        vat_note = _STANDARD_NOTE
        vat_eur = round(sum_eur * VAT_RATE, 2)
        total_eur = round(sum_eur + vat_eur, 2)

    return {
        "supplier": supplier,
        "buyer": buyer,
        "number": number,
        "issued_at": issued_at,
        "item": {
            "description": item.get("description", "") or "",
            "qty": qty,
            "unit_price_eur": round(float(unit_price), 2),
        },
        "sum_eur": sum_eur,
        "vat_mode": vat_mode,
        "vat_eur": vat_eur,
        "vat_note": vat_note,
        "total_eur": total_eur,
    }


# ── PDF rendering ────────────────────────────────────────────────────────────
# Reuse the same vendored DejaVu Unicode font main.py registers so Lithuanian
# glyphs (ąčęėįšųūž) render correctly on the Render Linux box (Helvetica has no
# LT glyphs). Registration is idempotent + defensive: if the font is already
# registered (main.py imported first) or the file is missing, fall back cleanly.

_FONT_NORMAL = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    global _FONT_NORMAL, _FONT_BOLD
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets", "fonts")
        registered = set(pdfmetrics.getRegisteredFontNames())
        if "ArialUni" not in registered:
            pdfmetrics.registerFont(
                TTFont("ArialUni", os.path.join(font_dir, "DejaVuSans.ttf")))
        if "ArialUniBold" not in registered:
            pdfmetrics.registerFont(
                TTFont("ArialUniBold", os.path.join(font_dir, "DejaVuSans-Bold.ttf")))
        _FONT_NORMAL = "ArialUni"
        _FONT_BOLD = "ArialUniBold"
    except Exception:  # noqa: BLE001 — glyphless Helvetica beats no invoice.
        _FONT_NORMAL = "Helvetica"
        _FONT_BOLD = "Helvetica-Bold"


def _eur(value: float) -> str:
    return f"{float(value):.2f} €"


def render_pvm_invoice_pdf(fields: dict) -> bytes:
    """Render a `build_invoice_fields` dict into a valid LT sąskaita-faktūra PDF.
    Returns raw bytes (starting with %PDF). Contains the supplier block, buyer
    block, "Sąskaita faktūra" heading with serija/numeris, data, the line-item
    table, sum, the VAT note, total, and the IBAN."""
    _register_fonts()
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    supplier = fields.get("supplier", {})
    buyer = fields.get("buyer", {})
    item = fields.get("item", {})

    h1 = ParagraphStyle("h1", fontName=_FONT_BOLD, fontSize=15, leading=18)
    label = ParagraphStyle("label", fontName=_FONT_BOLD, fontSize=9, leading=12)
    body = ParagraphStyle("body", fontName=_FONT_NORMAL, fontSize=9, leading=12)
    body_r = ParagraphStyle("body_r", fontName=_FONT_NORMAL, fontSize=9,
                            leading=12, alignment=TA_RIGHT)
    note = ParagraphStyle("note", fontName=_FONT_NORMAL, fontSize=8.5,
                          leading=11, textColor=colors.HexColor("#444444"))
    total_style = ParagraphStyle("total", fontName=_FONT_BOLD, fontSize=11,
                                 leading=14, alignment=TA_RIGHT)

    # Paragraph() parses its text as reportlab markup; buyer fields are typed by
    # the user (audit backend-security-8: "<font …>" or a stray "&" broke or
    # restyled the invoice). Every field is escaped before it is laid out.
    from xml.sax.saxutils import escape as _x

    def _party_lines(party: dict, is_supplier: bool) -> list:
        lines = [Paragraph(_x(str(party.get("name", "") or "—")), body)]
        code_key = "code" if is_supplier else "company_code"
        if party.get(code_key):
            lines.append(Paragraph(f"Įmonės kodas: {_x(str(party[code_key]))}", body))
        if party.get("pvm_code"):
            lines.append(Paragraph(f"PVM kodas: {_x(str(party['pvm_code']))}", body))
        if is_supplier and party.get("address"):
            lines.append(Paragraph(_x(str(party["address"])), body))
        if party.get("email"):
            lines.append(Paragraph(_x(str(party["email"])), body))
        if is_supplier and party.get("iban"):
            lines.append(Paragraph(f"IBAN: {_x(str(party['iban']))}", body))
        return lines

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="PVM saskaita faktura")
    story: list = []

    story.append(Paragraph(
        f"Sąskaita faktūra Serija PATHON Nr. {fields.get('number', '')}", h1))
    story.append(Paragraph(f"Data: {fields.get('issued_at', '')}", body))
    story.append(Spacer(1, 0.5 * cm))

    # Supplier / buyer two-column block.
    parties = Table(
        [[Paragraph("Pardavėjas", label), Paragraph("Pirkėjas", label)],
         [_party_lines(supplier, True), _party_lines(buyer, False)]],
        colWidths=[8.5 * cm, 8.5 * cm])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
    ]))
    story.append(parties)
    story.append(Spacer(1, 0.6 * cm))

    # Line-item table.
    rows = [
        [Paragraph("Aprašymas", label), Paragraph("Kiekis", label),
         Paragraph("Vnt. kaina", label), Paragraph("Suma", label)],
        [Paragraph(_x(str(item.get("description", "") or "")), body),
         Paragraph(str(item.get("qty", "")), body_r),
         Paragraph(_eur(item.get("unit_price_eur", 0)), body_r),
         Paragraph(_eur(fields.get("sum_eur", 0)), body_r)],
    ]
    tbl = Table(rows, colWidths=[9 * cm, 2.5 * cm, 3 * cm, 3 * cm])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph(f"Suma: {_eur(fields.get('sum_eur', 0))}", body_r))
    if fields.get("vat_eur") is not None:
        story.append(Paragraph(f"PVM (21%): {_eur(fields['vat_eur'])}", body_r))
    story.append(Paragraph(f"Iš viso mokėti: {_eur(fields.get('total_eur', 0))}",
                           total_style))
    story.append(Spacer(1, 0.5 * cm))

    if fields.get("vat_note"):
        story.append(Paragraph(fields["vat_note"], note))
    if supplier.get("iban"):
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(f"Apmokėti į sąskaitą: {supplier['iban']}", body))

    doc.build(story)
    return buf.getvalue()
