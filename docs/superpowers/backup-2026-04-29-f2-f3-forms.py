# Standartinė LT struktūra: header su uzsakovo + rangovo duomenimis +
# laikotarpis + darbai + parašai. Naudojama vyriausybiniuose ir
# privačiuose statybos projektuose.

def _build_f2_workbook(data: dict):
    """Forma F2 — atliktų darbų aktas. Excel kompozicija."""
    from datetime import date as _date

    C_DARK = "1F3864"
    C_HDR  = "D6E4F0"
    thin   = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    projektas    = data.get("projektas", "Projektas")
    rangovas     = data.get("rangovas", "")
    uzsakovas    = data.get("uzsakovas", "")
    objekto_adr  = data.get("objekto_adresas", "")
    laikotarpis  = data.get("laikotarpis", _date.today().strftime("%Y-%m-%d"))
    eilutes      = data.get("eilutes", []) or []
    today_str    = _date.today().strftime("%Y-%m-%d")
    vat_rate     = float(data.get("vat_rate", 21))
    nr_doc       = data.get("dokumento_nr") or f"F2/{today_str}"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Forma F2"

    # Title block
    ws.merge_cells("A1:G1")
    c = ws["A1"]
    c.value = "FORMA F2 — ATLIKTŲ DARBŲ AKTAS"
    c.font = Font(bold=True, size=14, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_DARK)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    ws["A3"] = f"Akto Nr.: {nr_doc}"
    ws["A4"] = f"Sudarymo data: {today_str}"
    ws["A5"] = f"Atlikimo laikotarpis: {laikotarpis}"
    ws["A7"] = f"Užsakovas: {uzsakovas}"
    ws["A8"] = f"Rangovas: {rangovas}"
    ws["A9"] = f"Objektas: {objekto_adr}"
    ws["A10"] = f"Projektas: {projektas}"
    for r in (3, 4, 5, 7, 8, 9, 10):
        ws[f"A{r}"].font = Font(size=10)

    # Table header
    headers = ["Eil. Nr.", "Darbų / paslaugų pavadinimas", "Mato vnt.", "Kiekis", "Kaina €", "Suma €", "Pastabos"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=12, column=ci, value=h)
        c.font = Font(bold=True, size=10)
        c.fill = PatternFill("solid", fgColor=C_HDR)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border
    ws.row_dimensions[12].height = 28

    col_widths = {"A": 8, "B": 56, "C": 10, "D": 12, "E": 12, "F": 14, "G": 24}
    for col, w in col_widths.items():
        ws.column_dimensions[col].width = w

    sub_total = 0.0
    row = 13
    for i, e in enumerate(eilutes, 1):
        kiekis = float(e.get("kiekis") or 0)
        kaina  = float(e.get("kaina") or 0)
        suma   = round(kiekis * kaina, 2)
        sub_total += suma
        vals = [i,
                e.get("aprasymas", ""),
                e.get("mato_vnt", ""),
                kiekis,
                kaina,
                suma,
                e.get("pastabos", "") or ""]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=row, column=ci, value=v)
            c.border = border
            c.font = Font(size=10)
            if ci in (4, 5, 6):
                c.number_format = "#,##0.00"
                c.alignment = Alignment(horizontal="right")
        row += 1

    # Totals
    vat_amount = round(sub_total * vat_rate / 100, 2)
    grand = round(sub_total + vat_amount, 2)
    ws.cell(row=row + 1, column=5, value="Iš viso be PVM:").font = Font(bold=True)
    c = ws.cell(row=row + 1, column=6, value=sub_total)
    c.number_format = "#,##0.00"; c.font = Font(bold=True); c.alignment = Alignment(horizontal="right")
    ws.cell(row=row + 2, column=5, value=f"PVM ({vat_rate:.0f}%):").font = Font(size=10)
    c = ws.cell(row=row + 2, column=6, value=vat_amount)
    c.number_format = "#,##0.00"; c.alignment = Alignment(horizontal="right")
    ws.cell(row=row + 3, column=5, value="Iš viso su PVM:").font = Font(bold=True, size=11)
    c = ws.cell(row=row + 3, column=6, value=grand)
    c.number_format = "#,##0.00"; c.font = Font(bold=True, size=11)
    c.fill = PatternFill("solid", fgColor="FFF8F0")
    c.alignment = Alignment(horizontal="right")

    # Signatures
    sig_row = row + 6
    ws.cell(row=sig_row, column=1, value="Užsakovas:").font = Font(bold=True)
    ws.cell(row=sig_row, column=4, value="Rangovas:").font = Font(bold=True)
    ws.cell(row=sig_row + 2, column=1, value="(parašas, vardas, pavardė)")
    ws.cell(row=sig_row + 2, column=4, value="(parašas, vardas, pavardė)")
    for r in (sig_row, sig_row + 1, sig_row + 2):
        for col in ("B", "C", "E", "F"):
            ws[f"{col}{r}"].border = Border(bottom=thin) if r == sig_row + 1 else None

    return wb


def _build_f3_workbook(data: dict):
    """Forma F3 — Pažyma apie atliktų darbų vertę. Cumulative summary form."""
    from datetime import date as _date

    C_DARK = "1F3864"
    C_HDR  = "D6E4F0"
    thin   = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    projektas    = data.get("projektas", "Projektas")
    rangovas     = data.get("rangovas", "")
    uzsakovas    = data.get("uzsakovas", "")
    objekto_adr  = data.get("objekto_adresas", "")
    laikotarpis  = data.get("laikotarpis", _date.today().strftime("%Y-%m-%d"))
    sutarties_nr = data.get("sutarties_nr", "")
    eilutes      = data.get("eilutes", []) or []
    today_str    = _date.today().strftime("%Y-%m-%d")
    vat_rate     = float(data.get("vat_rate", 21))
    nr_doc       = data.get("dokumento_nr") or f"F3/{today_str}"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Forma F3"

    ws.merge_cells("A1:F1")
    c = ws["A1"]
    c.value = "FORMA F3 — PAŽYMA APIE ATLIKTŲ DARBŲ VERTĘ"
    c.font = Font(bold=True, size=14, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=C_DARK)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    ws["A3"] = f"Pažymos Nr.: {nr_doc}"
    ws["A4"] = f"Sudarymo data: {today_str}"
    ws["A5"] = f"Sutarties Nr.: {sutarties_nr}"
    ws["A6"] = f"Atlikimo laikotarpis: {laikotarpis}"
    ws["A8"] = f"Užsakovas: {uzsakovas}"
    ws["A9"] = f"Rangovas: {rangovas}"
    ws["A10"] = f"Objektas: {objekto_adr}"
    ws["A11"] = f"Projektas: {projektas}"
    for r in (3, 4, 5, 6, 8, 9, 10, 11):
        ws[f"A{r}"].font = Font(size=10)

    headers = ["Eil. Nr.", "Skyrius / etapas", "Sutarties vertė €", "Atlikta šiuo laikotarpiu €", "Atlikta nuo sutarties pradžios €", "Likutis €"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=13, column=ci, value=h)
        c.font = Font(bold=True, size=10)
        c.fill = PatternFill("solid", fgColor=C_HDR)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border
    ws.row_dimensions[13].height = 36

    col_widths = {"A": 8, "B": 36, "C": 18, "D": 22, "E": 22, "F": 16}
    for col, w in col_widths.items():
        ws.column_dimensions[col].width = w

    # Group by skyrius
    by_sk = {}
    for e in eilutes:
        sk = e.get("skyrius", "Kiti darbai") or "Kiti darbai"
        kiekis = float(e.get("kiekis") or 0)
        kaina  = float(e.get("kaina") or 0)
        suma   = round(kiekis * kaina, 2)
        by_sk[sk] = by_sk.get(sk, 0.0) + suma

    row = 14
    grand_period = 0.0
    for i, (sk, suma) in enumerate(sorted(by_sk.items(), key=lambda x: -x[1]), 1):
        # F3 has multiple period columns; we fill "this period" only since
        # we don't have prior-period data. User can edit Excel manually.
        sutarties_verte = suma  # default — same as period
        atlikta_iki_dabar = suma
        likutis = 0.0
        vals = [i, sk, sutarties_verte, suma, atlikta_iki_dabar, likutis]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=row, column=ci, value=v)
            c.border = border
            c.font = Font(size=10)
            if ci >= 3:
                c.number_format = "#,##0.00"
                c.alignment = Alignment(horizontal="right")
        grand_period += suma
        row += 1

    # Totals + VAT
    vat_amount = round(grand_period * vat_rate / 100, 2)
    grand = round(grand_period + vat_amount, 2)
    ws.cell(row=row + 1, column=3, value="Iš viso be PVM:").font = Font(bold=True)
    c = ws.cell(row=row + 1, column=4, value=grand_period); c.number_format = "#,##0.00"; c.font = Font(bold=True); c.alignment = Alignment(horizontal="right")
    ws.cell(row=row + 2, column=3, value=f"PVM ({vat_rate:.0f}%):")
    c = ws.cell(row=row + 2, column=4, value=vat_amount); c.number_format = "#,##0.00"; c.alignment = Alignment(horizontal="right")
    ws.cell(row=row + 3, column=3, value="Mokėtina suma su PVM:").font = Font(bold=True, size=11)
    c = ws.cell(row=row + 3, column=4, value=grand); c.number_format = "#,##0.00"
    c.font = Font(bold=True, size=11); c.fill = PatternFill("solid", fgColor="FFF8F0"); c.alignment = Alignment(horizontal="right")

    sig_row = row + 6
    ws.cell(row=sig_row, column=1, value="Užsakovas:").font = Font(bold=True)
    ws.cell(row=sig_row, column=4, value="Rangovas:").font = Font(bold=True)
    ws.cell(row=sig_row + 2, column=1, value="(parašas, vardas, pavardė)")
    ws.cell(row=sig_row + 2, column=4, value="(parašas, vardas, pavardė)")

    return wb


@app.post("/export/f2")
async def export_f2(data: dict):
    """Forma F2 — Atliktų darbų aktas. Receives same payload shape as
    /generate-excel plus optional rangovas/uzsakovas/objekto_adresas/laikotarpis fields."""
    import re as _re_local
    wb = _build_f2_workbook(data)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = "F2_" + _re_local.sub(r"[^\w]", "_", (data.get("projektas") or "projektas")[:30], flags=_re_local.ASCII) + ".xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/export/f3")
async def export_f3(data: dict):
    """Forma F3 — Pažyma apie atliktų darbų vertę. Cumulative skyrius totals."""
    import re as _re_local
    wb = _build_f3_workbook(data)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = "F3_" + _re_local.sub(r"[^\w]", "_", (data.get("projektas") or "projektas")[:30], flags=_re_local.ASCII) + ".xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── Sprint §37 (2026-04-29): F2/F3 PDF variants ─────────────────────────
# Same content as Excel form but using reportlab for printable PDF output.
# Some LT contractors prefer signing physical paper; PDF is the print path.

def _build_lt_form_pdf(data: dict, form_type: str = "F2") -> bytes:
    """Build either F2 or F3 form as PDF. Single-page layout with header,
    table, totals, signature block. Returns raw PDF bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from datetime import date as _date

    projektas    = data.get("projektas", "Projektas")
    rangovas     = data.get("rangovas", "")
    uzsakovas    = data.get("uzsakovas", "")
    objekto_adr  = data.get("objekto_adresas", "")
    laikotarpis  = data.get("laikotarpis", _date.today().strftime("%Y-%m-%d"))
    sutarties_nr = data.get("sutarties_nr", "")
    eilutes      = data.get("eilutes", []) or []
    today_str    = _date.today().strftime("%Y-%m-%d")
    vat_rate     = float(data.get("vat_rate", 21))
    nr_doc       = data.get("dokumento_nr") or f"{form_type}/{today_str}"

    DARK = colors.HexColor("#1F3864")
    GRID = colors.HexColor("#999999")
    HDR_BG = colors.HexColor("#D6E4F0")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm,
    )

    styles = getSampleStyleSheet()
    title_st = ParagraphStyle("title", parent=styles["Title"], fontSize=14,
                              textColor=colors.white, alignment=TA_CENTER)
    body_st = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=11)
    small_st = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=10,
                              textColor=colors.grey)

    elements = []

    # Title banner
    title_text = ("FORMA F2 — ATLIKTŲ DARBŲ AKTAS" if form_type == "F2"
                  else "FORMA F3 — PAŽYMA APIE ATLIKTŲ DARBŲ VERTĘ")
    title_table = Table([[Paragraph(title_text, title_st)]],
                        colWidths=[doc.width])
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 8))

    # Document metadata
    info_rows = [
        [f"{form_type} Nr.: {nr_doc}", f"Sudarymo data: {today_str}"],
        [f"Atlikimo laikotarpis: {laikotarpis}",
         f"Sutarties Nr.: {sutarties_nr}" if form_type == "F3" else ""],
    ]
    info_table = Table(info_rows, colWidths=[doc.width / 2] * 2)
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4))

    parties_rows = [
        [Paragraph(f"<b>Užsakovas:</b> {uzsakovas}", body_st)],
        [Paragraph(f"<b>Rangovas:</b> {rangovas}", body_st)],
        [Paragraph(f"<b>Objektas:</b> {objekto_adr}", body_st)],
        [Paragraph(f"<b>Projektas:</b> {projektas}", body_st)],
    ]
    parties_table = Table(parties_rows, colWidths=[doc.width])
    parties_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
    ]))
    elements.append(parties_table)
    elements.append(Spacer(1, 12))

    # Data table
    if form_type == "F2":
        # Per-row F2: Nr, Aprašymas, Mato vnt, Kiekis, Kaina, Suma
        head = ["Nr.", "Darbų pavadinimas", "Vnt.", "Kiekis", "Kaina €", "Suma €"]
        col_widths = [1.2 * cm, 9.5 * cm, 1.5 * cm, 2 * cm, 2 * cm, 2.3 * cm]
        rows_data = [head]
        sub_total = 0.0
        for i, e in enumerate(eilutes, 1):
            kiekis = float(e.get("kiekis") or 0)
            kaina = float(e.get("kaina") or 0)
            suma = round(kiekis * kaina, 2)
            sub_total += suma
            rows_data.append([
                str(i),
                Paragraph((e.get("aprasymas") or "")[:200], body_st),
                e.get("mato_vnt", ""),
                f"{kiekis:,.2f}".replace(",", " "),
                f"{kaina:,.2f}".replace(",", " "),
                f"{suma:,.2f}".replace(",", " "),
            ])
    else:
        # F3 grouped by skyrius
        from collections import OrderedDict
        groups: dict[str, float] = OrderedDict()
        for e in eilutes:
            sk = e.get("skyrius") or "Kiti darbai"
            kiekis = float(e.get("kiekis") or 0)
            kaina = float(e.get("kaina") or 0)
            groups[sk] = groups.get(sk, 0.0) + (kiekis * kaina)
        head = ["Nr.", "Skyrius / etapas", "Sutarties vertė €",
                "Atlikta šiuo laikotarpiu €", "Atlikta nuo pradžios €", "Likutis €"]
        col_widths = [1 * cm, 5.5 * cm, 2.5 * cm, 3 * cm, 3 * cm, 2.5 * cm]
        rows_data = [head]
        sub_total = 0.0
        for i, (sk, suma) in enumerate(sorted(groups.items(), key=lambda x: -x[1]), 1):
            sub_total += suma
            rows_data.append([
                str(i), Paragraph(sk, body_st),
                f"{suma:,.2f}".replace(",", " "),
                f"{suma:,.2f}".replace(",", " "),
                f"{suma:,.2f}".replace(",", " "),
                "0,00",
            ])

    table = Table(rows_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HDR_BG),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 8))

    # Totals
    vat_amount = round(sub_total * vat_rate / 100, 2)
    grand = round(sub_total + vat_amount, 2)
    totals_data = [
        ["", "", "", "", "Iš viso be PVM:", f"{sub_total:,.2f}".replace(",", " ")],
        ["", "", "", "", f"PVM ({vat_rate:.0f}%):", f"{vat_amount:,.2f}".replace(",", " ")],
        ["", "", "", "", "Iš viso su PVM:", f"{grand:,.2f}".replace(",", " ")],
    ]
    totals_table = Table(totals_data, colWidths=col_widths)
    totals_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (4, 2), (-1, 2), "Helvetica-Bold"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (4, 2), (-1, 2), colors.HexColor("#FFF8F0")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 32))

    # Signatures
    sig_data = [
        [Paragraph("<b>Užsakovas:</b>", body_st), "",
         Paragraph("<b>Rangovas:</b>", body_st), ""],
        [Paragraph("_____________________", body_st), "",
         Paragraph("_____________________", body_st), ""],
        [Paragraph("(parašas, vardas, pavardė)", small_st), "",
         Paragraph("(parašas, vardas, pavardė)", small_st), ""],
    ]
    sig_table = Table(sig_data, colWidths=[doc.width / 4] * 4)
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buf.seek(0)
    return buf.read()


@app.post("/export/f2-pdf")
async def export_f2_pdf(data: dict):
    """Forma F2 PDF — printable variant of Excel /export/f2."""
    import re as _re_local
    pdf_bytes = _build_lt_form_pdf(data, form_type="F2")
    fname = "F2_" + _re_local.sub(r"[^\w]", "_", (data.get("projektas") or "projektas")[:30], flags=_re_local.ASCII) + ".pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/export/f3-pdf")
async def export_f3_pdf(data: dict):
    """Forma F3 PDF — printable variant of Excel /export/f3."""
    import re as _re_local
    pdf_bytes = _build_lt_form_pdf(data, form_type="F3")
    fname = "F3_" + _re_local.sub(r"[^\w]", "_", (data.get("projektas") or "projektas")[:30], flags=_re_local.ASCII) + ".pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
