"""User-visible prose guard — the runtime twin of the vocabulary guard test.

Strings that reach the contractor's screen come from two places: rules that
exist in the code TODAY (`confidence.CLASS_RULES`, the ledger, the sanity
checks) and prose that was persisted into a project blob by whatever version
built it. The 2026-08-31 rewrite fixed the former; the latter kept every old
sentence, and any new surface that renders a stored field verbatim resurfaces
it (2026-09-02: a Patikra card printed a calibration confession naming another
customer's project). So: nothing stored is trusted. Every prose field is passed
through `scrub_prose` on the way out of the database and out of the recompute
endpoints, and rewritten in place once at startup (`db.scrub_all_projects`).

Two vocabularies are combined:
  * JARGON — methodology/dev speak that is never acceptable on screen. Generic,
    lives in code.
  * CONFIDENTIAL TERMS — customer identifiers. They are NEVER written into the
    repository; they come from the environment (`SAMATU_CONFIDENTIAL_TERMS`,
    comma-separated) or a gitignored `backend/.confidential-terms` file (one per
    line). Absent both, only the jargon guard runs.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Methodology confession / dev-speak. Keep this list generic — no names.
_JARGON_TOKENS = (
    r"rangovo samat", r"\brangovą\b", r"Rangovas [A-D]\b", r"\(\d+ projekt", r"projektai\)",
    r"\bvs\b", r"%/", r"\brecall\b", r"etalon", r"kalibruot", r"ginčytin",
    r"Ekstrakcij", r"Gretimyb", r"pradinis pass", r"archetip", r"low confidence",
    r"\bVision\b", r"žinomai", r"Sprint\s*\d", r"\bTODO\b", r"\bFIXME\b",
    r"shared-walls", r"\bMAE\b", r"benchmark",
)
JARGON = re.compile("|".join(_JARGON_TOKENS), re.IGNORECASE)

_TERMS_FILE = Path(__file__).resolve().parent.parent / ".confidential-terms"


def _load_terms() -> list[str]:
    terms: list[str] = []
    env = os.environ.get("SAMATU_CONFIDENTIAL_TERMS", "")
    terms += [t.strip() for t in env.split(",") if t.strip()]
    try:
        if _TERMS_FILE.exists():
            terms += [ln.strip() for ln in _TERMS_FILE.read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.startswith("#")]
    except OSError:
        pass
    # de-dupe, keep order
    seen: set[str] = set()
    return [t for t in terms if not (t.lower() in seen or seen.add(t.lower()))]


def confidential_pattern() -> re.Pattern | None:
    terms = _load_terms()
    if not terms:
        return None
    return re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)


def is_banned(text: str) -> bool:
    if not isinstance(text, str) or not text:
        return False
    if JARGON.search(text):
        return True
    pat = confidential_pattern()
    return bool(pat and pat.search(text))


# Generic guidance when a sentence had to go entirely.
FALLBACK = "Patikrinkite šį kiekį pagal brėžinį."

_CLAUSE_SPLIT = re.compile(r"(?<=[.;])\s+|\s+—\s+")


def scrub_text(text: str, fallback: str = FALLBACK) -> str:
    """Drop every clause that carries jargon or a confidential term; keep the
    rest. Nothing left → the generic guidance. Clean text passes through
    untouched (identity on every current CLASS_RULES string)."""
    if not isinstance(text, str) or not text.strip():
        return text
    if not is_banned(text):
        return text
    kept = [c for c in _CLAUSE_SPLIT.split(text) if c and not is_banned(c)]
    cleaned = " ".join(k.strip() for k in kept).strip()
    return cleaned or fallback


# Keys whose string values are prose shown to the user. Labels/ids/numbers are
# never touched — only these.
PROSE_KEYS = frozenset({
    "_confidence_reason", "review_reason", "calculation_basis", "_assumption",
    "message", "note", "included_because", "excluded_because", "reason",
    "calculation_trace", "_wall_finish_assumptions", "_ceiling_finish_assumptions",
    "warnings", "_lt_warnings", "saltinis_pastaba", "pastaba",
    # reader/check notes that older engines wrote in dev-speak ("Low confidence",
    # "Re-extract'ink … Vision prompt'as", "Sprint 4 Block B")
    "hint", "_apdailos_pastabos", "_pastabos",
    # The room check sheet (2026-09-04): the six per-fact source sentences and
    # the per-quantity formula line. Generated fresh on every request, so this
    # is belt-and-braces — but they are the most-read prose in the product and
    # the guard must own them too.
    "sentence", "formula",
})
# NOT prose: `pavadinimas`, `pastabos` (project notes), page titles, file names —
# those are the user's OWN document content (their drawing's title block may
# carry their address) and must never be rewritten.


def _scrub_value(v, key: str | None):
    if isinstance(v, str):
        return scrub_text(v) if key in PROSE_KEYS else v
    if isinstance(v, list):
        # a list under a prose key is a list of prose (or of warning dicts)
        return [_scrub_value(x, key if isinstance(x, str) else None) for x in v]
    if isinstance(v, dict):
        return {k: _scrub_value(x, k) for k, x in v.items()}
    return v


def scrub_prose(obj):
    """Deep-copy `obj` with every prose field scrubbed. Safe on any JSON shape."""
    return _scrub_value(obj, None)


def reason_for_label(label: str) -> str | None:
    """The CURRENT class-rule reason for a position label, or None."""
    from .confidence import CLASS_RULES  # local import: confidence imports nothing from here
    low = (label or "").lower()
    for needle, _conf, reason in CLASS_RULES:
        if needle in low:
            return reason
    return None


def refresh_reasons(rows: list[dict]) -> int:
    """For rows whose stored `_confidence_reason` is banned, replace it with the
    current class-rule reason for the label (else the scrubbed remainder /
    generic guidance). Mutates in place; returns how many rows changed."""
    changed = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        r = row.get("_confidence_reason")
        if isinstance(r, str) and is_banned(r):
            row["_confidence_reason"] = reason_for_label(row.get("aprasymas") or "") or scrub_text(r)
            changed += 1
    return changed
