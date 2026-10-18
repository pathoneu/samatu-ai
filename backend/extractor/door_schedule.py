"""Deterministic DOOR-SCHEDULE scanner ($0, no Vision call) — what the drawing's own text says about
the doors: a „Durų žiniaraštis" table (codes, sizes, frame type, counts), the openings annotated for
frameless doors on the plan, a governing note, and the door products named on a finish board.

WHY (2026-09-23, the founder: „kiek durų su apvadais žiniaraštis rodo? patikrink durų žiniaraščio skaitymą").
Checked across the six contractor projects:

    objektas_d  „Vidinių angų (durų) žiniaraštis" — D-1, D-2, 910×2100, both „beapvadinės";
                note „Durų staktas ruošti beapvadinėms durims"        → the table IS the answer:
                2 × (0,91 + 2 × 2,10) = 10,22 m, his row to the centimetre
    objektas_a  no table; two openings annotated „Durų anga iki lubų, skirta beapvadinėms durims"
                (the LD-1/LD-2/LD-3 tags the Vision reader took for door tags are curtain-niche details
                on the ceiling plan)                                   → annotations, no total
    objektas_g  no table; the finish board names the door PRODUCTS („… vidaus durys …", three models
                with casings), frameless doors mentioned nowhere         → framed doors
    objektas_b, objektas_c, objektas_h — nothing about door types in the text at all

So the frame type is a TEXT fact when it is anywhere at all, and this scanner reads it without a model:
a table is parsed from word positions (pdfplumber), the plan is counted for each code, annotations and
notes are counted per page. The result feeds `universal_rules.settle_frameless_default` (the project
assumption with its evidence) and `reconcile_doors_with_schedule` (the door list capped and sized by the
table), and the sentence is shown to the person. Never raises.
"""
from __future__ import annotations

import io
import re

# a schedule heading: „Durų žiniaraštis", „Vidinių angų (durų) žiniaraštis", „Durų specifikacija", „Durų lentelė"
_HEADING_RE = re.compile(
    r"(?:dur\w*[^\n]{0,40}(?:žiniarašt|ziniarast|specifikac|lentel|sąraš|saras)|"
    r"(?:žiniarašt|ziniarast|specifikac)\w*[^\n]{0,40}dur)", re.IGNORECASE)
# a door code word in the table and on the plan: D-1, D1, D-12, VD-1, ID-2 (LD-1 is a ceiling/niche detail)
_CODE_RE = re.compile(r"^(?:D|VD|ID|DV)-?\d{1,2}\*?$")
_CODE_TEXT_RE = re.compile(r"(?<![A-Za-z])(?:D|VD|ID|DV)-?\d{1,2}(?![\d\w])")
# frame vocabulary. The negation is matched with or without its space („beapvadinės", „be apvadų") and is
# tested FIRST: the framed word is looked for only in what is left once the frameless phrases are taken out —
# before 2026-10-03 „be apvadų" read as framed, because a look-behind for „be" does not see „be ".
_FRAMELESS_RE = re.compile(r"be\s*apvad|paslėpt\w*\s+(?:dur|stakt)|paslept\w*\s+(?:dur|stakt)|nematom\w*\s+stakt|"
                           r"filo\s*muro|invisible", re.IGNORECASE)
_FRAMED_RE = re.compile(r"apvad", re.IGNORECASE)
_SLIDING_RE = re.compile(r"stumdom|slankio", re.IGNORECASE)
_GLASS_RE = re.compile(r"stiklin", re.IGNORECASE)
# a door size written as one token or with a sign between: „910x2100", „910 × 2100", „910*2100"
_SIZE_RE = re.compile(r"(?<!\d)(\d{3,4})\s*[x×X*]\s*(\d{3,4})(?!\d)")
# annotations at openings and governing notes
_ANNOTATION_RE = re.compile(r"be\s*apvadin\w*\s+durims|skirta\s+be\s*apvadin|durims\s+be\s+apvad", re.IGNORECASE)
_NOTE_ALL_RE = re.compile(r"visos\s+vidaus\s+durys[^.\n]{0,60}be\s*apvad", re.IGNORECASE)
_NOTE_PREP_RE = re.compile(r"stakt\w*\s+ruošti\s+be\s*apvadin|stakt\w*\s+ruosti\s+be\s*apvadin", re.IGNORECASE)
_SLIDING_NOTE_RE = re.compile(r"\d+\s*\.\s*stumdom\w*\s+durys", re.IGNORECASE)
# a door product named on a finish board: „DECO-10 vidaus durys, nashville oak"
_PRODUCT_RE = re.compile(r"((?:[^\s,;:()]+\s+){1,2})vidaus\s+durys", re.IGNORECASE)
_NUM_RE = re.compile(r"^\d{3,4}$")
MIN_TEXT_CHARS = 200
_MAX_ROWS = 40
_LINE_PT = 3.0             # words of one table line start within this of each other (`_reading_order`)
AMBIGUOUS = "neaisku"      # a row that names the doors frameless AND framed — never settled by this reader


def _empty(text_ok: bool) -> dict:
    return {"status": "nera", "text_layer_ok": text_ok, "pages": [], "lentele": None,
            "beapvadines": 0, "su_apvadais": 0, "stumdomos": 0, "kitos": 0, "neaiskios": 0, "neaiskus_kodai": [],
            "anotacijos_beapvadines": 0, "pastaba_visos": False, "pastaba_beapvadines": False,
            "stumdomos_pastaba": False, "gaminiai": [], "sakinys": ""}


def _row_type(text: str) -> str:
    t = text or ""
    frameless = bool(_FRAMELESS_RE.search(t))
    framed = bool(_FRAMED_RE.search(_FRAMELESS_RE.sub(" ", t)))
    if frameless and framed:
        # „be apvadų" and „su apvadais" on one row (two door kinds in one cell, or the next row's words
        # pulled in) — counted as neither, and the sentence asks him to check that code
        return AMBIGUOUS
    if frameless:
        return "beapvadines"
    if _SLIDING_RE.search(t):
        return "stumdomos"
    if _GLASS_RE.search(t):
        return "stiklines"
    if framed:
        return "su_apvadais"
    return "nezinoma"


def _row_size(text: str, cells: list[dict]) -> tuple[int | None, int | None]:
    """Width and height in mm: a „910x2100" token first (one word, or with the sign standing apart), else
    the first two plausible numbers of the row in reading order."""
    m = _SIZE_RE.search(text or "")
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if 400 <= w <= 4000 and 400 <= h <= 4000:
            return w, h
    nums = [int(w["text"]) for w in cells if _NUM_RE.match(w["text"]) and 400 <= int(w["text"]) <= 4000]
    return (nums[0] if nums else None), (nums[1] if len(nums) > 1 else None)


def _reading_order(words: list[dict]) -> list[dict]:
    """Words line by line, left to right. A line is a sweep over `top` (within _LINE_PT of its first word),
    not a rounding bucket: a word with a taller glyph („ų", „š") starts a point higher than its neighbours,
    and a bucket edge between them put „be" after „apvadų" — the negation read backwards."""
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: w["top"]):
        if lines and w["top"] - lines[-1][0]["top"] <= _LINE_PT:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [w for line in lines for w in sorted(line, key=lambda w: w["x0"])]


def _parse_table(page, heading_words: list[dict]) -> list[dict]:
    """The rows under a heading: each door-code word starts a row; the row is every word from the code's
    line down to the next code (or 40 pt), to the right of the table's left edge."""
    top = max(w["bottom"] for w in heading_words)
    left = min(w["x0"] for w in heading_words) - 24
    words = [w for w in page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=2, y_tolerance=3)
             if w["top"] >= top - 2 and w["x0"] >= left]
    codes = sorted((w for w in words if _CODE_RE.match(w["text"])), key=lambda w: (w["top"], w["x0"]))
    rows: list[dict] = []
    for k, cw in enumerate(codes[:_MAX_ROWS]):
        y0 = cw["top"] - 3
        y1 = (codes[k + 1]["top"] - 3) if k + 1 < len(codes) else cw["top"] + 40
        cells = _reading_order([w for w in words if y0 <= w["top"] < y1 and w is not cw])
        text = " ".join(w["text"] for w in cells)
        width, height = _row_size(text, cells)
        kiekis = None
        m = re.search(r"\b(\d{1,2})\s*vnt", text, re.IGNORECASE)
        if m:
            kiekis = int(m.group(1))
        rows.append({"kodas": cw["text"].rstrip("*"), "plotis_mm": width, "aukstis_mm": height,
                     "tipas": _row_type(text), "kiekis": kiekis, "tekstas": text[:160],
                     "bbox_pct": _words_pct(page, [cw] + cells)})
    return rows


def _words_pct(page, words: list[dict]) -> list[float] | None:
    """The box around these words as display-frame fractions [x0, y0, x1, y1] (extractor/table_reader: the
    pdfplumber page frame, its page box origin subtracted, IS the PDFium display frame)."""
    try:
        ox, oy = float(page.bbox[0]), float(page.bbox[1])
        pw, ph = float(page.width), float(page.height)
        if not words or pw <= 0 or ph <= 0:
            return None
        clip = lambda v: min(max(v, 0.0), 1.0)  # noqa: E731
        return [round(clip((min(w["x0"] for w in words) - ox) / pw), 5), round(clip((min(w["top"] for w in words) - oy) / ph), 5),
                round(clip((max(w["x1"] for w in words) - ox) / pw), 5), round(clip((max(w["bottom"] for w in words) - oy) / ph), 5)]
    except Exception:  # noqa: BLE001 — a box is evidence, never the reason a row is lost
        return None


def _union_pct(boxes: list) -> list[float] | None:
    boxes = [b for b in boxes if isinstance(b, (list, tuple)) and len(b) == 4]
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


# where a ruled table may stand relative to its heading, as shares of the page: just under it (or the heading
# ruled inside it), overlapping it sideways
_RULED_ABOVE, _RULED_BELOW, _RULED_SIDE = 0.02, 0.25, 0.15


def _ruled_rows(pdf_bytes: bytes, pg: int, page, heading_words: list[dict]) -> tuple[list[dict], dict | None]:
    """The rows of the RULED door table under this heading (extractor/table_reader + schedules: cells, each row
    with its box), in this scanner's row shape — or ([], None) when the heading stands over no ruled door table
    (a schedule drawn as plain text: the word-position parser reads it)."""
    try:
        from .schedules import classify_table, schedule_rows
        from .table_reader import read_tables
        head = _words_pct(page, heading_words)
        if head is None:
            return [], None
        best = None
        for t in read_tables(pdf_bytes, pg):
            kind, roles = classify_table(t)
            if kind != "durys":
                continue
            x0, y0, x1, _ = t["bbox_pct"]
            if not (head[1] - _RULED_ABOVE <= y0 <= head[3] + _RULED_BELOW):
                continue
            if x1 < head[0] - _RULED_SIDE or x0 > head[2] + _RULED_SIDE:
                continue
            if best is None or y0 < best[0]["bbox_pct"][1]:
                best = (t, roles)
        if best is None:
            return [], None
        table, roles = best
        rows = []
        for r in schedule_rows(table, "durys", roles)[0][:_MAX_ROWS]:
            rows.append({"kodas": str(r["kodas"]).rstrip("*"), "plotis_mm": r["plotis_mm"], "aukstis_mm": r["aukstis_mm"],
                         "tipas": r["tipas"], "kiekis": r["kiekis"], "tekstas": str(r.get("tekstas") or "")[:160],
                         "bbox_pct": r.get("bbox_pct")})
        return rows, table
    except Exception:  # noqa: BLE001 — the word parser is always there to fall back on
        return [], None


def _count_on_plans(code: str, texts: list[str], table_page: int) -> int:
    """How many times the code stands on the drawing outside its own table row."""
    pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(code) + r"(?![0-9])")
    n = 0
    for i, t in enumerate(texts):
        hits = len(pat.findall(t or ""))
        if i + 1 == table_page:
            hits -= 1                                          # the table's own row
        n += max(0, hits)
    return n


def _sentence(out: dict) -> str:
    table = out.get("lentele") or {}
    rows = table.get("eilutes") or []
    if rows:
        parts = []
        for r in rows:
            size = (f"{r['plotis_mm']}×{r['aukstis_mm']}" if r.get("plotis_mm") and r.get("aukstis_mm") else "")
            tipas = {"beapvadines": "beapvadinės", "su_apvadais": "su apvadais", "stumdomos": "stumdomos",
                     "stiklines": "stiklinės", AMBIGUOUS: "tipas neaiškus"}.get(r.get("tipas") or "", "tipas neužrašytas")
            parts.append(f"{r['kodas']} {size} {tipas} ×{r.get('kiekis') or 1}".replace("  ", " "))
        framed = out.get("su_apvadais") or 0
        tail = "su apvadais nėra" if not framed else f"su apvadais — {framed}"
        unclear = [str(r["kodas"]) for r in rows if r.get("tipas") == AMBIGUOUS]
        if unclear:
            tail += (f". {', '.join(unclear)} eilutėje užrašyta ir „be apvadų“, ir „su apvadais“ — patikrinkite, "
                     "kokios tai durys" if len(unclear) == 1 else
                     f". {', '.join(unclear)} eilutėse užrašyta ir „be apvadų“, ir „su apvadais“ — patikrinkite, "
                     "kokios tai durys")
        return f"Durų žiniaraštyje ({table.get('page')} lapas): " + ", ".join(parts) + f"; {tail}."
    bits = []
    if out.get("pastaba_visos"):
        bits.append("brėžinio pastaba: visos vidaus durys beapvadinės")
    n = out.get("anotacijos_beapvadines") or 0
    if n:
        word = "anga pažymėta" if n % 10 == 1 and n % 100 != 11 else "angos pažymėtos" if n % 10 in range(2, 10) and n % 100 not in range(12, 20) else "angų pažymėta"
        bits.append(f"plane {n} {word} „skirta beapvadinėms durims“")
    if out.get("pastaba_beapvadines"):
        bits.append("pastaba: durų staktas ruošti beapvadinėms durims")
    if bits:
        return "Durų žiniaraščio nėra; " + "; ".join(bits) + "."
    if out.get("gaminiai"):
        return ("Durų žiniaraščio nėra; apdailos lape nurodyti vidaus durų gaminiai (" +
                "; ".join(out["gaminiai"][:2]) + "), beapvadinių niekur neminima.")
    if not out.get("text_layer_ok"):
        return "Brėžinio tekstas neįskaitomas — durų žiniaraščio programa perskaityti negali."
    return "Durų žiniaraščio ar durų tipo užrašų brėžinyje nėra."


def scan_door_schedule(pdf_bytes: bytes) -> dict:
    """{status: lentele|anotacijos|gaminiai|nera, text_layer_ok, pages, lentele: {page, eilutes: [...]},
        beapvadines, su_apvadais, stumdomos, kitos (units the table lists), neaiskios + neaiskus_kodai (units
        and codes of rows that name both frame types — counted under `kitos`, never as either type),
        anotacijos_beapvadines, pastaba_visos, pastaba_beapvadines, stumdomos_pastaba, gaminiai: [...], sakinys}.

    Since 2026-10-18 (Pathon v3 W3-A) the table is read from its RULED cells when the heading stands over a
    ruled door table (extractor/table_reader + schedules: header roles, a „Kiekis" column read as the count),
    else from word positions as before; `lentele` gains `bbox_pct` (the table) and `saltinis` („lentele" |
    „zodziai"), every row gains `page` and `bbox_pct` — display-frame fractions [x0, y0, x1, y1], the frame of
    the evidence crops, so a row can be shown on the drawing."""
    try:
        from .pdf_page_cache import page_texts
        texts = [t or "" for t in page_texts(pdf_bytes)]
    except Exception:  # noqa: BLE001
        return _empty(False)
    chars = sum(len(t) for t in texts)
    out = _empty(chars >= MIN_TEXT_CHARS)
    if chars < MIN_TEXT_CHARS:
        out["sakinys"] = _sentence(out)
        return out
    # annotations, notes, products — per page
    products: list[str] = []
    for i, t in enumerate(texts):
        n_anno = len(_ANNOTATION_RE.findall(_NOTE_PREP_RE.sub(" ", t)))
        if n_anno:
            out["anotacijos_beapvadines"] += n_anno
            out["pages"].append(i + 1)
        if _NOTE_ALL_RE.search(t):
            out["pastaba_visos"] = True
        if _NOTE_PREP_RE.search(t):
            out["pastaba_beapvadines"] = True
        if _SLIDING_NOTE_RE.search(t):
            out["stumdomos_pastaba"] = True
        for m in _PRODUCT_RE.finditer(t):
            name = " ".join(m.group(1).split()).strip(" ,;:()")
            name = name.split(",")[-1].strip() or name
            s = f"{name} vidaus durys" if name else "vidaus durys"
            if s not in products:
                products.append(s[:80])
    out["gaminiai"] = products[:5]
    # the table
    table_pages = [i + 1 for i, t in enumerate(texts) if _HEADING_RE.search(t)]
    if table_pages:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for pg in table_pages[:3]:
                    page = pdf.pages[pg - 1]
                    words = page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=2, y_tolerance=3)
                    heading = [w for w in words if re.match(r"žiniarašt|ziniarast|specifikac|lentel", w["text"], re.IGNORECASE)]
                    if not heading:
                        continue
                    # the heading word whose line also carries „durų"
                    picked = None
                    for hw in heading:
                        # the heading's own words only — a plan label on the same line would pull the
                        # table's left edge out to the plan and its door tags into the rows
                        line = [w for w in words if abs(w["top"] - hw["top"]) < 4
                                and hw["x0"] - 220 <= w["x0"] and w["x1"] <= hw["x1"] + 320]
                        if any(re.search(r"dur", w["text"], re.IGNORECASE) for w in line):
                            picked = line
                            break
                    if not picked:
                        continue
                    # the ruled table's cells first (table_reader: each row with its box); a schedule written as
                    # plain text is read from its word positions, as before
                    rows, ruled = _ruled_rows(pdf_bytes, pg, page, picked)
                    source = "lentele" if rows else "zodziai"
                    if not rows:
                        rows = _parse_table(page, picked)
                    if not rows:
                        continue
                    for r in rows:
                        if r["kiekis"] is None:
                            r["kiekis"] = max(1, _count_on_plans(r["kodas"], texts, pg))
                        r["page"] = pg
                    box = (ruled or {}).get("bbox_pct") or _union_pct([r.get("bbox_pct") for r in rows])
                    out["lentele"] = {"page": pg, "eilutes": rows, "bbox_pct": box, "saltinis": source}
                    if pg not in out["pages"]:
                        out["pages"].append(pg)
                    break
        except Exception:  # noqa: BLE001 — a table we cannot parse is no table
            pass
    rows = (out["lentele"] or {}).get("eilutes") or []
    for r in rows:
        key = {"beapvadines": "beapvadines", "su_apvadais": "su_apvadais", "stumdomos": "stumdomos"}.get(r["tipas"], "kitos")
        out[key] += int(r.get("kiekis") or 1)
        if r["tipas"] == AMBIGUOUS:
            out["neaiskios"] += int(r.get("kiekis") or 1)
            out["neaiskus_kodai"].append(r["kodas"])
    out["pages"] = sorted(set(out["pages"]))
    if rows:
        out["status"] = "lentele"
    elif out["anotacijos_beapvadines"] or out["pastaba_visos"] or out["pastaba_beapvadines"]:
        out["status"] = "anotacijos"
    elif out["gaminiai"]:
        out["status"] = "gaminiai"
    out["sakinys"] = _sentence(out)
    return out
