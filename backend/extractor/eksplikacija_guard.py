"""Is this eksplikacija table actually THESE rooms' table?

Born from the 2026-08-23 "bundle" ablation: Beržų's 17 interior sheets were
appended behind 37 architectural sheets of a DIFFERENT building, and the
eksplikacija reader returned the first table it saw — SA-02's room schedule.
The merge then joined rows BY NUMBER ALONE, so Beržų's "111 Tėvų vonia" was
assigned SA-02's "111 LAUKO TERASA = 66.47 m²", tagged as a confident
eksplikacija read. Headline MAE 3.1% → 34.7% with every room name correct.

A real contractor bundle carries the architectural part's room schedule for
the SAME building — numbering may match while areas or rooms differ — so
this is the expected upload shape, not a corner case.

Two deterministic checks, no model calls:

  assess_eksplikacija_table(rooms, eks_rows)
      Over nr-matched pairs, how often do the NAMES agree? A table that
      numbers like ours but names unlike ours is foreign → "reject".
      Fewer than MIN_PAIRS matches → "insufficient" (no table-level
      judgement; the row guard still applies).

  row_contradicts(room, eks_row)
      A nr-matched row whose name flatly contradicts the room's name must not
      override that room even when the table as a whole is fine (partial
      renumbering). Generic names ("Kambarys", "Patalpa") never contradict.

Name agreement is token overlap after Lithuanian normalisation (diacritics
stripped, punctuation split, a small wet-room synonym class so TUALETAS /
WC / san.mazgas / vonia agree with each other), or one normalised name
containing the other ("svetaine" ⊂ "svetainevirtuve").
"""
from __future__ import annotations

import re
import unicodedata

MIN_PAIRS = 3            # below this, a rate is noise — no table-level verdict
REJECT_BELOW = 0.5       # agreement rate under which the table is foreign

_STOP = {"ir", "su", "be", "pat", "patalpa", "patalpos"}
_GENERIC = {"kambarys", "kamb", "patalpa", "patalpos", "pat"}
# Wet-room family: a toilet and a bathroom are plausibly the same room under
# two names; a terrace and a bathroom are not.
_WET = {"tualetas", "wc", "san", "sanmazgas", "sanitarinis", "mazgas", "vonia",
        "vonios", "dusas", "dusine", "prausykla"}


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def name_tokens(s: str | None) -> set[str]:
    toks = {t for t in re.split(r"[^a-z0-9]+", _norm(s)) if t and t not in _STOP}
    if toks & _WET:
        toks = (toks - _WET) | {"<wet>"}
    return toks


def names_agree(a: str | None, b: str | None) -> bool:
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    if ta & tb:
        return True
    ja, jb = "".join(sorted(ta)), "".join(sorted(tb))
    ca, cb = re.sub(r"[^a-z0-9]", "", _norm(a)), re.sub(r"[^a-z0-9]", "", _norm(b))
    return bool(ca and cb and (ca in cb or cb in ca))


def is_generic_name(s: str | None) -> bool:
    # Raw tokens, NOT name_tokens(): "Patalpa" is a stop-word there and would
    # vanish — but a name made only of generic words is exactly the case.
    raw = {t for t in re.split(r"[^a-z0-9]+", _norm(s)) if t}
    return bool(raw) and raw <= (_GENERIC | _STOP)


def row_contradicts(room: dict, eks_row: dict) -> bool:
    """True when both names are present, neither is generic, and they share
    nothing — a nr collision between two different rooms."""
    rn, en = room.get("pavadinimas"), eks_row.get("pavadinimas")
    if not (rn and en):
        return False
    if is_generic_name(rn) or is_generic_name(en):
        return False
    return not names_agree(rn, en)


def assess_eksplikacija_table(rooms: list[dict], eks_rows: list[dict]) -> dict:
    """Table-level verdict. Returns {verdict, matched, agreed, rate, pairs}."""
    by_nr: dict[str, dict] = {}
    for r in eks_rows:
        nr = str(r.get("nr") or "").strip()
        if nr and nr not in by_nr:
            by_nr[nr] = r
    pairs = []
    for room in rooms:
        nr = str(room.get("nr") or "").strip()
        row = by_nr.get(nr) if nr else None
        if row is None:
            continue
        pairs.append({
            "nr": nr,
            "room": room.get("pavadinimas"),
            "table": row.get("pavadinimas"),
            "agree": names_agree(room.get("pavadinimas"), row.get("pavadinimas")),
        })
    matched = len(pairs)
    agreed = sum(1 for p in pairs if p["agree"])
    rate = (agreed / matched) if matched else None
    if matched < MIN_PAIRS:
        verdict = "insufficient"
    elif rate < REJECT_BELOW:
        verdict = "reject"
    else:
        verdict = "accept"
    return {"verdict": verdict, "matched": matched, "agreed": agreed,
            "rate": rate, "pairs": pairs}


def room_source_pages(rooms: list[dict], n_pages: int, margin: int = 2,
                      exclude: set[int] | None = None) -> list[int]:
    """The pages Pass-1 read the rooms from, ±margin, clipped to the document
    and minus `exclude` — where THESE rooms' own eksplikacija must live."""
    base: set[int] = set()
    for r in rooms:
        try:
            p = int(r.get("puslapio_nr") or 0)
        except (TypeError, ValueError):
            continue
        if p >= 1:
            base.update(range(max(1, p - margin), min(n_pages, p + margin) + 1))
    base -= set(exclude or ())
    return sorted(base)
