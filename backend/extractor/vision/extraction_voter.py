"""Room-level voter over N extract_interior Pass-1 runs.

Pure functions: no I/O, no API. Given N parsed-shape dicts (each with
`patalpos` + `detected_symbols_summary`), return a single consensus dict
plus per-field vote-agreement so the UI can flag low-consensus values.

Matching key is the eksplikacija anchor (nr → name → paskirtis+area),
which is read from a TABLE and is far more stable run-to-run than the
geometry-derived fields we vote on (perimetras_m, lubu_aukstis_m, counts).

Why median (not mean): a single wild run (e.g. perimeter 18 where the
truth is 30) must not drag the consensus. Median of 3 ignores one outlier
entirely; mean would not.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from statistics import median
from typing import Any

# Geometry-derived per-room fields that drift run-to-run and benefit from
# median voting. plotas_m2 is usually eksplikacija-anchored (stable) but is
# voted too for robustness on no-eksplikacija plans.
_NUMERIC_VOTE_FIELDS = ("perimetras_m", "lubu_aukstis_m", "plotas_m2", "n_partition_walls")


def _norm_name(s: str | None) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s)


def _room_key(room: dict) -> str:
    nr = room.get("nr")
    if nr is not None and str(nr).strip():
        return f"nr:{nr}"
    name = _norm_name(room.get("pavadinimas"))
    if name:
        return f"nm:{name}"
    return f"pa:{(room.get('paskirtis') or '').lower()}:{round(float(room.get('plotas_m2') or 0))}"


def match_rooms(runs: list[list[dict]], *, min_votes: int = 2) -> list[list[dict]]:
    """Group room dicts that refer to the same physical room across runs.

    Returns a list of groups (each a list of the matched room dicts),
    keeping only groups present in >= min_votes distinct runs. Order is
    deterministic: by first-seen key.
    """
    buckets: dict[str, list[tuple[int, dict]]] = {}
    order: list[str] = []
    for run_idx, run in enumerate(runs):
        for room in run or []:
            k = _room_key(room)
            if k not in buckets:
                buckets[k] = []
                order.append(k)
            buckets[k].append((run_idx, room))
    groups: list[list[dict]] = []
    for k in order:
        members = buckets[k]
        if len({ri for ri, _ in members}) >= min_votes:
            groups.append([r for _, r in members])
    return groups


def _median_or_none(vals: list[Any]) -> float | None:
    nums = [float(v) for v in vals if v is not None]
    return median(nums) if nums else None


def _vote_elementai(group: list[dict], rep: dict) -> list[dict]:
    """Vote element (door/window/niche) counts per tipas (median across runs),
    keeping rep's per-element dimensions but adjusting kiekis to consensus."""
    per_run_counts: dict[str, list[int]] = defaultdict(list)
    for r in group:
        c: dict[str, int] = defaultdict(int)
        present: set[str] = set()
        for el in (r.get("elementai") or []):
            t = (el.get("tipas") or "").lower()
            c[t] += int(el.get("kiekis") or 1)
            present.add(t)
        for t in present:
            per_run_counts[t].append(c[t])
    voted_counts = {t: int(round(median(v))) for t, v in per_run_counts.items() if v}

    rep_by_tipas: dict[str, list[dict]] = {}
    for el in (rep.get("elementai") or []):
        rep_by_tipas.setdefault((el.get("tipas") or "").lower(), []).append(el)

    out: list[dict] = []
    for t, n in voted_counts.items():
        if n <= 0:
            continue
        templates = rep_by_tipas.get(t)
        if templates:
            total = sum(int(e.get("kiekis") or 1) for e in templates)
            for e in templates:
                share = max(1, round(n * (int(e.get("kiekis") or 1) / total))) if total else n
                out.append({**e, "kiekis": share})
        else:
            out.append({"tipas": t, "kiekis": n})
    return out


def vote_room_group(group: list[dict]) -> dict:
    """Collapse a matched-room group into one voted room dict."""
    vote_meta: dict[str, dict] = {}
    medians: dict[str, float | None] = {}
    for f in _NUMERIC_VOTE_FIELDS:
        present = [r.get(f) for r in group if r.get(f) is not None]
        m = _median_or_none(present)
        medians[f] = m
        if m is not None:
            vote_meta[f] = {"n": len(present), "runs": len(group), "values": present}

    # Representative = member whose perimetras is closest to the voted median,
    # so non-voted fields (bbox_pct, elementai geometry, paskirtis) come from a
    # real run rather than being synthesised.
    pm = medians.get("perimetras_m")
    rep = (min(group, key=lambda r: abs(float(r.get("perimetras_m") or 0) - pm))
           if pm is not None else group[0])

    voted: dict[str, Any] = dict(rep)
    for f, m in medians.items():
        if m is not None:
            voted[f] = int(round(m)) if f == "n_partition_walls" else round(m, 3)
    voted["elementai"] = _vote_elementai(group, rep)
    voted["_vote"] = vote_meta
    return voted


def vote_symbols(runs: list[dict]) -> dict:
    """Median each detected_symbols_summary count across runs."""
    vals: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        for k, v in (r.get("detected_symbols_summary") or {}).items():
            try:
                vals[k].append(float(v))
            except (TypeError, ValueError):
                continue
    return {k: int(round(median(vs))) for k, vs in vals.items() if vs}


# Disagreement tolerances — beyond these, runs are flagged low-confidence so the
# UI can show the user exactly which Vision-derived values to double-check
# (CLAUDE.md §7 — surface failures, don't hide them).
_PERIM_COV_TOL = 0.05      # coefficient of variation on perimeter
_CEIL_RANGE_TOL = 0.20     # metres spread on ceiling height


def _cov(vals: list[float]) -> float:
    nums = [float(v) for v in vals if v is not None]
    if len(nums) < 2:
        return 0.0
    mean = sum(nums) / len(nums)
    if mean <= 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in nums) / len(nums)
    return (var ** 0.5) / mean


def _low_confidence_fields(voted_rooms: list[dict]) -> list[dict]:
    """Scan voted rooms for fields where the runs disagreed beyond tolerance."""
    flags: list[dict] = []
    for room in voted_rooms:
        vote = room.get("_vote") or {}
        label = room.get("pavadinimas") or room.get("nr")
        pm = vote.get("perimetras_m")
        if pm and _cov(pm.get("values") or []) > _PERIM_COV_TOL:
            flags.append({"room": label, "field": "perimetras_m",
                          "values": pm["values"], "reason": "perimeter_cov_high"})
        ch = vote.get("lubu_aukstis_m")
        if ch:
            vals = [float(v) for v in (ch.get("values") or []) if v is not None]
            if vals and (max(vals) - min(vals)) > _CEIL_RANGE_TOL:
                flags.append({"room": label, "field": "lubu_aukstis_m",
                              "values": ch["values"], "reason": "ceiling_height_spread"})
    return flags


def vote_extraction(runs: list[dict], *, min_votes: int = 2) -> dict:
    """Vote N parsed-shape dicts into one consensus dict.

    Carries through the first run's non-voted top-level keys (puslapiai,
    scale, etc.), overrides patalpos + detected_symbols_summary with voted
    values, and adds a `_voting` provenance block (incl. low-confidence fields
    where runs disagreed beyond tolerance, so the UI can flag them).
    """
    base = dict(runs[0]) if runs else {}
    room_runs = [r.get("patalpos") or [] for r in runs]
    groups = match_rooms(room_runs, min_votes=min_votes)
    voted_rooms = [vote_room_group(g) for g in groups]
    base["patalpos"] = voted_rooms
    base["detected_symbols_summary"] = vote_symbols(runs)
    base["_voting"] = {
        "n_runs": len(runs),
        "min_votes": min_votes,
        "n_rooms_consensus": len(voted_rooms),
        "n_rooms_per_run": [len(r) for r in room_runs],
        "low_confidence_fields": _low_confidence_fields(voted_rooms),
    }
    return base
