"""Majority-vote dimension extractor.

Runs the dimension extractor N times (typically 3), clusters spatially-
nearby dimensions across runs, then emits a deterministic single list
where each cluster contributes one entry with the median value_mm and a
``vote_count`` field.

Motivation: a single `dim_extractor` pass on a complex floor plan is
non-deterministic at temperature=1 — the model occasionally drops some
dimensions, picks slightly different coordinates, or rounds to a
different tens-of-mm. Voting damps both sources of jitter:

  • Coverage: a real dimension appears in all 3 runs; an artifact
    appears in 1 of 3 and gets filtered by the ``min_votes`` threshold.
  • Value drift: when run A says 3150 and run B says 3160 for the same
    physical dimension, the cluster's median is the better estimate
    than picking either one.

Clusters are formed by spatial proximity in (x_pct, y_pct) space, gated
by orientation match. Two dimensions in different orientations at the
same pixel are ALWAYS different physical features.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class _DimRecord:
    """Flattened representation of a single dimension observation across
    runs. ``run`` carries the source-run index for traceability."""
    run: int
    id: str
    text: str
    value_mm: float | None
    x_pct: float
    y_pct: float
    orientation: str
    pixel_start_pct: list[float] | None
    pixel_end_pct: list[float] | None
    confidence: str


@dataclass
class VotedDimension:
    """One voted dimension. ``vote_count`` is the number of runs in which
    a member of this cluster appeared (≤ total runs)."""
    id: str
    text: str
    value_mm: float
    x_pct: float
    y_pct: float
    orientation: str
    pixel_start_pct: list[float] | None
    pixel_end_pct: list[float] | None
    confidence: str
    vote_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "value_mm": self.value_mm,
            "x_pct": self.x_pct,
            "y_pct": self.y_pct,
            "orientation": self.orientation,
            "pixel_start_pct": self.pixel_start_pct,
            "pixel_end_pct": self.pixel_end_pct,
            "confidence": self.confidence,
            "vote_count": self.vote_count,
        }


def _flatten(runs: Sequence[Sequence[dict[str, Any]]]) -> list[_DimRecord]:
    out: list[_DimRecord] = []
    for run_idx, run in enumerate(runs):
        for d in run:
            out.append(_DimRecord(
                run=run_idx,
                id=str(d.get("id") or ""),
                text=str(d.get("text") or ""),
                value_mm=(float(d["value_mm"]) if d.get("value_mm") is not None else None),
                x_pct=float(d.get("x_pct") or 0.0),
                y_pct=float(d.get("y_pct") or 0.0),
                orientation=str(d.get("orientation") or "horizontal"),
                pixel_start_pct=d.get("pixel_start_pct"),
                pixel_end_pct=d.get("pixel_end_pct"),
                confidence=str(d.get("confidence") or "high"),
            ))
    return out


def _distance_pct(a: _DimRecord, b: _DimRecord) -> float:
    """Euclidean distance in pct-of-page units."""
    return math.hypot(a.x_pct - b.x_pct, a.y_pct - b.y_pct)


def cluster_dimensions(
    runs: Sequence[Sequence[dict[str, Any]]],
    *,
    proximity_pct: float = 0.05,
    value_tolerance_pct: float = 0.05,
    min_votes: int = 2,
) -> list[VotedDimension]:
    """Cluster dimensions across runs and emit voted entries.

    Parameters
    ----------
    runs : list of run-results (each is a list of dimension dicts).
    proximity_pct : two dimensions cluster only when their (x_pct, y_pct)
        Euclidean distance is below this threshold. Default 0.02 = 2% of
        the page diagonal. Generous because cross-run coord drift can be
        large on small dimension labels.
    value_tolerance_pct : two same-position dimensions only cluster when
        their values agree within this fractional tolerance. Catches the
        rare case where a dimension and a level marker share the same
        position but are different physical features.
    min_votes : cluster must have at least this many distinct-run members
        to survive. Default 2 — strictly more than 1 means single-run
        outliers are filtered.

    Returns
    -------
    list of VotedDimension, sorted by descending vote_count then by
    ascending x_pct (deterministic ordering for byte-identical output).
    """
    records = _flatten(runs)
    if not records:
        return []

    # Sort records into a deterministic canonical order BEFORE clustering so
    # the anchor-picking pass is invariant to (a) reordering of input runs
    # and (b) the model's per-run ordering of dimensions. Tie-breakers:
    #     (1) descending value_mm (longer dimensions anchor first — they
    #         tend to be overall building dimensions, more stable),
    #     (2) ascending x_pct, then y_pct (left-to-right, top-to-bottom).
    records.sort(key=lambda r: (
        -(r.value_mm or 0),
        r.x_pct,
        r.y_pct,
        r.run,
        r.id,
    ))

    used: set[int] = set()
    clusters: list[list[_DimRecord]] = []

    for i, anchor in enumerate(records):
        if i in used:
            continue
        # Skip records with no value (e.g. level markers) — they're not
        # meaningful for length voting.
        if anchor.value_mm is None or anchor.value_mm <= 0:
            used.add(i)
            continue

        cluster = [anchor]
        used.add(i)
        for j in range(i + 1, len(records)):
            if j in used:
                continue
            cand = records[j]
            # Same orientation required (horizontal vs vertical are
            # different physical features even at the same point).
            if cand.orientation != anchor.orientation:
                continue
            if cand.value_mm is None or cand.value_mm <= 0:
                continue
            if _distance_pct(anchor, cand) > proximity_pct:
                continue
            # Value sanity — don't merge a 3150 and a 7500 at the same
            # position; they're different dimensions occluding each other.
            denom = max(anchor.value_mm, cand.value_mm)
            if denom > 0:
                if abs(anchor.value_mm - cand.value_mm) / denom > value_tolerance_pct:
                    continue
            cluster.append(cand)
            used.add(j)
        clusters.append(cluster)

    # Vote count = distinct-run cardinality (a dim appearing twice in run 0
    # but not in runs 1/2 is still only one vote).
    voted: list[VotedDimension] = []
    for cluster in clusters:
        run_set = {r.run for r in cluster}
        if len(run_set) < min_votes:
            continue
        sorted_vals = sorted(d.value_mm for d in cluster)  # type: ignore[type-var]
        n = len(sorted_vals)
        median = sorted_vals[n // 2] if n % 2 else 0.5 * (sorted_vals[n // 2 - 1] + sorted_vals[n // 2])
        # Pick the cluster representative DETERMINISTICALLY. Sort cluster by
        # (closeness-to-median, value_mm, x_pct, y_pct, run, id) so two
        # cluster members with the same |value - median| break ties
        # identically across reorderings of the input runs.
        rep = min(cluster, key=lambda d: (
            abs((d.value_mm or 0) - median),
            d.value_mm or 0,
            d.x_pct, d.y_pct, d.run, d.id,
        ))
        voted.append(VotedDimension(
            id=rep.id,
            text=rep.text,
            value_mm=median,
            x_pct=rep.x_pct,
            y_pct=rep.y_pct,
            orientation=rep.orientation,
            pixel_start_pct=rep.pixel_start_pct,
            pixel_end_pct=rep.pixel_end_pct,
            confidence=rep.confidence,
            vote_count=len(run_set),
        ))

    # Deterministic order: votes desc, then x_pct asc, then y_pct asc.
    voted.sort(key=lambda v: (-v.vote_count, v.x_pct, v.y_pct, v.value_mm))
    # Re-issue ids in stable order so downstream comparisons are clean.
    for idx, v in enumerate(voted, start=1):
        v.id = f"d{idx}"
    return voted


def vote_dimensions(
    runs: Sequence[Sequence[dict[str, Any]]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience wrapper returning the canonical ``dimensions`` payload
    shape (matches ``DimensionList.to_dict``)."""
    voted = cluster_dimensions(runs, **kwargs)
    return {
        "dimensions": [v.to_dict() for v in voted],
        "_meta": {
            "voting_runs": len(runs),
            "n_voted": len(voted),
            "vote_count_distribution": {
                str(c): sum(1 for v in voted if v.vote_count == c)
                for c in sorted({v.vote_count for v in voted})
            },
        },
    }


# ── Robust two-tier voter ─────────────────────────────────────────────────────
def _coefficient_of_variation(values: list[float]) -> float:
    """std/mean. Returns 0 for empty / zero-mean lists."""
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    if mean <= 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / n
    return (var ** 0.5) / mean


def _build_voted_from_cluster(
    cluster: list[_DimRecord],
    *,
    tier: str,
    is_singleton: bool = False,
) -> VotedDimension:
    sorted_vals = sorted(d.value_mm or 0 for d in cluster)
    n = len(sorted_vals)
    median = sorted_vals[n // 2] if n % 2 else 0.5 * (sorted_vals[n // 2 - 1] + sorted_vals[n // 2])
    rep = min(cluster, key=lambda d: (
        abs((d.value_mm or 0) - median),
        d.value_mm or 0, d.x_pct, d.y_pct, d.run, d.id,
    ))
    v = VotedDimension(
        id=rep.id, text=rep.text, value_mm=median,
        x_pct=rep.x_pct, y_pct=rep.y_pct,
        orientation=rep.orientation,
        pixel_start_pct=rep.pixel_start_pct,
        pixel_end_pct=rep.pixel_end_pct,
        confidence=rep.confidence,
        vote_count=len({r.run for r in cluster}),
    )
    # Carry the tier label on the dict-form output via a side attribute.
    # We use object __dict__ rather than dataclass field to keep the existing
    # VotedDimension shape stable for callers that already serialise it.
    object.__setattr__(v, "_tier", tier)
    object.__setattr__(v, "_singleton", is_singleton)
    return v


def _greedy_cluster_indices(
    records: list[_DimRecord],
    eligible: set[int],
    *,
    proximity_pct: float,
    value_tolerance_pct: float,
) -> tuple[list[list[int]], set[int]]:
    """Greedy single-pass clustering over a fixed set of eligible record
    indices. Returns (clusters_by_index, indices_used)."""
    clusters: list[list[int]] = []
    used: set[int] = set()
    sorted_eligible = sorted(eligible, key=lambda i: (
        -(records[i].value_mm or 0),
        records[i].x_pct, records[i].y_pct, records[i].run, records[i].id,
    ))
    for i in sorted_eligible:
        if i in used:
            continue
        anchor = records[i]
        if anchor.value_mm is None or anchor.value_mm <= 0:
            used.add(i)
            continue
        cluster_idx = [i]
        used.add(i)
        for j in sorted_eligible:
            if j in used:
                continue
            cand = records[j]
            if cand.orientation != anchor.orientation:
                continue
            if cand.value_mm is None or cand.value_mm <= 0:
                continue
            if math.hypot(anchor.x_pct - cand.x_pct, anchor.y_pct - cand.y_pct) > proximity_pct:
                continue
            denom = max(anchor.value_mm, cand.value_mm)
            if denom > 0 and abs(anchor.value_mm - cand.value_mm) / denom > value_tolerance_pct:
                continue
            cluster_idx.append(j)
            used.add(j)
        clusters.append(cluster_idx)
    return clusters, used


def robust_voter(
    runs: Sequence[Sequence[dict[str, Any]]],
    *,
    tier1_proximity_pct: float = 0.05,
    tier1_value_tol: float = 0.05,
    tier2_proximity_pct: float = 0.10,
    tier2_value_tol: float = 0.02,
    tier2_min_votes: int = 3,
    singleton_min_runs: int = 3,
) -> dict[str, Any]:
    """Two-tier voter + singleton salvage. Designed to raise retention above
    the ~33% the strict single-tier voter hits in production while keeping
    deterministic order-independent output.

    Pipeline:
      Tier 1 (strict): proximity_pct=0.05, value_tol=0.05, min_votes=2.
        Records that cluster here form the high-confidence backbone.
      Tier 2 (relaxed): for records left unclustered by tier 1, proximity
        widened to 0.10 and value tolerance tightened to 0.02 (CoV<2%).
        Requires ``tier2_min_votes`` distinct runs (default 3 of 5).
      Singleton salvage: among still-unclustered records, group by EXACT
        value_mm (rounded to mm). Groups with ≥``singleton_min_runs``
        distinct runs are emitted with confidence="low" and _singleton=True.

    The output preserves the order-independence property — all sorts use
    full tie-break tuples and the rep-picking is deterministic. Identical
    inputs (modulo run permutation) produce byte-identical JSON.

    Returns a dict with ``dimensions`` (list of voted dicts including
    _tier/_singleton flags) and ``_meta`` with retention stats.
    """
    records = _flatten(runs)
    total_records = len(records)
    if total_records == 0:
        return {
            "dimensions": [], "_meta": {
                "voting_runs": len(runs), "total_records": 0,
                "tier1_voted": 0, "tier2_voted": 0,
                "singleton_voted": 0, "n_voted": 0,
                "retention_pct": 0.0,
            },
        }

    # ── Tier 1 ────────────────────────────────────────────────────────────────
    eligible_idx = set(range(total_records))
    t1_clusters, t1_used = _greedy_cluster_indices(
        records, eligible_idx,
        proximity_pct=tier1_proximity_pct,
        value_tolerance_pct=tier1_value_tol,
    )
    tier1_voted: list[VotedDimension] = []
    tier1_consumed: set[int] = set()
    for idx_list in t1_clusters:
        cluster = [records[i] for i in idx_list]
        if len({r.run for r in cluster}) >= 2:
            tier1_voted.append(_build_voted_from_cluster(cluster, tier="tier1"))
            tier1_consumed.update(idx_list)

    # ── Tier 2 ────────────────────────────────────────────────────────────────
    leftover_after_t1 = eligible_idx - tier1_consumed
    t2_clusters, _ = _greedy_cluster_indices(
        records, leftover_after_t1,
        proximity_pct=tier2_proximity_pct,
        value_tolerance_pct=tier2_value_tol,
    )
    tier2_voted: list[VotedDimension] = []
    tier2_consumed: set[int] = set()
    for idx_list in t2_clusters:
        cluster = [records[i] for i in idx_list]
        if len({r.run for r in cluster}) < tier2_min_votes:
            continue
        # CoV check explicitly (gates value-jitter beyond tier1's pairwise rule)
        vals = [r.value_mm for r in cluster if r.value_mm is not None]
        if _coefficient_of_variation(vals) > tier2_value_tol:
            continue
        tier2_voted.append(_build_voted_from_cluster(cluster, tier="tier2"))
        tier2_consumed.update(idx_list)

    # ── Singleton salvage ─────────────────────────────────────────────────────
    leftover_after_t2 = leftover_after_t1 - tier2_consumed
    by_exact_value: dict[tuple[str, int], list[int]] = {}
    for i in leftover_after_t2:
        r = records[i]
        if r.value_mm is None or r.value_mm <= 0:
            continue
        key = (r.orientation, int(round(r.value_mm)))
        by_exact_value.setdefault(key, []).append(i)

    singleton_voted: list[VotedDimension] = []
    for idx_list in by_exact_value.values():
        cluster = [records[i] for i in idx_list]
        if len({r.run for r in cluster}) < singleton_min_runs:
            continue
        v = _build_voted_from_cluster(cluster, tier="singleton", is_singleton=True)
        # Mark salvaged singletons explicitly as lower confidence
        v.confidence = "low"
        singleton_voted.append(v)

    # ── Combine + deterministic sort + re-id ─────────────────────────────────
    voted = tier1_voted + tier2_voted + singleton_voted
    voted.sort(key=lambda v: (-v.vote_count, v.x_pct, v.y_pct, v.value_mm))
    for idx, v in enumerate(voted, start=1):
        v.id = f"d{idx}"

    # Retention denominator: the average number of dimensions per run.
    # We measure "what fraction of a typical run's dimensions made it into
    # the voted output". A retention of 100% would mean the voter emits as
    # many dimensions as a single run on average — i.e. nothing was lost.
    avg_per_run = total_records / max(len(runs), 1)
    retention_pct = (len(voted) / avg_per_run * 100.0) if avg_per_run > 0 else 0.0

    return {
        "dimensions": [{**v.to_dict(),
                        "_tier": getattr(v, "_tier", "unknown"),
                        "_singleton": getattr(v, "_singleton", False)}
                       for v in voted],
        "_meta": {
            "voting_runs": len(runs),
            "total_records": total_records,
            "avg_per_run": round(avg_per_run, 2),
            "tier1_voted": len(tier1_voted),
            "tier2_voted": len(tier2_voted),
            "singleton_voted": len(singleton_voted),
            "n_voted": len(voted),
            "retention_pct": round(retention_pct, 2),
            "vote_count_distribution": {
                str(c): sum(1 for v in voted if v.vote_count == c)
                for c in sorted({v.vote_count for v in voted})
            },
        },
    }
