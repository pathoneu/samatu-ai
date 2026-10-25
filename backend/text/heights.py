"""Ceiling heights from the drawing's TEXT — one reader, used by the paid reading, the free re-read and the eval
(v4 Phase 3c-1, 2026-10-25; plan 2026-10-24 §3.2, rules R3 / R7).

Before this module the reading model's heights were the default and the text only corrected them: Pass-1's
project height and its per-room map (`lubu_auksciai`) were applied, a section marker counted only when it
agreed with Pass-1 or was taller than 2,95 m, a ceiling-plan altitude could only RAISE a model height, and a
plan statement reached only a room still carrying our 2,82 m default. Phase 3b then blanked every height the
text had not confirmed. Here the order is turned round: the text is read first, the model is never asked.

`apply_text_heights(parsed, pdf_bytes)`:

  1. Every room's height that is not his (`_overrides.lubu_auksciai`, `user_override` / `manual`) is taken off
     the room; a model figure is kept as `_lubu_aukstis_modelio` (shown nowhere, used by nothing).
  2. Per room, where the drawing says so (first that applies):
       - an altitude printed inside the room on the ceiling plan (`height_markers.apply_positioned_marker_heights`
         → `ceiling_plan_marker`; the only height that also counts for a GKP ceiling, Phase 3b);
       - the room table's own height column, when the table was read from the text layer
         (`patalpu_lentele`);
       - a height the plan writes for ONE room („Lubų aukštis H=2700" in the room's block, a bare „H - 2820"
         beside the room's own label inside its outline — `plan_area_annotations.apply_height_statements`
         → `plano_uzrasas`).
  3. Per project otherwise — one rule, the first that has anything to say; when its values disagree no height
     is taken and the candidates are listed (never a weaker rule after a stronger one disagreed):
       - a ceiling-worded statement tied to no single room („Lubų aukštis 2,80 m", „patalpų aukštis 2700");
       - the altitude markers of the sections / elevations („+2.800") when they give ONE value in 2,2–4,5 m;
       - bare height stamps tied to no room („H - 2820"), when every one gives the same value.
     The rooms without a height of their own take it as `projekto_aukstis` (a read source of its own, so it
     survives the free re-read's room merge); the project carries `lubu_aukstis_m` + `_lubu_aukstis_saltinis =
     pjuvio_zymuo` as before.
  4. Nothing written: the room keeps no height; `row_provenance.fill_heights_from_read` (run after this) gives
     it the height read in the other rooms, else the one question „Kokio aukščio lubos?" stays (unchanged).

Every room with a height carries `aukstis_saltinis` = {kaip, lapas, tekstas} — which rule, on which sheet, which
string; `_meta.aukstis_tekstas` summarises the project (its height and rule, the candidates, the sheets read by
OCR, the seconds). Behind `SAMATU_OCR` a sheet with no text layer is read by local OCR (text/ocr.py) for the
statements and the section markers; with the flag off nothing is rendered.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any, Callable, Iterable

TABLE_SOURCE = "patalpu_lentele"
MARKER_SOURCE = "ceiling_plan_marker"
STATEMENT_SOURCE = "plano_uzrasas"
PROJECT_ROOM_SOURCE = "projekto_aukstis"     # the storey height the text writes, on a room with none of its own
NONE_SOURCE = "nera"
HUMAN_SOURCES = ("user_override", "manual")
TEXT_TABLE_SOURCES = ("pdfplumber_table", "ocr_table")
MODEL_KEY = "_lubu_aukstis_modelio"
PROVENANCE_KEY = "aukstis_saltinis"
META_KEY = "aukstis_tekstas"
# page kinds whose altitude markers state the storey (prompt.py vocabulary via page_classifier.canonical_tipas)
SECTION_KINDS = frozenset({"section", "facade", "wall_elevation"})
MIN_M, MAX_M = 2.2, 4.5
MIN_LAYER_CHARS = 8                        # text/layer.py: fewer visible characters = no text layer

# Rule names as they appear in `aukstis_saltinis.kaip` and `_meta.aukstis_tekstas.projektas.kaip`.
KAIP_MARKER = "lubu_plano_altitude"
KAIP_TABLE = "patalpu_lentele"
KAIP_STATEMENT = "plano_uzrasas"
KAIP_PROJECT_STATEMENT = "uzrasas_visam_aukstui"
KAIP_PROJECT_SECTION = "pjuvio_altitude"
KAIP_PROJECT_STAMP = "plano_zyma_visam_aukstui"
KAIP_HIS = "jusu_irasas"

# Keys an earlier read left on a room; a re-read decides them again.
_STALE_ROOM_KEYS = ("_height_source", "_height_marker_evidence", "_height_marker_m", "_height_marker_conflict",
                    "_height_marker_lower_ignored", "_lubu_aukstis_uzrasas", PROVENANCE_KEY)
# Sources that are a text reading of ours (re-read every time) or our own placeholder — not the model's figure.
_OURS = (TABLE_SOURCE, MARKER_SOURCE, STATEMENT_SOURCE, PROJECT_ROOM_SOURCE, "section_average", "kaip_kitose", NONE_SOURCE, "",
         "default_fallback", "height_gate_reattributed", "height_gate_clamped", "warning_salvage_rescore")
_MODEL_MAPS = ("lubu_auksciai", "lubu_auksciai_by_nr")

# „lubų aukštis 2,8 m", „Patalpų aukštis – 2700 mm", „lubu aukstis (svarus) h 2750" — on folded text.
_PHRASE_RE = re.compile(
    r"(?<![^\W\d_])(?:lubu|patalp\w*)\s+auksti\w*\s*(?:\([^)]{0,20}\)\s*)?[-–:=]?\s*(?:h\s*[-–:=]?\s*)?"
    r"(\d{4}|\d[.,]\d{1,3})\s*(mm|cm|m)?(?![\w])")
# the separator form of a section altitude („+2.800", „±2,750") — height_markers._HEIGHT_MARKER_RE
_ALTITUDE_RE = re.compile(r"(?<![\w.,])[+±]\s*(\d+[.,]\d{1,3})(?![\d.,\w])")


def _f(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def _metres(token: str, unit: str | None = None) -> float | None:
    v = _f(str(token).replace(",", "."))
    if v is None:
        return None
    if unit == "cm":
        v /= 100.0
    elif unit == "mm" or v > 100:
        v /= 1000.0
    v = round(v, 3)
    return v if MIN_M <= v <= MAX_M else None


def _lt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",") if v is not None else ""


# ── the drawing's text, page by page ─────────────────────────────────────────

def _page_texts(pdf_bytes: bytes) -> list[str]:
    """Each page's text layer (the shared, cached parse — pdf_page_cache)."""
    try:
        from extractor.pdf_page_cache import page_signals
        return [str(s.get("text") or "") for s in (page_signals(pdf_bytes) or [])]
    except Exception:  # noqa: BLE001 — no text is „nothing written", never a failure
        return []


def _ocr_items(pdf_bytes: bytes, texts: list[str]) -> tuple[list[tuple], list[int]]:
    """Behind SAMATU_OCR: the (page, W, H, chars, to_display) items of the sheets with no text layer, read by
    local OCR. Flag off → nothing rendered."""
    try:
        from text.ocr import ocr_enabled, ocr_page_items
    except Exception:  # noqa: BLE001
        return [], []
    if not ocr_enabled():
        return [], []
    items: list[tuple] = []
    pages: list[int] = []
    for i, t in enumerate(texts, 1):
        if sum(1 for ch in t if not ch.isspace()) >= MIN_LAYER_CHARS:
            continue
        try:
            got = ocr_page_items(pdf_bytes, i)
        except Exception:  # noqa: BLE001 — one unreadable sheet never sinks the read
            got = []
        if got:
            items.extend(got)
            pages.append(i)
    return items, pages


def _item_lines(item: tuple) -> list[str]:
    from extractor.plan_area_annotations import _line_text_mapped, _lines
    return [_line_text_mapped(line)[0] for line in _lines(item[3])]


def phrase_statements(page_lines: Iterable[tuple[int, str]], rooms: list[dict]) -> list[dict]:
    """„lubų aukštis 2,8 m" in a note or a legend: [{page, value_m, text, room}] — `room` is the ONE room the
    same line names (its name, whole word), else None (a statement for the storey)."""
    from extractor.plan_area_annotations import _fold
    names: dict[str, list[dict]] = {}
    for r in rooms:
        nm = " ".join(_fold(r.get("pavadinimas") or "").split())
        if len(nm) >= 2:
            names.setdefault(nm, []).append(r)
    out: list[dict] = []
    for page, line in page_lines:
        folded = _fold(line)
        for m in _PHRASE_RE.finditer(folded):
            v = _metres(m.group(1), m.group(2))
            if v is None:
                continue
            named = [rs[0] for nm, rs in names.items() if len(rs) == 1
                     and re.search(r"(?<![^\W_])" + re.escape(nm) + r"(?![^\W_])", folded)]
            out.append({"page": page, "value_m": v, "text": line.strip()[:80],
                        "room": named[0] if len(named) == 1 else None})
    return out


def altitude_markers(page_lines: Iterable[tuple[int, str]]) -> list[dict]:
    """„+2.800" markers in the storey range: [{page, value_m, text}]."""
    out = []
    for page, line in page_lines:
        for m in _ALTITUDE_RE.finditer(line):
            v = _metres(m.group(1), "m")
            if v is not None:
                out.append({"page": page, "value_m": v, "text": m.group(0).strip()})
    return out


def _page_kinds(parsed: dict) -> dict[int, str]:
    try:
        from extractor.page_classifier import canonical_tipas
    except Exception:  # noqa: BLE001
        return {}
    out: dict[int, str] = {}
    for p in parsed.get("puslapiai") or []:
        if not isinstance(p, dict):
            continue
        n = _f(p.get("nr") or p.get("page") or p.get("puslapio_nr"))
        if n:
            out[int(n)] = canonical_tipas(p.get("tipas") or p.get("type"))
    return out


# ── the project's height: one rule, the first with anything to say ───────────

def project_height(*, untied_ceiling: list[dict], markers: list[dict], untied_stamps: list[dict],
                   kinds: dict[int, str]) -> tuple[dict | None, list[dict]]:
    """(the project's height {value_m, kaip, lapas, tekstas} or None, the candidates when a rule disagreed)."""
    section_pages = {p for p, k in kinds.items() if k in SECTION_KINDS}
    ceiling_pages = {p for p, k in kinds.items() if k == "ceiling_plan"}
    if section_pages:
        markers = [m for m in markers if m["page"] in section_pages]
    else:                         # no classification of sections: every sheet but the ceiling plans (per-room)
        markers = [m for m in markers if m["page"] not in ceiling_pages]
    for kaip, found in ((KAIP_PROJECT_STATEMENT, untied_ceiling), (KAIP_PROJECT_SECTION, markers),
                        (KAIP_PROJECT_STAMP, untied_stamps)):
        if not found:
            continue
        values = sorted({round(float(s["value_m"]), 3) for s in found})
        if len(values) == 1:
            first = found[0]
            return ({"value_m": values[0], "kaip": kaip, "lapas": first.get("page"),
                     "tekstas": str(first.get("text") or "")[:80], "kiek": len(found)}, [])
        cands = [{"value_m": v, "kaip": kaip,
                  "lapai": sorted({s.get("page") for s in found if round(float(s["value_m"]), 3) == v}),
                  "tekstas": next(str(s.get("text") or "") for s in found if round(float(s["value_m"]), 3) == v)[:80]}
                 for v in values]
        return None, cands
    return None, []


# ── the one entry point ──────────────────────────────────────────────────────

def apply_text_heights(parsed: dict, pdf_bytes: bytes | None, *, statements: list[dict] | None = None,
                       emit: Callable[[dict], None] | None = None) -> dict:
    """Read the ceiling heights from the drawing's text onto `parsed`'s rooms (module doc). `statements`: the
    H-stamps the caller's text scan already read (`scan_text_layer(...)["heights"]`), else they are read here.
    Mutates `parsed`; returns the summary also written to `_meta.aukstis_tekstas`. Never raises."""
    t0 = time.time()
    try:
        return _apply(parsed, pdf_bytes, statements, emit, t0)
    except Exception as exc:  # noqa: BLE001 — a height reader never sinks the reading; the rooms stay unread
        summary = {"status": "failed", "error": repr(exc)[:200], "sekundes": round(time.time() - t0, 2)}
        parsed.setdefault("_meta", {})[META_KEY] = summary
        return summary


def _apply(parsed: dict, pdf_bytes: bytes | None, statements, emit, t0: float) -> dict:
    from extractor import row_provenance as rp
    from extractor.plan_area_annotations import _height_statements_on_page, _tie_statement, apply_height_statements

    rooms = [r for r in parsed.get("patalpos") or [] if isinstance(r, dict)]
    his = rp.own_heights(parsed)

    # 1 — every height that is not his comes off; the model's figure is kept aside, used by nothing
    for r in rooms:
        for k in _STALE_ROOM_KEYS:
            r.pop(k, None)
        src = str(r.get("lubu_aukstis_saltinis") or "").strip().lower()
        if _nr(r) in his or src in HUMAN_SOURCES:
            r[PROVENANCE_KEY] = {"kaip": KAIP_HIS}
            continue
        h = _f(r.get("lubu_aukstis_m"))
        if h and src not in _OURS:
            r.setdefault(MODEL_KEY, h)
            r.setdefault(MODEL_KEY + "_saltinis", src)    # which rooms the zoom pass re-reads (vision_call)
        r["lubu_aukstis_m"] = None
        r["lubu_aukstis_saltinis"] = NONE_SOURCE
    for key in _MODEL_MAPS:                       # the reading model's per-room maps: evidence, never applied
        if parsed.get(key):
            parsed.setdefault(f"_{key}_modelio", parsed[key])
        parsed.pop(key, None)
    if parsed.get("_lubu_aukstis_saltinis") != rp.PROJECT_HEIGHT_FROM_TEXT and _f(parsed.get("lubu_aukstis_m")):
        parsed.setdefault("_lubu_aukstis_modelio", parsed.get("lubu_aukstis_m"))
    parsed.pop("_lubu_aukstis_saltinis", None)
    parsed["warnings"] = [w for w in parsed.get("warnings") or []
                          if not (isinstance(w, dict) and w.get("code") == rp.SECTION_MARKER_WARNING)]

    open_rooms = lambda: [r for r in rooms if r.get("lubu_aukstis_saltinis") == NONE_SOURCE]  # noqa: E731
    # his rooms stay exactly as he left them: the readers below see every room (a neighbour's label decides
    # which room a marker belongs to) and anything they write on his is put back
    his_rooms = {id(r): {k: r.get(k) for k in ("lubu_aukstis_m", "lubu_aukstis_saltinis")}
                 for r in rooms if (r.get(PROVENANCE_KEY) or {}).get("kaip") == KAIP_HIS}

    def put_his_back() -> None:
        for r in rooms:
            kept = his_rooms.get(id(r))
            if kept is None:
                continue
            r.update(kept)
            for k in _STALE_ROOM_KEYS:
                r.pop(k, None)
            r[PROVENANCE_KEY] = {"kaip": KAIP_HIS}
    texts = _page_texts(pdf_bytes) if pdf_bytes else []
    ocr_items, ocr_pages = _ocr_items(pdf_bytes, texts) if pdf_bytes else ([], [])
    kinds = _page_kinds(parsed)

    # 2a — altitudes printed inside the rooms on the ceiling plan
    marker_lane = None
    if pdf_bytes and open_rooms():
        from extractor.height_markers import apply_positioned_marker_heights
        apply_positioned_marker_heights(parsed, pdf_bytes, emit=emit)
        marker_lane = parsed.get("_height_marker_lane") or {}
    put_his_back()
    for r in rooms:
        if r.get("lubu_aukstis_saltinis") == MARKER_SOURCE:
            ev = r.get("_height_marker_evidence") if isinstance(r.get("_height_marker_evidence"), dict) else {}
            raw = (ev.get("markers") or [None])[0] or f"+{_lt(_f(r.get('lubu_aukstis_m')))}"
            r[PROVENANCE_KEY] = {"kaip": KAIP_MARKER, "lapas": ev.get("page"), "tekstas": str(raw)}

    # 2b — the room table's own height column (a table read from the text layer only)
    eks = parsed.get("_eksplikacija") if isinstance(parsed.get("_eksplikacija"), dict) else {}
    eks_source = str(((eks.get("_meta") or {}) if isinstance(eks.get("_meta"), dict) else {}).get("source") or "")
    n_table = 0
    if eks_source in TEXT_TABLE_SOURCES:
        rows = [row for row in eks.get("patalpos") or [] if isinstance(row, dict) and _metres(str(row.get("lubu_aukstis_m") or ""), "m")]
        by_idx = {row.get("row_idx"): row for row in rows if row.get("row_idx") is not None}
        by_nr: dict[str, list[dict]] = {}
        for row in rows:
            by_nr.setdefault(str(row.get("nr") or "").strip(), []).append(row)
        for r in open_rooms():
            row = by_idx.get(r.get("eksplikacija_row_idx"))
            if row is None:
                cand = by_nr.get(_nr(r)) or []
                row = cand[0] if len(cand) == 1 else None
            if row is None:
                continue
            v = _metres(str(row.get("lubu_aukstis_m")), "m")
            r["lubu_aukstis_m"] = v
            r["lubu_aukstis_saltinis"] = TABLE_SOURCE
            r[PROVENANCE_KEY] = {"kaip": KAIP_TABLE, "lapas": row.get("page") or eks.get("eksplikacija_source_page"),
                                 "tekstas": str(row.get("lubu_aukstis_m_raw") or _lt(v))}
            n_table += 1

    # 2c — a height the plan writes for ONE room (H-stamps; and „lubų aukštis …" naming one room)
    if statements is None and pdf_bytes:
        from extractor.plan_area_annotations import read_height_statements
        statements = read_height_statements(pdf_bytes)
    stamps = list(statements or [])
    for item in ocr_items:
        try:
            stamps.extend(_height_statements_on_page(*item))
        except Exception:  # noqa: BLE001
            continue
    stmt_status = apply_height_statements(rooms, stamps) if stamps else {"status": "none", "rooms": []}
    put_his_back()
    for r in rooms:
        uz = r.get("_lubu_aukstis_uzrasas")
        if r.get("lubu_aukstis_saltinis") == STATEMENT_SOURCE and isinstance(uz, dict):
            r[PROVENANCE_KEY] = {"kaip": KAIP_STATEMENT, "lapas": uz.get("page"), "tekstas": uz.get("text")}
    lines = [(i, ln) for i, t in enumerate(texts, 1) for ln in t.splitlines()]
    lines += [(int(it[0]), ln) for it in ocr_items for ln in _item_lines(it)]
    # a phrase the H-stamp reader already read (same sheet, same value) is that stamp: the stamp knows where it
    # stands and which room it belongs to, the bare line does not
    stamp_keys = {(int(_f(s.get("page")) or 0), round(float(s["value_m"]), 3)) for s in stamps if _f(s.get("value_m"))}
    phrases = [p for p in phrase_statements(lines, rooms) if (p["page"], round(p["value_m"], 3)) not in stamp_keys]
    for p in phrases:
        r = p.get("room")
        if r is not None and r.get("lubu_aukstis_saltinis") == NONE_SOURCE:
            r["lubu_aukstis_m"] = p["value_m"]
            r["lubu_aukstis_saltinis"] = STATEMENT_SOURCE
            r[PROVENANCE_KEY] = {"kaip": KAIP_STATEMENT, "lapas": p["page"], "tekstas": p["text"]}

    # 3 — the project's height for the rooms the drawing gives none of their own
    untied_ceiling = [{"page": p["page"], "value_m": p["value_m"], "text": p["text"]} for p in phrases if p.get("room") is None]
    untied_stamps: list[dict] = []
    for s in stamps:
        kind, room = _tie_statement(s, rooms)
        if kind == "element" or room is not None:
            continue
        (untied_ceiling if s.get("ceiling") else untied_stamps).append(s)
    project, candidates = project_height(untied_ceiling=untied_ceiling, markers=altitude_markers(lines),
                                         untied_stamps=untied_stamps, kinds=kinds)
    if project is not None:
        parsed["lubu_aukstis_m"] = project["value_m"]
        parsed["_lubu_aukstis_saltinis"] = rp.PROJECT_HEIGHT_FROM_TEXT
        for r in open_rooms():
            r["lubu_aukstis_m"] = project["value_m"]
            r["lubu_aukstis_saltinis"] = PROJECT_ROOM_SOURCE
            r[PROVENANCE_KEY] = {"kaip": project["kaip"], "lapas": project["lapas"], "tekstas": project["tekstas"]}
        parsed.setdefault("warnings", []).append({
            "code": rp.SECTION_MARKER_WARNING, "severity": "info",
            "message": (f"Lubų aukštis paimtas iš brėžinio užrašo „{project['tekstas']}“: {_lt(project['value_m'])} m"
                        + (f" (lapas {project['lapas']})" if project.get("lapas") else "")
                        + ". Jei kurios patalpos aukštis kitas, pakeiskite jį „Nustatymuose“."),
        })

    per_room = {_nr(r): (r.get(PROVENANCE_KEY) or {}).get("kaip") for r in rooms if r.get(PROVENANCE_KEY)}
    summary = {
        "status": "read" if per_room else "nothing_written",
        "projektas": project,
        "kandidatai": candidates,
        "patalpos": per_room,
        "be_aukscio": [_nr(r) for r in open_rooms()],
        "pagal_taisykle": dict(Counter(v for v in per_room.values() if v)),
        "lentele": n_table,
        "zymos_lane": {k: (marker_lane or {}).get(k) for k in ("ok", "method", "reason")} if marker_lane is not None else None,
        "uzrasai": {k: v for k, v in stmt_status.items() if k != "rooms"},
        "ocr_lapai": ocr_pages,
        "sekundes": round(time.time() - t0, 2),
    }
    parsed.setdefault("_meta", {})[META_KEY] = summary
    if emit:
        try:
            emit({"event": "heights_from_text", "project": (project or {}).get("value_m"),
                  "rooms_read": len(per_room), "rooms_without": len(summary["be_aukscio"])})
        except Exception:  # noqa: BLE001
            pass
    return summary
