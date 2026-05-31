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
