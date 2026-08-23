"""Room-level voter over N extract_interior Pass-1 runs.

Pure functions: no I/O, no API. Given N parsed-shape dicts (each with
`patalpos` + `detected_symbols_summary`), return a single consensus dict
plus per-field vote-agreement so the UI can flag low-consensus values.

Matching key is the eksplikacija anchor (nr → name → paskirtis+area),
which is read from a TABLE and is far more stable run-to-run than the
geometry-derived fields we vote on (perimetras_m, lubu_aukstis_m, counts).

⚠ That key is only as good as the table. On a plan with NO eksplikacija the
model invents the numbering and two rounds can number the same rooms
differently, so the nr key medians two DIFFERENT rooms together. The
`robust_room_matching` flag routes those plans through
`room_matcher.match_rooms_robust` instead — read that module's docstring
before touching the matching logic here.

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


def default_min_votes(n_runs: int, *, robust: bool = True) -> int:
    """Majority of the runs that actually produced a result, floored at 2.

    Was hardcoded to 2. That is a majority only at n=3 (the shipping default)
    and n=4.

    n=5 — DELIBERATE CHANGE, 2 -> 3. The old threshold accepted a room that
    only 2 of 5 rounds saw, which is a minority presented as a consensus.
    n=5 needs VOTING_N=5 in the environment and nothing sets it, so this
    changes no configuration anyone runs; it is corrected rather than
    preserved because preserving it would mean keeping a minority vote alive
    for the sake of a configuration that does not exist. (The comment at the
    call site in vision_call.py used to claim n=5 was unchanged. It was not.)

    n=2 — FLOOR OF 2, i.e. unanimity, on BOTH matchers. There is no such thing
    as a majority of two, and n=2 is reachable in production without any
    config change: VOTING_N is 3, and a Railway timeout killing one round
    leaves two. A threshold of 1 there does not "vote" at all —
    `match_rooms` appends unmatched rooms as singleton groups, so every room
    either round hallucinated survives into the result, and `_cov` reports 0.0
    for a one-member group so nothing downstream flags it. The union of two
    rounds is strictly worse than their agreement.

    That makes the `robust` argument inert today: `max(2, ceil(n/2))` is the
    same number for both matchers at every n >= 2. It is kept in the signature
    because the reason each matcher wants a floor differs — the legacy nr
    matcher needs one because it SPLITS a physical room across two groups when
    the rounds number rooms differently (the ciurliu failure), so a 1-vote
    threshold would let both halves survive and double-count the area; the
    robust matcher needs one because two rounds cannot corroborate each other.
    If the robust matcher ever earns a lower threshold at n >= 3 it belongs
    here, behind `robust`, with the measurement that justified it.
    """
    n = max(int(n_runs), 1)
    if n <= 1:
        # ONE run. `vote_extraction` never gets here (_run_pass1_voted returns
        # runs[0] directly), but `match_rooms` is called with a single run
        # directly — and the old hardcoded 2 meant every group failed the
        # threshold and the run produced ZERO rooms. A lone run's rooms are
        # all we know; 1 is the only sensible threshold.
        return 1
    return max(2, (n + 1) // 2)


def _robust_matching_enabled() -> bool:
    try:
        from ..feature_flags import get_flags
        return bool(get_flags().get("robust_room_matching"))
    except Exception:                       # never fail an extraction on a flag
        return False


def match_rooms(runs: list[list[dict]], *, min_votes: int | None = None,
                robust: bool | None = None) -> list[list[dict]]:
    """Group room dicts that refer to the same physical room across runs.

    Returns a list of groups (each a list of the matched room dicts),
    keeping only groups present in >= min_votes distinct runs. Order is
    deterministic: by first-seen key.

    robust=None reads the `robust_room_matching` feature flag. When it is on
    AND the room numbering is not trustworthy (see room_matcher — invented
    numbering on a plan with no eksplikacija), rooms are matched by an optimal
    assignment on geometry + name + bbox instead of by nr, so two DIFFERENT
    rooms are never medianed together. See room_matcher.__doc__ for the
    ciurliu evidence.
    """
    if robust is None:
        robust = _robust_matching_enabled()
    if min_votes is None:
        min_votes = default_min_votes(len(runs), robust=robust)
    nr_keys: list[list[str]] | None = None
    if robust:
        from .room_matcher import match_rooms_robust, nr_match_keys
        nr_keys = nr_match_keys(runs)
        if nr_keys is None:
            groups = match_rooms_robust(runs)
            return [g for g in groups if len(g) >= min_votes]
        # Trustworthy numbering — group by the NORMALISED key the gate just
        # validated, not by the raw string. Identical to the legacy key
        # whenever the runs already agree on the exact spelling (every
        # eksplikacija-anchored project), but it no longer silently drops
        # every room when one round writes "1" and another writes "01".

    buckets: dict[str, list[tuple[int, dict]]] = {}
    order: list[str] = []
    for run_idx, run in enumerate(runs):
        for room_idx, room in enumerate(run or []):
            k = (f"nr:{nr_keys[run_idx][room_idx]}" if nr_keys is not None
                 else _room_key(room))
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


def vote_extraction(runs: list[dict], *, min_votes: int | None = None) -> dict:
    """Vote N parsed-shape dicts into one consensus dict.

    Carries through the first run's non-voted top-level keys (puslapiai,
    scale, etc.), overrides patalpos + detected_symbols_summary with voted
    values, and adds a `_voting` provenance block (incl. low-confidence fields
    where runs disagreed beyond tolerance, so the UI can flag them).
    """
    base = dict(runs[0]) if runs else {}
    room_runs = [r.get("patalpos") or [] for r in runs]
    robust = _robust_matching_enabled()
    # Import INSIDE the flag branch, and never let it fail the run — same
    # posture as _robust_matching_enabled above. With the flag off (the
    # shipping configuration) the answer is "nr_key" by definition, so an
    # unguarded import of a brand-new module was the one way a flag that is
    # switched OFF could still kill a paid 25-minute extraction. Resolved
    # BEFORE min_votes, so a failed import degrades to the legacy matcher AND
    # its floor-of-2 together — never to robust thresholds on the legacy
    # matcher, which is the combination that double-counts a split room.
    matcher = "nr_key"
    if robust:
        try:
            from .room_matcher import nr_key_is_trustworthy
            if not nr_key_is_trustworthy(room_runs):
                matcher = "assignment"
        except Exception:                   # never fail an extraction on a flag
            robust = False
    if min_votes is None:
        min_votes = default_min_votes(len(room_runs), robust=robust)
    groups = match_rooms(room_runs, min_votes=min_votes, robust=robust)
    voted_rooms = [vote_room_group(g) for g in groups]
    base["patalpos"] = voted_rooms
    base["detected_symbols_summary"] = vote_symbols(runs)
    base["_voting"] = {
        "n_runs": len(runs),
        "min_votes": min_votes,
        "matcher": matcher,
        "n_rooms_consensus": len(voted_rooms),
        "n_rooms_per_run": [len(r) for r in room_runs],
        "low_confidence_fields": _low_confidence_fields(voted_rooms),
    }
    return base
