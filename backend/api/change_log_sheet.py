"""„Pakeitimų žurnalas" — the internal copy's change-log sheet (v3 W7-A M5, 2026-10-18).

What the contractor changed in the project, in his words, newest first: every
`corrections` row (an assumption in Prielaidos, an outline, a symbol decision,
a typed number) and every saved version (`project_versions`). Only for the
internal copy („Vidinė kopija su pastabomis") — the client's file never carries
it — and only for a project the caller owns (the export body names the project;
a foreign or unknown id simply yields no sheet).

Pure apart from the two DB reads. No raw field paths or JSON reach the sheet:
an unknown change reads „Kitas pakeitimas".
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

SHEET_TITLE = "Pakeitimų žurnalas"
MAX_ROWS = 500

# corrections.field_path first segment → what he changed.
_FIELD_LABELS = {
    "lubu_auksciai": "Lubų aukštis",
    "glaistimo_lygis": "Glaistymo lygis",
    "stretch_ceiling_override": "Įtempiamos lubos",
    "vidaus_durys_beapvadines": "Vidaus durys be apvadų",
    "angokrasciai_apimtis": "Angokraščiai — kurių angų",
    "sienos_storis_m": "Sienos storis, m",
    "simbolis": "Simbolio sprendimas",
}
# patalpa.<nr>.<what>
_ROOM_PART_LABELS = {
    "kontūras": "Patalpos kontūras",
    "konturas": "Patalpos kontūras",
    "pertvaros": "Patalpos pertvaros",
    "plotas_m2": "Patalpos plotas, m²",
    "perimetras_m": "Patalpos perimetras, m",
    "lubu_aukstis_m": "Lubų aukštis, m",
}
_SOURCE_LABELS = {
    "prielaidos": "Prielaidos",
    "konturas": "Kontūras brėžinyje",
    "patalpa_pertvaros": "Patalpos pertvaros",
    "simbolis": "Simbolių žymėjimas",
    "inline_edit": "Pataisyta lentelėje",
}
# project_versions.saltinis — the frontend twin is lib/projectVersions.js SOURCE_LABELS.
_VERSION_LABELS = {
    "issaugota": "Išsaugota",
    "perskaityta": "Brėžinys perskaitytas iš naujo",
    "lapas": "Perskaitytas lapas",
    "klausimas": "Atsakytas klausimas",
    "grazinta": "Prieš grąžinant",
    "kita": "Kita",
}


def _when(iso: str | None) -> str:
    """„2026-10-16 14:02" in Lithuanian time; '' for a bad stamp."""
    if not iso:
        return ""
    try:
        t = _dt.datetime.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return str(iso)[:16]
    try:
        from zoneinfo import ZoneInfo
        t = t.astimezone(ZoneInfo("Europe/Vilnius"))
    except Exception:  # noqa: BLE001 — no tz database: UTC, still a time
        pass
    return t.strftime("%Y-%m-%d %H:%M")


def _value(v: Any) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "taip" if v else "ne"
    if isinstance(v, (int, float)):
        s = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
        return s.replace(".", ",")
    if isinstance(v, str):
        return v[:120]
    if isinstance(v, dict) and len(v) == 1:
        (only,) = v.values()
        if isinstance(only, (str, int, float, bool)) or only is None:
            return _value(only)
    return "pakeista"


def describe(field_path: str, room_nr: str | None = None) -> tuple[str, str]:
    """(what changed, room) for one corrections row."""
    parts = str(field_path or "").split(".")
    head = parts[0]
    room = str(room_nr or "")
    if head == "patalpa" and len(parts) >= 3:
        return _ROOM_PART_LABELS.get(parts[2], "Patalpos pakeitimas"), room or parts[1]
    if head == "simbolis" and len(parts) >= 2:
        return f"Simbolio sprendimas (lapas {parts[1]})", room
    label = _FIELD_LABELS.get(head, "Kitas pakeitimas")
    if len(parts) >= 2 and head in ("lubu_auksciai", "stretch_ceiling_override"):
        room = room or parts[1]
    return label, room


def change_log_entries(project_id: str, user: dict) -> list[dict]:
    """The rows of the sheet for a project the caller owns; [] otherwise."""
    import db
    if not project_id or not isinstance(project_id, str) or not user:
        return []
    user_filter = None if user.get("is_admin") else user.get("id")
    if db.get_project(project_id, user_id=user_filter) is None:
        return []
    out: list[dict] = []
    for c in db.list_corrections(project_id, limit=MAX_ROWS):
        what, room = describe(c.get("field_path"), c.get("room_nr"))
        out.append({
            "_at": c.get("occurred_at") or "",
            "kada": _when(c.get("occurred_at")),
            "kas": what,
            "patalpa": room,
            "buvo": _value(c.get("old_value")),
            "dabar": _value(c.get("new_value")),
            "kaip": _SOURCE_LABELS.get(c.get("source") or "", "Kita"),
        })
    for v in db.list_project_versions(project_id, user_id=user_filter) or []:
        name = (v.get("pavadinimas") or "").strip()
        out.append({
            "_at": v.get("created_at") or "",
            "kada": _when(v.get("created_at")),
            "kas": "Išsaugota versija" + (f" „{name[:80]}“" if name else ""),
            "patalpa": "",
            "buvo": "",
            "dabar": "",
            "kaip": _VERSION_LABELS.get(v.get("saltinis") or "", "Kita"),
        })
    out.sort(key=lambda e: e["_at"], reverse=True)
    return out[:MAX_ROWS]


def write_change_log_sheet(wb, entries: list[dict], projektas: str, *, safe_cell) -> None:
    """Add the sheet to an openpyxl workbook. `safe_cell` neutralises formulas
    (extractor.spreadsheet_safety). Nothing to show → one explaining row."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    ws = wb.create_sheet(title=SHEET_TITLE)
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.merge_cells("A1:F1")
    t = ws["A1"]
    t.value = safe_cell(f"Pakeitimų žurnalas  ·  {projektas}  ·  naujausi viršuje")
    t.font = Font(bold=True, size=11, color="FFFFFF")
    t.fill = PatternFill("solid", fgColor="2E4D7B")
    t.alignment = Alignment(horizontal="left", vertical="center", indent=2)
    ws.row_dimensions[1].height = 24
    heads = ["Kada", "Kas pakeista", "Patalpa", "Buvo", "Dabar", "Kaip"]
    widths = [17, 40, 10, 16, 16, 28]
    for ci, (lbl, w) in enumerate(zip(heads, widths), 1):
        c = ws.cell(row=2, column=ci, value=lbl)
        c.font = Font(bold=True, size=9, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
        c.border = border
        ws.column_dimensions[chr(64 + ci)].width = w
    if not entries:
        ws.merge_cells("A3:F3")
        ws["A3"].value = "Šiame projekte pakeitimų dar neužrašyta."
        ws["A3"].font = Font(size=9, italic=True)
        return
    for ri, e in enumerate(entries, 3):
        fill = PatternFill("solid", fgColor="F5F5F5" if ri % 2 else "FFFFFF")
        for ci, key in enumerate(("kada", "kas", "patalpa", "buvo", "dabar", "kaip"), 1):
            c = ws.cell(row=ri, column=ci, value=safe_cell(str(e.get(key) or "")))
            c.fill = fill
            c.border = border
            c.font = Font(size=9)
