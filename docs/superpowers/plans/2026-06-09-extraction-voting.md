# N-Pass Extraction Voting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilise the production interior extraction by running the high-variance Pass-1 (+ adjacency) N times and voting field-by-field into a single consensus `parsed` dict, fixing the kampai 325↔501 instability and the dead-pusiniai gap in one build.

**Architecture:** A new pure-function voter module (`extractor/vision/extraction_voter.py`) takes N parsed-shape dicts and returns one consensus dict + per-field vote-agreement confidence. `extract_interior()` gains a feature-flagged path that calls Pass-1 N times, votes rooms/symbols/elements, runs the adjacency pass N times and votes `n_partition_walls`, then runs Pass-2/3/4 + deterministic calc ONCE on the consensus. Voter is fully testable offline ($0); only Phase 3 spends on live Vision.

**Tech Stack:** Python 3.14, existing Anthropic client, pytest. Reuses the median/cluster patterns from `vision/majority_voter.py` but at the room level (matched by eksplikacija anchor, not spatial clustering).

**Why this shape:** Pass-1 is the single richest, highest-variance call (rooms, perimeters, ceiling heights, elementai, symbols all in one response). Voting it + the cheap adjacency page-pass captures the dominant variance without paying 3× for the whole 4-pass pipeline. Downstream passes (zoom/doors/finishes) run once on the stabilised consensus.

---

## File Structure

- **Create** `backend/extractor/vision/extraction_voter.py` — pure voter functions. No I/O, no API calls.
- **Create** `backend/tests/vision/test_extraction_voter.py` — unit tests (synthetic N-run inputs).
- **Modify** `backend/extractor/feature_flags.py` — add `extraction_voting` flag + `voting_n` int.
- **Modify** `backend/extractor/vision_call.py` — flagged voting path in `extract_interior`; adjacency wiring.
- **Create** `backend/tests/vision/test_extraction_voting_integration.py` — integration with a stubbed Pass-1 that returns 3 jittered runs.

---

### Task 1: Voter — room matching by eksplikacija anchor

**Files:**
- Create: `backend/extractor/vision/extraction_voter.py`
- Test: `backend/tests/vision/test_extraction_voter.py`

The matching key is stable across runs: `nr` if present, else normalised `pavadinimas`, else `(paskirtis, round(plotas_m2))`. Rooms that match across ≥`min_votes` runs survive; a room seen in only 1 of 3 runs is dropped (it's a hallucination/miss).

- [ ] **Step 1: Write failing test for `match_rooms`**

```python
from extractor.vision.extraction_voter import match_rooms

def test_match_rooms_by_nr_then_name():
    runs = [
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0}],
        [{"nr": 1, "pavadinimas": "Svetaine", "plotas_m2": 50.2}],
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 49.8}],
    ]
    groups = match_rooms(runs)
    assert len(groups) == 1
    assert len(groups[0]) == 3  # all three runs matched into one group

def test_match_rooms_drops_singletons():
    runs = [
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0}],
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0}],
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0},
         {"nr": 9, "pavadinimas": "Vaiduoklis", "plotas_m2": 3.0}],
    ]
    groups = match_rooms(runs, min_votes=2)
    keys = [g[0].get("pavadinimas") for g in groups]
    assert "Vaiduoklis" not in keys  # 1-of-3 → dropped
```

- [ ] **Step 2: Run, verify it fails (ImportError)**

Run: `venv/bin/python -m pytest backend/tests/vision/test_extraction_voter.py -q`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Implement `_room_key` + `match_rooms`**

```python
"""Room-level voter over N extract_interior Pass-1 runs.

Pure functions: no I/O, no API. Given N parsed-shape dicts (each with
`patalpos` + `detected_symbols_summary`), return a single consensus dict
plus per-field vote-agreement so the UI can flag low-consensus values.

Matching key is the eksplikacija anchor (nr → name → paskirtis+area),
which is read from a TABLE and is far more stable run-to-run than the
geometry-derived fields we vote on (perimetras_m, lubu_aukstis_m, counts).
"""
from __future__ import annotations

import re
import unicodedata
from statistics import median
from typing import Any


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
```

- [ ] **Step 4: Run, verify pass**

Run: `venv/bin/python -m pytest backend/tests/vision/test_extraction_voter.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/vision/extraction_voter.py backend/tests/vision/test_extraction_voter.py
git commit -m "feat(voter): room matching by eksplikacija anchor"
```

---

### Task 2: Voter — median numeric fields + vote element/symbol counts

**Files:**
- Modify: `backend/extractor/vision/extraction_voter.py`
- Test: `backend/tests/vision/test_extraction_voter.py`

Numeric room fields voted by **median** (robust to a single wild run): `perimetras_m`, `lubu_aukstis_m`, `plotas_m2`, `n_partition_walls`. Element counts (`elementai` by `tipas`) voted by **median count per tipas**. The representative room dict is the one closest to the median perimeter (carries through all non-voted fields like `bbox_pct`, `elementai` geometry). A `_vote` block records agreement.

- [ ] **Step 1: Write failing test**

```python
from extractor.vision.extraction_voter import vote_room_group, vote_symbols

def test_vote_room_group_medians_numeric():
    group = [
        {"nr": 1, "pavadinimas": "X", "plotas_m2": 50.0, "perimetras_m": 30.0,
         "lubu_aukstis_m": 2.8, "n_partition_walls": 3},
        {"nr": 1, "pavadinimas": "X", "plotas_m2": 50.0, "perimetras_m": 31.0,
         "lubu_aukstis_m": 2.8, "n_partition_walls": 3},
        {"nr": 1, "pavadinimas": "X", "plotas_m2": 50.0, "perimetras_m": 18.0,  # outlier
         "lubu_aukstis_m": 3.4, "n_partition_walls": 0},
    ]
    voted = vote_room_group(group)
    assert voted["perimetras_m"] == 30.0          # median, ignores 18 outlier
    assert voted["lubu_aukstis_m"] == 2.8          # median of 2.8,2.8,3.4
    assert voted["n_partition_walls"] == 3
    assert voted["_vote"]["perimetras_m"]["n"] == 3

def test_vote_symbols_median_per_key():
    runs = [
        {"detected_symbols_summary": {"praustuves": 3, "sviestuvai": 35}},
        {"detected_symbols_summary": {"praustuves": 5, "sviestuvai": 38}},
        {"detected_symbols_summary": {"praustuves": 5, "sviestuvai": 36}},
    ]
    voted = vote_symbols(runs)
    assert voted["praustuves"] == 5    # median(3,5,5)
    assert voted["sviestuvai"] == 36   # median(35,38,36)
```

- [ ] **Step 2: Run, verify fail**

Run: `venv/bin/python -m pytest backend/tests/vision/test_extraction_voter.py::test_vote_room_group_medians_numeric -q`
Expected: FAIL

- [ ] **Step 3: Implement `vote_room_group`, `vote_symbols`, `_median_count_by_tipas`**

```python
_NUMERIC_VOTE_FIELDS = ("perimetras_m", "lubu_aukstis_m", "plotas_m2", "n_partition_walls")


def _median_or_none(vals: list[float]) -> float | None:
    vals = [float(v) for v in vals if v is not None]
    return median(vals) if vals else None


def vote_room_group(group: list[dict]) -> dict:
    """Collapse a matched-room group into one voted room dict."""
    voted: dict[str, Any] = {}
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
    rep = min(group, key=lambda r: abs(float(r.get("perimetras_m") or 0) - (pm or 0))) if pm is not None else group[0]
    voted.update(rep)
    for f, m in medians.items():
        if m is not None:
            # keep ints intact for n_partition_walls
            voted[f] = int(round(m)) if f == "n_partition_walls" else round(m, 3)
    # Vote element counts per tipas (median across runs), then trim/pad rep's
    # elementai list so downstream count-based math (reveals, angokraščiai) uses
    # the consensus count while preserving rep's per-element dimensions.
    voted["elementai"] = _vote_elementai(group, rep)
    voted["_vote"] = vote_meta
    return voted


def _vote_elementai(group: list[dict], rep: dict) -> list[dict]:
    from collections import defaultdict
    per_run_counts: dict[str, list[int]] = defaultdict(list)
    for r in group:
        c: dict[str, int] = defaultdict(int)
        for el in (r.get("elementai") or []):
            c[(el.get("tipas") or "").lower()] += int(el.get("kiekis") or 1)
        # record this run's count for every tipas seen anywhere
        present = {(el.get("tipas") or "").lower() for el in (r.get("elementai") or [])}
        for t in present:
            per_run_counts[t].append(c[t])
    voted_counts = {t: int(round(median(v))) for t, v in per_run_counts.items() if v}
    # Build output from rep's elements (keep their dims), adjusting counts.
    rep_by_tipas: dict[str, list[dict]] = {}
    for el in (rep.get("elementai") or []):
        rep_by_tipas.setdefault((el.get("tipas") or "").lower(), []).append(el)
    out: list[dict] = []
    for t, n in voted_counts.items():
        if n <= 0:
            continue
        templates = rep_by_tipas.get(t)
        if templates:
            # distribute n across the rep templates proportionally to their count
            total = sum(int(e.get("kiekis") or 1) for e in templates)
            for e in templates:
                share = max(1, round(n * (int(e.get("kiekis") or 1) / total))) if total else n
                out.append({**e, "kiekis": share})
        else:
            out.append({"tipas": t, "kiekis": n})
    return out


def vote_symbols(runs: list[dict]) -> dict:
    """Median each detected_symbols_summary count across runs."""
    from collections import defaultdict
    vals: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        for k, v in (r.get("detected_symbols_summary") or {}).items():
            try:
                vals[k].append(float(v))
            except (TypeError, ValueError):
                continue
    return {k: int(round(median(vs))) for k, vs in vals.items() if vs}
```

- [ ] **Step 4: Run, verify pass**

Run: `venv/bin/python -m pytest backend/tests/vision/test_extraction_voter.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(voter): median numeric fields + vote element/symbol counts"
```

---

### Task 3: Voter — top-level `vote_extraction` assembling consensus parsed dict

**Files:**
- Modify: `backend/extractor/vision/extraction_voter.py`
- Test: `backend/tests/vision/test_extraction_voter.py`

- [ ] **Step 1: Write failing test**

```python
from extractor.vision.extraction_voter import vote_extraction

def test_vote_extraction_end_to_end():
    def run(perim, npw, praust):
        return {"patalpos": [
                    {"nr": 1, "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
                     "plotas_m2": 50.0, "perimetras_m": perim, "lubu_aukstis_m": 3.4,
                     "n_partition_walls": npw, "elementai": [{"tipas": "duris", "kiekis": 1}]}],
                "detected_symbols_summary": {"praustuves": praust}}
    runs = [run(30.0, 3, 3), run(31.0, 3, 5), run(18.0, 0, 5)]
    out = vote_extraction(runs, min_votes=2)
    room = out["patalpos"][0]
    assert room["perimetras_m"] == 30.0
    assert room["n_partition_walls"] == 3
    assert out["detected_symbols_summary"]["praustuves"] == 5
    assert out["_voting"]["n_runs"] == 3
```

- [ ] **Step 2: Run, verify fail.** Run: `venv/bin/python -m pytest backend/tests/vision/test_extraction_voter.py::test_vote_extraction_end_to_end -q` → FAIL

- [ ] **Step 3: Implement `vote_extraction`**

```python
def vote_extraction(runs: list[dict], *, min_votes: int = 2) -> dict:
    """Vote N parsed-shape dicts into one consensus dict.

    Carries through the first run's non-voted top-level keys (puslapiai,
    scale, etc.), overrides patalpos + detected_symbols_summary with voted
    values, and adds a `_voting` provenance block.
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
    }
    return base
```

- [ ] **Step 4: Run full voter suite.** `venv/bin/python -m pytest backend/tests/vision/test_extraction_voter.py -q` → PASS (5 tests)

- [ ] **Step 5: Commit.** `git add -A && git commit -m "feat(voter): vote_extraction consensus assembler"`

---

### Task 4: Feature flags

**Files:**
- Modify: `backend/extractor/feature_flags.py`
- Test: `backend/tests/test_feature_flags.py` (if exists; else add to voter test)

- [ ] **Step 1:** Add to `_FLAG_DEFINITIONS`: `"extraction_voting": ("ENABLE_EXTRACTION_VOTING", False)` (default OFF — opt-in until live-verified). Add an int reader for `VOTING_N` (default 3, clamp 2–5).
- [ ] **Step 2:** Write a test asserting the flag defaults False and `voting_n()` clamps.
- [ ] **Step 3:** Run → PASS.
- [ ] **Step 4:** Commit `feat(flags): extraction_voting flag + voting_n`.

---

### Task 5: Integrate voting + adjacency into `extract_interior`

**Files:**
- Modify: `backend/extractor/vision_call.py`
- Test: `backend/tests/vision/test_extraction_voting_integration.py`

The Pass-1 call (`vision_call.py:2148-2211`) is wrapped so that when `extraction_voting` is on, it runs N times into a list, votes, and proceeds with the consensus. The adjacency pass (`vision/adjacency_extractor.extract_adjacency` + `apply_adjacency_to_rooms`) runs once per Pass-1 round (cheap single-page pass) so `n_partition_walls` is in each run and gets voted. On adjacency failure: catch, leave `n_partition_walls` unset for that run, log a warning (never crash). Downstream Pass-2/3/4 + calc run ONCE on the consensus.

- [ ] **Step 1:** Write integration test with a monkeypatched Pass-1 function returning 3 jittered runs and a stubbed adjacency; assert the consensus room has the median perimeter and voted `n_partition_walls`, and that `_voting` is present.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Extract the single Pass-1 body into a helper `_run_pass1_once(...)`. Add `_run_pass1_voted(...)` that loops `voting_n()` times (each: Pass-1 + adjacency), then `vote_extraction(...)`. Gate in `extract_interior` on `flags["extraction_voting"]`.
- [ ] **Step 4:** Run integration test → PASS.
- [ ] **Step 5:** Run full non-network suite: `venv/bin/python -m pytest backend/tests/ -q -k "not vision and not api and not integration and not endpoint"` → all pass (≥773).
- [ ] **Step 6:** Commit `feat(extract): N-pass voting + adjacency wiring behind flag`.

---

### Task 6: Confidence surfacing

**Files:**
- Modify: `backend/extractor/vision_call.py` (santrauka/warnings emit)
- Test: integration test

- [ ] **Step 1:** When voting is on, for each room field where `_vote[field].values` disagree beyond a tolerance (perimeter CoV > 5%, ceiling height range > 0.2 m, or symbol values not unanimous), emit a 🟡/🔴 confidence flag into the existing warnings/confidence channel (per CLAUDE.md §7 — surface, don't hide).
- [ ] **Step 2:** Test that a high-variance group produces a low-confidence flag.
- [ ] **Step 3:** Run → PASS. Commit `feat(extract): surface per-field voting disagreement as confidence flags`.

---

### Task 7: Live verification (Phase 3 — spends $)

**Files:** none (measurement only)

- [ ] **Step 1:** Run berzas live WITH voting: `ENABLE_EXTRACTION_VOTING=1 VOTING_N=3 venv/bin/python scripts/run_vision_on_truth_set.py --only berzas` (or equivalent harness path). Capture kampai, combined paint, n_partition_walls_total.
- [ ] **Step 2:** Run it a SECOND time. Confirm run-to-run kampai delta is small (< ~5%) — the stability win. Record both.
- [ ] **Step 3:** Confirm voted kampai lands near contractor truth (493) — i.e. pusiniai is now populated in production.
- [ ] **Step 4:** Run `eval_harness.py --totals-only` on the voted extract; confirm no regression on paint/LED, and that kampai is now honestly representative.
- [ ] **Step 5:** Write findings to `docs/superpowers/research/2026-06-09-extraction-voting-results.md` (honest: stability delta, accuracy delta, $ cost, latency). If it stabilises + lands near truth → recommend flipping the flag default ON. If not → keep OFF and document why.

---

## Self-Review Notes

- **Cost guard:** voting only wraps Pass-1 + the cheap adjacency page-pass (~3× the cheapest passes), not the full 4-pass pipeline. Downstream passes run once. Document the actual $ in Task 7.
- **Structural disagreement risk:** if the 3 runs return different room SETS, `match_rooms` drops min-votes<2 rooms (hallucinations) and keeps the stable core. `_n_rooms_per_run` is logged so a flaky room count is visible.
- **No silent caps:** every drop (singleton room, failed adjacency) is logged/flagged, per CLAUDE.md.
- **Reversibility:** entire path is behind `ENABLE_EXTRACTION_VOTING` (default OFF). Zero impact until Task 7 proves it out.
