"""Identity-safe room matching across N Pass-1 voting rounds.

WHY THIS EXISTS
---------------
`extraction_voter.match_rooms` groups rooms across runs by `_room_key`, which
is `nr:<nr>` whenever the run emitted a room number. On a plan WITH an
eksplikacija table that is exactly right: the nr is read from the table, so it
is the same physical room in every run. On a plan WITHOUT one the model
INVENTS the numbering, and two rounds can number the same rooms differently.
The voter then medians two different rooms together — and the median of two
values is their MEAN, so it manufactures a number no round ever produced.

Measured on the saved objektas_c round data (ground_truth/objektas_c/ai_extract.json,
`_vote.values`, no eksplikacija — `rooms_in_table: 0`):

    nr   round A (plotas/perim/npw)   round B (plotas/perim/npw)   voted
    01   14.5 / 15.4 / 2              16.5 / 16.4 / 2              15.50  same room
    02    4.5 /  8.5 / 3               4.5 /  8.5 / 3               4.50  same room
    03   13.5 / 14.8 / 3              14.5 / 15.6 / 2              14.00  same room
    04   40.0 / 26.0 / 5              13.0 / 14.6 / -              26.50  DIFFERENT
    05   13.5 / 14.8 / 3               5.0 /  9.0 / 2               9.25  DIFFERENT
    06    4.5 /  8.5 / 2              42.0 / 26.0 / 5              23.25  DIFFERENT

Round A's numbering maps 1:1 onto the six physical rooms the adjacency pass
found (ground_truth/objektas_c/adjacency.json — Miegamasis npw=2, Vonia prie
miegamojo npw=3, Kambarys ŠR npw=3, Svetainė-virtuvė npw=5, Kambarys PR npw=3,
Vonia prie lauko durų npw=2). Round B's does not: its nr06 carries npw=5 and
42 m², i.e. it is the Svetainė-virtuvė. So the voter averaged a 4.5 m² bathroom
with a 42 m² open-plan living room and produced a 23.25 m² "vonia" with a
geometrically impossible perimeter.

The corpus says this is not a one-off: over the 452 voted rooms that still
carry per-round values in this repo, 25 (5.5%) have a pairwise area spread
above 35% — every one of them on a no-eksplikacija plan, and every one of
them a value pair like 4.5/42.0, 12.5/32.0, 28.0/5.0.

THE FIX
-------
Two paths, chosen automatically:

1. **nr path** (`nr_key_is_trustworthy`) — used when the numbering is complete,
   unique inside each run, identical across all runs, AND geometrically
   coherent (no nr-group contains two rooms whose areas differ by more than
   `AREA_VETO`). This reproduces the current behaviour bit-for-bit on every
   eksplikacija-anchored project (objektas_a, objektas_b, objektas_d: areas are read
   from the table and are identical across rounds, so coherence is trivially
   satisfied).

2. **assignment path** — otherwise. Rooms are clustered incrementally: run 0
   seeds the clusters, and each later run is matched against them by optimal
   (Hungarian) assignment over a normalised cost that blends area, perimeter,
   LT-normalised name similarity, paskirtis, bbox overlap and a weak nr prior.
   Two rules keep identities apart:
     * a **hard area veto** — a pair whose areas differ by more than
       `AREA_VETO` can never be matched, whatever its name or nr says;
     * a **cost ceiling** — a pair above `COST_MAX` is left unmatched rather
       than force-fitted.
   A cluster takes at most one room per run, so a room can never be averaged
   with another room from its own round.

Perimeter is deliberately NOT a veto: the corpus contains rounds that report
perimetras_m = 0 for every room (eval_runs/2026-07-04_20-32-12_objektas_a_vision),
which is a failed read, not a different room.

Pure functions: no I/O, no API, deterministic.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from statistics import median
from typing import Any

# ── Thresholds ───────────────────────────────────────────────────────────
# Calibrated on every saved `_vote` block in the repo (452 voted rooms across
# 46 runs). Pairwise |Δarea| / max(area):
#   legitimate run-to-run jitter tops out at 0.333 (28/30/42 on one open-plan
#   room) and is <= 0.077 at the 90th percentile;
#   identity collisions start at 0.438 and run to 0.893.
# 0.35 sits in the gap. Raising it past 0.45 lets objektas_c's 40-vs-13 pair back
# in; lowering it past 0.25 starts splitting genuine jitter.
AREA_VETO = 0.35
# Normalised blended cost above which a pair is left unmatched. With every
# term present, a pair that agrees on nothing but a same-ish area scores ~0.6.
COST_MAX = 0.55
# Soft saturation point for the perimeter term (a 50% perimeter difference
# already contributes its full weight).
_PERIM_SCALE = 0.50

_W_AREA = 3.0
_W_PERIM = 1.5
_W_NAME = 2.0
_W_PASKIRTIS = 1.0
_W_BBOX = 2.0
_W_NR = 0.5          # weak prior only — never decisive on its own

_FORBIDDEN = 1e6     # finite sentinel so the Hungarian arithmetic stays sane


# ── Normalisation helpers ────────────────────────────────────────────────
def norm_name(s: str | None) -> str:
    """Lowercase, strip Lithuanian diacritics, collapse whitespace."""
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip()


def norm_nr(nr: Any) -> str:
    """Strict nr normalisation: lowercase, drop a leading 'nr'/'no' label and
    any surrounding punctuation/whitespace. '01' and '1' stay DIFFERENT here."""
    s = str(nr if nr is not None else "").strip().lower()
    s = re.sub(r"^(nr|no)\s*\.?\s*", "", s)
    return re.sub(r"[\s]+", "", s).strip(" .-")


def loose_nr(nr: Any) -> str:
    """Loose nr normalisation: last dot/dash segment, leading zeros stripped.

    '1' -> '1', '01' -> '1', '1.01' -> '1', '101' -> '101'. Used only when it
    stays injective inside every run (it collapses '1.01' and '2.01' to '1',
    so a two-floor plan falls back to the strict form)."""
    s = norm_nr(nr)
    if not s:
        return ""
    seg = re.split(r"[.\-/]", s)[-1] or s
    stripped = seg.lstrip("0")
    return stripped or seg


def name_similarity(a: str | None, b: str | None) -> float:
    """0..1 similarity between two LT room names, diacritics-insensitive."""
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    # Token overlap catches "Svetainė/Valgomasis/Virtuvė" vs "Svetainė-virtuvė"
    ta = {t for t in re.split(r"[^a-z0-9]+", na) if len(t) > 2}
    tb = {t for t in re.split(r"[^a-z0-9]+", nb) if len(t) > 2}
    jacc = len(ta & tb) / len(ta | tb) if (ta or tb) else 0.0
    return max(ratio, jacc)


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _rel_diff(a: float, b: float) -> float:
    m = max(abs(a), abs(b))
    return abs(a - b) / m if m else 0.0


def bbox_iou(a: dict | None, b: dict | None) -> float | None:
    """Intersection-over-union of two bbox_pct dicts, or None if unusable."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    try:
        ax, ay, aw, ah = (float(a["x"]), float(a["y"]), float(a["w"]), float(a["h"]))
        bx, by, bw, bh = (float(b["x"]), float(b["y"]), float(b["w"]), float(b["h"]))
    except (KeyError, TypeError, ValueError):
        return None
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return None
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return (inter / union) if union > 0 else None


# ── Pair cost ────────────────────────────────────────────────────────────
def pair_cost(a: dict, b: dict) -> float | None:
    """Blended 0..1 cost that `a` and `b` are the same physical room.

    Returns None when the pair is FORBIDDEN (hard area veto) or when there is
    no shared evidence at all to compare on.
    """
    terms: list[tuple[float, float]] = []

    area_a, area_b = _num(a.get("plotas_m2")), _num(b.get("plotas_m2"))
    if area_a is not None and area_b is not None:
        d = _rel_diff(area_a, area_b)
        if d > AREA_VETO:
            return None                       # different rooms, full stop
        terms.append((_W_AREA, d / AREA_VETO))

    p_a, p_b = _num(a.get("perimetras_m")), _num(b.get("perimetras_m"))
    if p_a is not None and p_b is not None:
        terms.append((_W_PERIM, min(_rel_diff(p_a, p_b) / _PERIM_SCALE, 1.0)))

    na, nb = norm_name(a.get("pavadinimas")), norm_name(b.get("pavadinimas"))
    if na and nb:
        terms.append((_W_NAME, 1.0 - name_similarity(na, nb)))

    pa, pb = norm_name(a.get("paskirtis")), norm_name(b.get("paskirtis"))
    if pa and pb:
        terms.append((_W_PASKIRTIS, 0.0 if pa == pb else 1.0))

    iou = bbox_iou(a.get("bbox_pct"), b.get("bbox_pct"))
    if iou is not None:
        terms.append((_W_BBOX, 1.0 - iou))

    ka, kb = norm_nr(a.get("nr")), norm_nr(b.get("nr"))
    if ka and kb:
        same = (ka == kb) or (loose_nr(ka) == loose_nr(kb))
        terms.append((_W_NR, 0.0 if same else 1.0))

    if not terms:
        return None                            # nothing to compare on
    total_w = sum(w for w, _ in terms)
    return sum(w * x for w, x in terms) / total_w


# ── Hungarian assignment (O(n^3) JV, pure Python, deterministic) ─────────
def _hungarian(cost: list[list[float]]) -> list[int]:
    """Minimum-cost assignment. Returns row -> col (or -1). Rows <= cols."""
    n, m = len(cost), len(cost[0])
    inf = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], inf, 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j], way[j] = cur, j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    out = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def solve_assignment(cost: list[list[float | None]]) -> list[int]:
    """Optimal row->col assignment over a cost matrix whose None cells are
    forbidden. Cells above COST_MAX are forbidden too. Returns -1 for rows
    left unmatched. Deterministic."""
    if not cost or not cost[0]:
        return [-1] * len(cost)
    n, m = len(cost), len(cost[0])
    dense = [[(_FORBIDDEN if (c is None or c > COST_MAX) else float(c))
              for c in row] for row in cost]
    if n <= m:
        raw = _hungarian(dense)
        pairs = [(i, raw[i]) for i in range(n)]
    else:
        t = [[dense[i][j] for i in range(n)] for j in range(m)]
        raw = _hungarian(t)
        pairs = [(raw[j], j) for j in range(m) if raw[j] >= 0]
    out = [-1] * n
    for i, j in pairs:
        if i >= 0 and j >= 0 and dense[i][j] < _FORBIDDEN:
            out[i] = j
    return out


# ── nr-path trust gate ───────────────────────────────────────────────────
def nr_match_keys(runs: list[list[dict]]) -> list[list[str]] | None:
    """The per-run, per-room nr keys to group by — or None if nr is unsafe.

    Requires, in order: every room numbered; numbers unique inside each run;
    the SAME number set in every run; and every nr-group geometrically
    coherent (no pairwise area gap above AREA_VETO). Tries the strict form
    first and falls back to the loose one ('1' / '01' / '1.01' are the same
    room) only while the loose form stays injective inside every run.

    Returned aligned with `runs`, one key list per run (empty list for an
    empty run), so the caller can bucket by index.
    """
    if not any(runs):
        return [[] for _ in runs]

    strict: list[list[str]] = []
    for run in runs:
        keys = [norm_nr(room.get("nr")) for room in (run or [])]
        if run and not all(keys):
            return None                        # an unnumbered room
        strict.append(keys)

    def _sets_agree(keysets: list[list[str]]) -> bool:
        live = [k for k in keysets if k]
        if any(len(set(k)) != len(k) for k in live):
            return False                       # duplicate nr inside a run
        first = set(live[0])
        return all(set(k) == first for k in live[1:])

    keysets = strict
    if not _sets_agree(keysets):
        loose = [[loose_nr(k) for k in keys] for keys in strict]
        if not _sets_agree(loose):
            return None
        keysets = loose

    # Geometric coherence: the nrs agree as LABELS — do they agree as ROOMS?
    by_key: dict[str, list[float]] = {}
    for run, keys in zip(runs, keysets):
        for room, k in zip(run or [], keys):
            a = _num(room.get("plotas_m2"))
            if a is not None:
                by_key.setdefault(k, []).append(a)
    for areas in by_key.values():
        if len(areas) > 1 and _rel_diff(min(areas), max(areas)) > AREA_VETO:
            return None
    return keysets


def nr_key_is_trustworthy(runs: list[list[dict]]) -> bool:
    """True when grouping by room number is safe (and therefore preferred)."""
    return nr_match_keys(runs) is not None


# ── Public entry point ───────────────────────────────────────────────────
def _cluster_probe(members: list[dict]) -> dict:
    """A comparable stand-in for a cluster: median geometry, first member's
    identity fields (the first member is always the earliest run)."""
    probe = dict(members[0])
    for f in ("plotas_m2", "perimetras_m"):
        vals = [_num(m.get(f)) for m in members]
        vals = [v for v in vals if v is not None]
        if vals:
            probe[f] = median(vals)
    return probe


def match_rooms_robust(runs: list[list[dict]]) -> list[list[dict]]:
    """Group rooms across runs so that a group never mixes two identities.

    Returns groups in a deterministic order (run-0 rooms first, in their
    original order, then rooms first seen in later runs). Does NOT apply the
    min_votes filter — the caller does.
    """
    # Seed the clusters with the first non-empty run.
    start = 0
    while start < len(runs) and not runs[start]:
        start += 1
    if start >= len(runs):
        return []
    clusters: list[list[dict]] = [[room] for room in runs[start]]

    for run in runs[start + 1:]:
        rooms = list(run or [])
        if not rooms:
            continue
        probes = [_cluster_probe(c) for c in clusters]
        cost: list[list[float | None]] = [
            [pair_cost(probe, room) for room in rooms] for probe in probes
        ]
        assigned = solve_assignment(cost) if probes else []
        taken: set[int] = set()
        for ci, ri in enumerate(assigned):
            if ri >= 0:
                clusters[ci].append(rooms[ri])
                taken.add(ri)
        for ri, room in enumerate(rooms):
            if ri not in taken:
                clusters.append([room])
    return clusters
