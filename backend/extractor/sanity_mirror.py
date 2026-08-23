"""Single builder for the `lt_sanity` UI mirror.

Why this module exists
──────────────────────
Three code paths used to hand-roll the same mirror:

  * `extractor/vision_call.py`   step 4.1  (/extract-interior)
  * `main.py`                    ~6400     (/recompute-interior)
  * `api/revalidate.py`          _build_lt_sanity_mirror

They drifted, and the drift was silent:

  1. All three flattened a warning down to
     `{level, room, field, value, expected, message}` — dropping `severity`,
     `hint`, `code`, `actual` and `source`. `extractor/sanity_checks.py`
     (CLAUDE.md §6 — the paint/floor ratio, ceiling≈floor, baseboard≈perimeter
     family) publishes `severity` and NO `level`, so `w.get("level", "INFO")`
     turned every one of them — including `severity="high"` — into a blue INFO
     row that the banner keeps collapsed and leaves out of the counter. The
     app's only generalisation safety net on an unseen project was muted.
  2. Two of the three read `_lt_warnings` ONLY, so rebuilding the mirror
     (revalidate / recompute) DELETED the cross-page, scale, §6 sanity,
     consistency and perimeter streams that live in `warnings`.
  3. A plain string inside `warnings` (scale_validator's older shape) made
     `w.get(...)` raise, and the caller's blanket `except` swallowed it — the
     project ended up with NO `lt_sanity` key at all.

Everything below is pure: no I/O, no mutation of the input dicts.

Severity contract (kept identical on the JS side, see
`frontend/src/lib/sanitySeverity.js`)
──────────────────────────────────────────────────────────────────────────
  severity  level     UI tier
  high      WARNING   red, expanded by default, counted as "įspėjimas"
  med       WARNING   amber, expanded by default, counted as "įspėjimas"
  low       INFO      muted, collapsed by default, counted as "pastaba"
  (high)    ERROR     red — an authored ERROR always outranks its severity

`warnings_count` keeps its historical meaning (ERROR + WARNING) so existing
callers and tests are unaffected; the new `high`/`medium`/`low` counters are
what the severity pill reads.
"""
from __future__ import annotations

import re

# Anything a validator has ever put in `level`, normalised.
_LEVEL_ALIASES = {
    "ERROR": "ERROR", "FAIL": "ERROR", "CRITICAL": "ERROR", "CRIT": "ERROR",
    "WARN": "WARNING", "WARNING": "WARNING",
    "INFO": "INFO", "NOTE": "INFO", "OK": "INFO", "PASS": "INFO",
    "DEBUG": "INFO",
}

# `sanity_checks.Warning.severity` is "low" | "med" | "high"; other validators
# have used "medium"/"warning"/"info" over the years.
_SEVERITY_ALIASES = {
    "high": "high", "critical": "high", "error": "high", "fail": "high",
    "med": "med", "medium": "med", "warn": "med", "warning": "med",
    "low": "low", "info": "low", "note": "low", "regression": "high",
}

_LEVEL_FROM_SEVERITY = {"high": "WARNING", "med": "WARNING", "low": "INFO"}
_SEVERITY_FROM_LEVEL = {"ERROR": "high", "WARNING": "med", "INFO": "low"}

# Fields copied verbatim onto every UI warning when present.
_PASSTHROUGH = ("code", "hint", "actual", "suggestion", "source",
                "discrepancy_pct")


def normalize_level(raw) -> str | None:
    """'warn' / 'FAIL' / 'Warning' → 'WARNING' / 'ERROR' / 'WARNING'."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _LEVEL_ALIASES.get(raw.strip().upper())


def normalize_severity(raw) -> str | None:
    """'medium' / 'HIGH' / 'info' → 'med' / 'high' / 'low'."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _SEVERITY_ALIASES.get(raw.strip().lower())


def resolve_tier(warning: dict) -> tuple[str, str]:
    """Return `(level, severity)` for one raw validator warning.

    An authored ERROR always wins (it is the loudest thing a validator can
    say). Otherwise `severity` decides the level, so a `severity="high"`
    check from `sanity_checks.py` can never land in the collapsed INFO
    bucket again.
    """
    lvl = normalize_level(warning.get("level"))
    sev = normalize_severity(warning.get("severity"))

    if lvl == "ERROR":
        return "ERROR", "high"
    if sev is None:
        sev = _SEVERITY_FROM_LEVEL.get(lvl or "INFO", "low")
    return _LEVEL_FROM_SEVERITY[sev], sev


def to_ui_warning(warning, default_source: str | None = None) -> dict:
    """Flatten one validator warning into the shape the banner renders.

    Accepts a bare string (scale_validator's legacy shape) so a single odd
    entry can never take the whole mirror down with it.
    """
    if not isinstance(warning, dict):
        warning = {"level": "INFO", "message": str(warning)}

    level, severity = resolve_tier(warning)
    out = {
        "level": level,
        "severity": severity,
        "room": warning.get("patalpa_nr") or warning.get("room") or "",
        "field": warning.get("field", ""),
        "value": warning.get("value"),
        "expected": warning.get("expected"),
        "message": warning.get("message", ""),
    }
    for key in _PASSTHROUGH:
        val = warning.get(key)
        if val is not None and val != "":
            out[key] = val
    if "source" not in out and default_source:
        out["source"] = default_source
    return out


def summarize(ui_warnings: list[dict], rooms_count: int,
              total_area_m2: float) -> dict:
    n_err = sum(1 for w in ui_warnings if w.get("level") == "ERROR")
    n_warn = sum(1 for w in ui_warnings if w.get("level") == "WARNING")
    n_info = sum(1 for w in ui_warnings if w.get("level") == "INFO")
    n_high = sum(1 for w in ui_warnings if w.get("severity") == "high")
    n_med = sum(1 for w in ui_warnings if w.get("severity") == "med")
    n_low = sum(1 for w in ui_warnings if w.get("severity") == "low")
    return {
        "rooms_count": rooms_count,
        "total_area_m2": total_area_m2,
        # Historical meaning — ERROR + WARNING. Do not redefine: exports,
        # the revalidate response and older tests read it.
        "warnings_count": n_err + n_warn,
        "errors": n_err,
        "warnings": n_warn,
        "info": n_info,
        # Severity pill counters (the landing-tab strip reads these).
        "high": n_high,
        "medium": n_med,
        "low": n_low,
    }


# Developer prose that OLD checks persisted into project blobs (the emit sites
# were translated on 2026-08-23, but saved projects still carry the strings and
# every rebuild re-surfaces them — the prod walkthrough saw "Patikrink ar
# shared-walls correction veikia (Sprint 4 Block B)" in the red banner). Strip
# the jargon sentence, keep the measurable part of the message.
_DEV_PROSE = re.compile(
    r"\s*[^.]*\b(Sprint\s*\d|developer|shared-walls correction|TODO|FIXME)"
    r"[^.]*\.?", re.IGNORECASE)


def _sanitize_and_dedupe(ui: list[dict]) -> list[dict]:
    """Drop legacy dev-jargon clauses from messages and collapse exact
    duplicates (same code + room + message) that accumulate when a saved
    stream and a re-run stream both carry the same check."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for w in ui:
        msg = w.get("message")
        if isinstance(msg, str) and _DEV_PROSE.search(msg):
            cleaned = _DEV_PROSE.sub("", msg).strip()
            w = {**w, "message": cleaned or msg}
        key = (w.get("code"), w.get("room"), w.get("field"), (w.get("message") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def build_lt_sanity(parsed: dict, rooms_count: int | None = None) -> dict:
    """Build `{warnings, summary}` from EVERY validator stream on `parsed`.

    Streams:
      * `_lt_warnings` — `extractor/lt_rules.apply_lt_sanity` (STR rules)
      * `warnings`     — cross_page_validator, scale_validator,
                         sanity_checks (§6), consistency_checker,
                         perimeter_validator, pipeline notes

    Rebuilding from `_lt_warnings` alone is what made "Atnaujinti AI
    patikrinimus" delete checks; both lists are always read here.
    """
    flat = parsed.get("_lt_warnings")
    pipeline = parsed.get("warnings")
    ui: list[dict] = []
    for source_default, stream in (("lt_rules", flat), (None, pipeline)):
        if not isinstance(stream, list):
            continue
        for w in stream:
            ui.append(to_ui_warning(w, default_source=source_default))
    ui = _sanitize_and_dedupe(ui)

    if rooms_count is None:
        rooms = parsed.get("patalpos")
        rooms_count = len(rooms) if isinstance(rooms, list) else 0

    raw_area = parsed.get("bendras_plotas_m2") or 0
    try:
        area = round(float(raw_area), 1)
    except (TypeError, ValueError):
        area = 0.0

    return {"warnings": ui, "summary": summarize(ui, rooms_count, area)}
