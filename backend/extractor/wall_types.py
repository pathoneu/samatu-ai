"""Wall and partition types the drawing's legends name (Pathon v3 W5-D, D9) — „Naujai statomos pertvaros",
„Esamos sienos", „GK pertvara 100 mm" — with the sheet and box of each legend row. €0: the sheets whose text
says „pertvar…" / „sienų plan…" / „sienų tip…" (PDFium text, cheap), their legend zones split into rows
(extractor/legend_rows.py), the rows whose words name a wall or a partition.

A FACT only — evidence the room sheet shows beside the walls, never a quantity, a formula or a default. Which
wall of a room is which type is not decided here (that needs the partition plan laid over the room's outline);
the sentence says so. A legend whose text layer is unreadable (a broken font: objektas_h p8 „Naðjai ¦ÐÞmðÐjama
siena") is reported as unreadable, never quoted.

    read_wall_types(pdf_bytes) -> {"eilutes": [{page, tekstas, rusis, spalva, rect_pct}], "neperskaityta": [page…]}
"""
from __future__ import annotations

import hashlib
import logging
import re

log = logging.getLogger("samatu.wall_types")

SHEET_RE = re.compile(r"pertvar|sienu plan|sienu tip|sienu zymejim")
ROW_RE = re.compile(r"pertvar|sien[ao]s?\b|sienu|sienut|\bgk\b|g/k|gipskart|murin|blok", re.I)
KIND_RULES = (("griaunama", re.compile(r"griau|ardom|demontuoj", re.I)),
              ("nauja", re.compile(r"nauj|statom|montuojam|projektuojam", re.I)),
              ("esama", re.compile(r"esam|egzistuoj|lieka", re.I)))
_READABLE = re.compile(r"[A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž0-9\s.,;:()/\-–+×x%°\"'„“]")
MAX_SHEETS = 12


def readable(text: str) -> bool:
    """A text layer whose characters are mostly Lithuanian letters, digits and punctuation — a broken font
    (mojibake) is not quoted to anyone."""
    t = str(text or "").strip()
    if len(t) < 3:
        return False
    ok = sum(1 for ch in t if _READABLE.match(ch))
    return ok / len(t) >= 0.9


def kind_of(text: str) -> str | None:
    for kind, rx in KIND_RULES:
        if rx.search(text or ""):
            return kind
    return None


def read_wall_types(pdf_bytes: bytes) -> dict:
    out = {"eilutes": [], "neperskaityta": []}
    try:
        import pypdfium2 as pdfium

        from . import legend_rows as lr
        from .pdfium_guard import PDFIUM_LOCK
        from .vector_symbols import _folded_texts
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_bytes)
            n = len(doc)
            doc.close()
        texts = _folded_texts(pdf_bytes, hashlib.blake2b(pdf_bytes, digest_size=16).digest(), list(range(1, n + 1)))
        sheets = [p for p in range(1, n + 1) if SHEET_RE.search(texts.get(p, ""))][:MAX_SHEETS]
        for p in sheets:
            for leg in lr.suggest_legend_rows(pdf_bytes, p).get("legends") or []:
                for r in leg.get("rows") or []:
                    text = str(r.get("text") or "").strip()
                    if not readable(text):
                        if p not in out["neperskaityta"]:
                            out["neperskaityta"].append(p)
                        continue
                    if not ROW_RE.search(text):
                        continue
                    g, t = r.get("glyph_bbox_pct"), r.get("text_bbox_pct")
                    rect = [min(g[0], t[0]), min(g[1], t[1]), max(g[2], t[2]), max(g[3], t[3])] if g and t else (g or t)
                    out["eilutes"].append({"page": p, "tekstas": text, "rusis": kind_of(text), "spalva": r.get("colour"),
                                           "rect_pct": [round(v, 5) for v in rect] if rect else None})
    except Exception as exc:  # noqa: BLE001 — evidence only; never sinks the read
        log.warning("wall types failed: %r", exc)
    return out


def wall_type_sentence(entry: dict) -> str:
    kind = {"nauja": " (nauja)", "esama": " (esama)", "griaunama": " (griaunama)"}.get(entry.get("rusis") or "", "")
    return (f"Brėžinio legendoje ({entry.get('page')} psl.) sienų tipas: „{entry.get('tekstas')}“{kind}. "
            "Kurios šios patalpos sienos yra šio tipo — žiūrėkite brėžinyje.")
