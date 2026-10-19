"""The „Mokymosi žurnalas" — one Lithuanian sentence per `corrections` row (togal-v2 W11).

Presentation over stored data only: what the person did, in the app's own words, built
by ONE function so every place that shows the journal says the same thing. Numbers use
a comma decimal. A sentence never carries a client, project or company name: rooms are
named by their number, rows by their own work label, questions by their topic.
"""
from __future__ import annotations

from typing import Any

from extractor import user_text as _user_text

# The Patikra question kinds (extractor/project_questions.ORDER) → what the question was about.
QUESTION_TOPICS = {
    "aukstis": "lubų aukštį",
    "konturas": "patalpų kontūrus",
    "erdve": "atvirą erdvę",
    "perimetras": "perimetrus",
    "plotas": "plotus",
    "angos": "angas",
    "durys": "vidaus duris",
    "grindys": "grindų dangas",
    "apdaila": "sienų apdailą",
    # the drawing's schedules against what was read elsewhere (Pathon v3 W3-A; answered in Patikra since W2-B)
    "lentele_durys": "durų žiniaraštį",
    "lentele_langai": "langų žiniaraštį",
    "lentele_zymos": "žiniaraščio žymes plane",
    "lentele_apdaila": "apdailos lentelę",
    "lentele_suma": "eksplikacijos sumą",
}

# `_konturas.saltinis` (api/room_outline.py) → what the person did to the outline.
OUTLINE_ACTS = {
    "nubrezta": "kontūrą nubrėžėte ranka",
    "parodyta": "kontūrą parodėte spustelėdami patalpoje",
    "pasiulyta": "priėmėte programos siūlomą kontūrą",
    "padalinta": "atvirą erdvę padalijote linija",
    "sujungta": "patalpą sujungėte su kita",
}

# What an „Atšaukti" undid (api/room_outline.py `_restore`, source „atsaukta"), in the accusative.
UNDONE_ACTS = {
    "konturas": "kontūro pakeitimą",
    "sujungimas": "patalpų sujungimą",
    "padalijimas": "erdvės padalijimą",
}

# Prielaidos fields (AssumptionsPanel) → what was changed, in the accusative.
SETTING_NAMES = {
    "lubu_auksciai": "lubų aukštį",
    "walls_paint_override": "sienų apdailą",
    "stretch_ceiling_override": "įtempiamas lubas",
    "glaistimo_lygis": "glaistymo lygį",
    "sienos_storis_m": "sienos storį",
}


def lt_number(value: Any) -> str | None:
    """143.2 → „143,2", 150 → „150,0", 10.123 → „10,12"; None for anything that is not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    text = f"{float(value):.2f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text.replace(".", ",")


def _rows_by_id(project: dict | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in (project or {}).get("darbu_sarasas") or (project or {}).get("pozicijos") or []:
        if not isinstance(row, dict):
            continue
        for key in (row.get("id"), row.get("_id"), f"{row.get('eil_nr', '')}-{row.get('aprasymas', '')}"):
            if key:
                out.setdefault(str(key), row)
    return out


def _path(c: dict) -> list[str]:
    return str(c.get("field_path") or "").split(".")


def _row_label(c: dict, rows: dict[str, dict]) -> tuple[str, str]:
    """(„Eilutė „Sienų dažymas"" or „Eilutė", its unit) — the row's id sits between `eilute.` and `.kiekis`."""
    parts = _path(c)
    rid = ".".join(parts[1:-1]) if len(parts) >= 3 else ""
    row = rows.get(rid) or {}
    label = str(row.get("aprasymas") or "").strip()
    unit = str(row.get("mato_vnt") or row.get("vnt") or "").strip()
    return (f"Eilutė „{label}“" if label else "Eilutė"), unit


def _qty(value: Any, unit: str) -> str:
    """A quantity with its unit; a whole count of pieces („vnt.") without a decimal."""
    if unit.startswith("vnt") and isinstance(value, (int, float)) and not isinstance(value, bool) and float(value).is_integer():
        return f"{int(value)} {unit}"
    n = lt_number(value)
    return f"{n} {unit}".strip() if n is not None else "—"


def _room(c: dict) -> str:
    nr = c.get("room_nr")
    if not nr:
        parts = _path(c)
        nr = parts[1] if len(parts) >= 2 and parts[0] == "patalpa" else None
    return f"Patalpa {nr}" if nr else "Patalpa"


def sentence_for(c: dict, rows: dict[str, dict] | None = None) -> str:
    """One correction row → one sentence. `rows`: the project's rows by id (`_rows_by_id`)."""
    rows = rows or {}
    source = str(c.get("source") or "")
    old, new = c.get("old_value"), c.get("new_value")

    if source == "eilute_teisinga":
        label, unit = _row_label(c, rows)
        return f"{label}: kiekį {_qty(new, unit)} patvirtinote kaip teisingą"
    if source == "eilute_kiekis":
        label, unit = _row_label(c, rows)
        return f"{label}: kiekį pakeitėte {lt_number(old) or '—'} → {_qty(new, unit)}"
    if source == "patalpa_patvirtinta":
        area = lt_number(new)
        return f"{_room(c)}: plotą {area} m² patvirtinote" if area else f"{_room(c)}: patalpą patvirtinote"
    if source == "patalpa_pertvaros":
        def count(v):
            try:
                return str(int(round(float(v))))
            except (TypeError, ValueError):
                return "—"
        change = f"{count(old)} → {count(new)}"
        return f"{_room(c)}: pertvarų sienų atviroje erdvėje pakeitėte {change}"
    if source in ("klausimas_tinka", "klausimas_netinka"):
        qid = str(c.get("note") or ".".join(_path(c)[1:]) or "")
        topic = QUESTION_TOPICS.get(qid.split(":")[0])
        head = f"Klausimas apie {topic}" if topic else "Patikros klausimas"
        return f"{head}: {'priėmėte siūlymą' if source == 'klausimas_tinka' else 'atsakėte savaip'}"
    if source == "konturas":
        how = (new or {}).get("saltinis") if isinstance(new, dict) else None
        act = OUTLINE_ACTS.get(str(how or ""), "kontūrą pataisėte ranka")
        area = lt_number((new or {}).get("plotas_m2")) if isinstance(new, dict) else None
        tail = f" (pagal kontūrą {area} m²)" if area and how != "sujungta" else ""
        return f"{_room(c)}: {act}{tail}"
    if source == "atsaukta":
        # „Atšaukti" after an outline save (Pathon v3 W1-D, api/room_outline.py `_restore`)
        act = (new or {}).get("atsaukta") if isinstance(new, dict) else None
        what = UNDONE_ACTS.get(str(act or ""), "pakeitimą")
        return f"{_room(c)}: {what} atšaukėte"
    if source == "simbolis":
        parts = _path(c)
        page = parts[1] if len(parts) >= 3 else None
        klass = ".".join(parts[2:]) if len(parts) >= 3 else ""
        decision = (new or {}).get("sprendimas") if isinstance(new, dict) else None
        verb = "patvirtinote" if decision == "accept" else "atmetėte"
        where = f"Lapas {page}" if page else "Brėžinys"
        return f"{where}: rastą simbolį „{klass}“ {verb}" if klass else f"{where}: rastą simbolį {verb}"
    if source == "legenda":
        # „Pažymėti legendą" (Pathon v3 W2-B): one row per legend row he reviewed
        parts = _path(c)
        page = parts[1] if len(parts) >= 3 else None
        new_d = new if isinstance(new, dict) else {}
        old_d = old if isinstance(old, dict) else {}
        name = str(new_d.get("pavadinimas") or old_d.get("eilute") or "").strip()
        where = f"Lapas {page}" if page else "Brėžinys"
        what = f"legendos eilutę „{name}“" if name else "legendos eilutę"
        if new_d.get("sprendimas") == "accept":
            n = new_d.get("kiekis")
            tail = f" — {n} vnt." if isinstance(n, (int, float)) else ""
            gone = new_d.get("pasalinta")
            if isinstance(gone, (int, float)) and gone > 0:
                tail += f", {int(gone)} rastų pašalinote"
            return f"{where}: {what} patvirtinote{tail}"
        return f"{where}: {what} atmetėte"
    if source == "ivertinimas":
        # 👍 / 👎 (Pathon v3 W5-C, api/feedback.py): the paid read as a whole, or one found symbol
        v = new if isinstance(new, dict) else {}
        verdict = v.get("ivertinimas")
        parts = _path(c)
        if len(parts) >= 2 and parts[1] == "simbolis":
            where = f"Lapas {v.get('lapas')}" if v.get("lapas") else "Brėžinys"
            if verdict == "atsaukta":
                return f"{where}: „neieškoti tokių“ atšaukėte"
            return f"{where}: rastas ženklas tiko" if verdict == "taip" else f"{where}: rastą ženklą pažymėjote — neieškoti tokių"
        if verdict == "atsaukta":
            return "Brėžinio perskaitymo įvertinimą atšaukėte"
        return "Brėžinio perskaitymą įvertinote: tiko" if verdict == "taip" else "Brėžinio perskaitymą įvertinote: netiko"
    if source in ("pokalbis_taip", "pokalbis_ne"):
        return "Pokalbis: atsakymas tiko" if source == "pokalbis_taip" else "Pokalbis: atsakymas netiko"
    # Prielaidos and anything older: the setting, the room, before → after when both are numbers
    field = _path(c)[0]
    what = SETTING_NAMES.get(field)
    room = f"{_room(c)}: " if c.get("room_nr") else ""
    change = f" {lt_number(old)} → {lt_number(new)}" if lt_number(old) and lt_number(new) else ""
    text = f"{room}{what or 'nustatymą'} pakeitėte{change}"
    return text[:1].upper() + text[1:]


def journal(project: dict | None, corrections: list[dict]) -> list[dict]:
    """Every row with its `sentence` (scrubbed like every prose field on its way out)."""
    rows = _rows_by_id(project)
    out = []
    for c in corrections or []:
        sentence = _user_text.scrub_prose({"sentence": sentence_for(c, rows)})["sentence"]
        out.append({**c, "sentence": sentence})
    return out


CSV_COLUMNS = ("laikas", "patalpa", "laukas", "buvo", "tapo", "saltinis", "pastaba")
_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _csv_cell(value: Any) -> str:
    """A value as one CSV cell: numbers and text as they are, anything else as JSON. A TEXT cell that a
    spreadsheet would run as a formula gets a leading apostrophe (the export rule: user text is never a formula)."""
    import json

    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "'" + text if text.startswith(_FORMULA_LEADS) else text


def corrections_csv(corrections: list[dict]) -> str:
    """The correction corpus of one project as CSV text, oldest first, UTF-8 with a BOM so a spreadsheet reads
    the Lithuanian letters; columns `CSV_COLUMNS`."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for c in sorted(corrections or [], key=lambda r: (str(r.get("occurred_at") or ""), r.get("id") or 0)):
        writer.writerow([_csv_cell(c.get("occurred_at")), _csv_cell(c.get("room_nr")), _csv_cell(c.get("field_path")),
                         _csv_cell(c.get("old_value")), _csv_cell(c.get("new_value")), _csv_cell(c.get("source")),
                         _csv_cell(c.get("note"))])
    return "﻿" + buf.getvalue()
