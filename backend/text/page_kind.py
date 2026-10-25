"""Sheet kind from the sheet's own text — the title block first, then the page (v4 Phase 3c-2, plan §3.2 `page_kind`).

The reading used to take every sheet's kind from Pass-1, a model looking at the page images (`puslapiai[].tipas`);
the lanes pick their sheets by it (plans for the outlines, ceiling plans for the altitudes, sections for the
heights, plumbing / electrical sheets, finish sheets). Now the kind comes from the words the sheet writes about
itself — „LUBŲ PLANAS", „SANTECHNIKOS PLANAS", „SIENŲ IŠKLOTINĖS", „PJŪVIS 1-1" — read from the text layer (local
OCR behind `SAMATU_OCR` for a sheet without one). The title block (the lower right of the sheet,
`page_classifier._ANTSPAUDAS_BBOX`) is read first: a note on a plan that says „žr. išklotinėse" must not make the
plan an elevation. A title written backwards by the CAD export („sanalp sokinhcetnaS", objektas_b) is read too.

No title phrase → the layout decides what it can: a drawing sheet that writes dimension strings and room numbers
is a plan; anything else stays `unknown`, which every consumer treats as „read it" (fail open). A language model is
never asked to look at the sheet; `classify_text_with_model` may ask one to pick a kind from the sheet's TEXT, and
its answer is kept only when the words it cites stand in that text (text/schema_llm.py's guard).

    page_kinds(pdf_bytes) -> [{nr, tipas, saltinis: antspaudas|lapas|isdestymas|None, tekstas}]
    apply_text_page_kinds(parsed, pdf_bytes) -> how many sheets the text classified

The vocabulary is page_classifier.CANONICAL_TIPAI (prompt.py's), so every existing consumer reads it unchanged.
Never raises.
"""
from __future__ import annotations

import logging
import re
import unicodedata

log = logging.getLogger("samatu.page_kind")

TITLE_BOX = (0.40, 0.70, 1.00, 1.00)          # page_classifier._ANTSPAUDAS_BBOX — the LT title block
SOURCE_KEY = "tipas_saltinis"                 # puslapiai[i][...] — where the kind came from
MODEL_KIND_KEY = "tipas_modelio"              # the kind Pass-1 gave from the image, kept as evidence only
META_KEY = "lapu_rusys_is_teksto"             # parsed["_meta"][...] = {klasifikuota, lapu, rusys: {page: kind}} — rides
                                              # the recompute context, so the rows see the same kinds after an edit


def kinds_from_meta(parsed: dict) -> dict[int, str]:
    """{page: kind} the text gave, as stored in `_meta` (empty for a project read before v4 3c-2)."""
    meta = parsed.get("_meta") if isinstance(parsed, dict) else None
    rec = meta.get(META_KEY) if isinstance(meta, dict) else None
    out: dict[int, str] = {}
    for k, v in ((rec or {}).get("rusys") or {}).items() if isinstance(rec, dict) else ():
        try:
            out[int(k)] = str(v)
        except (TypeError, ValueError):
            continue
    return out


def fold(text) -> str:
    s = unicodedata.normalize("NFD", str(text or "").upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


# (kind, pattern) — a sheet TITLE: a short line of the sheet's text (≤ TITLE_MAX_WORDS words) that names the kind.
_STRONG: tuple[tuple[str, re.Pattern], ...] = (
    ("finish_schedule", re.compile(r"\bAPDAIL(OS|U) (PLANAS|ZINIARAST|SPECIFIKACIJ)|\bSIENU APDAIL")),
    ("wall_elevation", re.compile(r"\bISKLOTIN")),
    ("ceiling_plan", re.compile(r"\bLUBU (PLANAS|IRENGIMO|ISDESTYMO|SCHEMA)|\b(PAKABINAMU|ITEMPIAMU|ITEMPTU) LUBU\b")),
    ("plumbing", re.compile(r"\bSANTECHNIK\w* (PLANAS|SCHEMA|BREZINYS)|\bVANDENTIEKIO (PLANAS|SCHEMA)|\bVANDENS IVADU PLANAS"
                            r"|\bNUOTEKU (PLANAS|TINKL)"
                            r"|\bVANDENS IR NUOTEK|^SANTECHNIKA$")),
    ("electrical", re.compile(r"\b(ELEKTROS |APSVIETIMO |PRIRISIMO |ROZECIU |JUNGIKLIU |SVIESTUVU |SILPNU SROVIU )+"
                              r"(PLANAS|SCHEMA|ISDESTYMAS)\b|\bELEKTROTECHNIK")),
    ("section", re.compile(r"\bPJUVI(S|AI)\b")),
    ("facade", re.compile(r"\bFASADA(S|I)\b")),
    ("door_window_schedule", re.compile(r"\b(DURU|LANGU)( IR (DURU|LANGU))? (SPECIFIKACIJ|ZINIARAST)")),
    ("specification", re.compile(r"\bPRIETAISAI$")),
    ("floor_plan", re.compile(r"\bGRINDU (PLANAS|DANGOS|DANGU)|\bPERTVARU PLANAS|\b(AP)?MATAVIMU PLANAS"
                              r"|\bAUKSTO PLANAS|\bBALDU (PLANAS|ISDESTYM)|\bMONTUOJAMU PERTVARU|\bPATALPU PLANAS"
                              r"|\bPLANAS SU MATMEN|\bDEMONTUOJAMU|\bESAMOS BUKLES PLANAS|\bPLANAS$")),
)
# weak titles: only a line that IS the title („VIZUALIZACIJA", „SPECIFIKACIJA"), never a note that mentions one
_WEAK: tuple[tuple[str, re.Pattern], ...] = (
    ("non_relevant", re.compile(r"^(\d+\s*)?VIZUALIZACIJ\w*( \d+)?$")),
    ("specification", re.compile(r"^(\w+ )?SPECIFIKACIJ\w*$")),
    ("title_page", re.compile(r"^(TITULINIS|LAPU ZINIARASTIS|BREZINIU ZINIARASTIS|TURINYS)\b")),
)
TITLE_MAX_WORDS = 6
_NOTE = re.compile(r";$|\bZR\.|[()]|\bTIKSLIN|\bPAGAL\b|\bNUMATOM|\bKIEKI|\d+[,.]\d+ ?M\b")
_DIM = re.compile(r"^\d{3,5}$")                # a dimension string in millimetres
_ROOM_NR = re.compile(r"^\d{1,2}[.\-]\d{1,2}$|^[0-9]{3}$|^0\d$")


def _phrase_lines(pdf_bytes: bytes, page: int) -> list[tuple[str, float, float]] | None:
    """(folded text, x centre share, y centre share) per phrase of the sheet, every text direction, display frame
    (sheet_zones.read_phrases — PDFium; a title block written turned 90° reads as words, which pdfplumber splits
    into single letters on objektas_g). None when the sheet has no readable text that way."""
    try:
        from extractor.sheet_zones import display_frame, read_phrases
        fr = display_frame(pdf_bytes, page)
        if fr is None:
            return None
        W, H = float(fr[0]) or 1.0, float(fr[1]) or 1.0
        phrases, n_chars, _ok = read_phrases(pdf_bytes, page, (fr[0], fr[1]))
        if not phrases or n_chars < 8:
            return None
        return [(fold(ph.get("text")), (float(ph["x0"]) + float(ph["x1"])) / 2 / W,
                 (float(ph["top"]) + float(ph["bottom"])) / 2 / H) for ph in phrases]
    except Exception:  # noqa: BLE001
        log.debug("page_kind phrases failed p%s", page, exc_info=True)
        return None


def _lines(sig: dict) -> list[tuple[str, float, float]]:
    """(folded text, x centre share, y centre share) per text line: words on one baseline, next to each other."""
    W, H = float(sig.get("width") or 0) or 1.0, float(sig.get("height") or 0) or 1.0
    words = sorted((w for w in sig.get("words") or [] if str(w.get("text") or "").strip()),
                   key=lambda w: (round(float(w.get("top") or 0) / 2.0), float(w.get("x0") or 0)))
    out: list[tuple[str, float, float]] = []
    cur: list[dict] = []

    def flush():
        if cur:
            x0, x1 = min(float(w["x0"]) for w in cur), max(float(w["x1"]) for w in cur)
            t0, t1 = min(float(w["top"]) for w in cur), max(float(w["bottom"]) for w in cur)
            out.append((fold(" ".join(str(w["text"]) for w in cur)), (x0 + x1) / 2 / W, (t0 + t1) / 2 / H))
    for w in words:
        if cur:
            last = cur[-1]
            same = abs(float(w["top"]) - float(cur[0]["top"])) <= 2.0
            near = float(w["x0"]) - float(last["x1"]) <= 3.0 * max(1.0, float(last["bottom"]) - float(last["top"]))
            if not (same and near):
                flush()
                cur = []
        cur.append(w)
    flush()
    return out


def _in_title_block(x: float, y: float) -> bool:
    """The LT title block: the lower right of the sheet, or the strip along its right edge (objektas_b)."""
    return (x >= TITLE_BOX[0] and y >= TITLE_BOX[1]) or x >= 0.88


def _title_kind(lines: list[tuple[str, float, float]]) -> tuple[str | None, str | None, str | None]:
    """(kind, the title words, saltinis) from the sheet's short lines: a title in the title block first, else a
    title anywhere on the sheet; strong kinds before the weak ones."""
    best = None
    for text, x, y in lines:
        for cand in (text, text[::-1]):
            n_words = len(cand.split())
            if not cand or n_words > TITLE_MAX_WORDS or _NOTE.search(cand):
                continue
            for rank, rules in ((0, _STRONG), (1, _WEAK)):
                for prio, (kind, rx) in enumerate(rules):
                    m = rx.search(cand)
                    if not m:
                        continue
                    key = (rank, 0 if _in_title_block(x, y) else 1, prio)
                    if best is None or key < best[0]:
                        best = (key, kind, cand, "antspaudas" if key[1] == 0 else "lapas")
                    break
    if best is None:
        return None, None, None
    return best[1], best[2], best[3]


def _layout_kind(sig: dict) -> tuple[str | None, str | None]:
    """A drawing that writes dimension strings and room numbers is a plan (the layout, not a title)."""
    words = [str(w.get("text") or "").strip() for w in sig.get("words") or []]
    dims = sum(1 for w in words if _DIM.match(w))
    rooms = sum(1 for w in words if _ROOM_NR.match(w))
    if dims >= 12 and rooms >= 3:
        return "floor_plan", f"{dims} matmenų, {rooms} patalpų numerių"
    return None, None


def _ocr_signal(pdf_bytes: bytes, page: int, sig: dict) -> dict:
    """A sheet without a text layer, read by local OCR behind `SAMATU_OCR` into the same shape (words with
    boxes in points); the sheet as it was when OCR is off or fails."""
    try:
        from .ocr import ocr_enabled, ocr_page
        if not ocr_enabled():
            return sig
        W, H, words = ocr_page(pdf_bytes, page)
        ws = [{"text": str(w.text), "x0": float(w.x0), "top": float(w.y0), "x1": float(w.x1), "bottom": float(w.y1)}
              for w in words if str(getattr(w, "text", "") or "").strip()]
        return {"text": " ".join(w["text"] for w in ws), "words": ws, "width": float(W), "height": float(H)}
    except Exception:  # noqa: BLE001 — no OCR is no text, never a failure
        log.debug("page_kind OCR failed p%s", page, exc_info=True)
        return sig


def page_kinds(pdf_bytes: bytes) -> list[dict]:
    """One entry per sheet, in order: {nr, tipas, saltinis, tekstas}. Never raises."""
    out: list[dict] = []
    try:
        from extractor.pdf_page_cache import page_signals
        sigs = page_signals(pdf_bytes)
    except Exception:  # noqa: BLE001
        return out
    for i, sig in enumerate(sigs):
        nr = i + 1
        if len(str(sig.get("text") or "").strip()) < 8:
            sig = _ocr_signal(pdf_bytes, nr, sig)
        kind, said, source = _title_kind(_phrase_lines(pdf_bytes, nr) or _lines(sig))
        if not kind and _phrase_lines(pdf_bytes, nr):
            kind, said, source = _title_kind(_lines(sig))
        if not kind:
            kind, said = _layout_kind(sig)
            source = "isdestymas" if kind else None
        out.append({"nr": nr, "tipas": kind or "unknown", "saltinis": source, "tekstas": said})
    return out


def apply_text_page_kinds(parsed: dict, pdf_bytes: bytes) -> int:
    """Set `parsed["puslapiai"][i]["tipas"]` from the sheet's text (page_kinds). The kind Pass-1 gave from the
    image is kept beside it as `tipas_modelio` (evidence only — no lane reads it); a sheet the text does not
    classify becomes `unknown` (fail open: the lanes read it). Sheets Pass-1 never listed are added. Returns how
    many sheets the text classified. Never raises."""
    try:
        kinds = page_kinds(pdf_bytes)
        if not kinds:
            return 0
        old = {}
        for p in parsed.get("puslapiai") or []:
            if isinstance(p, dict):
                try:
                    old[int(p.get("nr") or p.get("page") or p.get("puslapis"))] = p
                except (TypeError, ValueError):
                    continue
        rows = []
        n = 0
        for k in kinds:
            row = dict(old.get(k["nr"]) or {"nr": k["nr"]})
            row.setdefault("nr", k["nr"])
            if MODEL_KIND_KEY not in row and row.get("tipas") is not None and row.get(SOURCE_KEY) is None:
                row[MODEL_KIND_KEY] = row.get("tipas")
            row["tipas"] = k["tipas"]
            row[SOURCE_KEY] = k["saltinis"]
            if k["tekstas"]:
                row["tipas_tekstas"] = k["tekstas"]
            n += 1 if k["saltinis"] else 0
            rows.append(row)
        parsed["puslapiai"] = rows
        parsed.setdefault("_meta", {})[META_KEY] = {"klasifikuota": n, "lapu": len(rows),
                                                    "rusys": {str(k["nr"]): k["tipas"] for k in kinds}}
        return n
    except Exception:  # noqa: BLE001
        log.warning("apply_text_page_kinds failed", exc_info=True)
        return 0
