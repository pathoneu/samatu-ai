"""Row-level scorecard — the share of the contractor's OWN billed rows we reproduce.

WHY (2026-09-04). `eval_harness.py` scores ~22 aggregated metrics (paint, ceiling,
LED, tiles, kampai, angokraščiai…) and reports a 3–20 % headline MAE. The
contractor does not read that table: he holds his sąmata next to ours and judges
every billed row in his own vocabulary and his own granularity. Measured that
way (`docs/superpowers/research/2026-09-04-row-level-accuracy-gap.md`) we
reproduce roughly a quarter of his rows on the project we know best and one in
seven on the bigger one — a completely different number from the headline.

This module turns that comparison into an instrument:

    contractor line_items  ×  app rows  →  per-row bucket

Design rules, all deliberate:

1. **The concept table is FROZEN.** Matching goes through the hand-maintained
   `CONCEPTS` table in `scripts/reconcile_samata_lines.py` — never a fuzzy
   string match, which silently scores a real miss as a hit. A contractor row
   no concept covers is bucketed `unmapped`: it is reported, it counts against
   us, and it is NEVER scored as a hit. Adding a concept would move rows out of
   `unmapped` and inflate the metric, so growing the table is not an accuracy
   gain and must be reported as what it is — a mapping change.
2. **Count-weighted, not €-weighted.** None of the six parsed sąmatas carries
   prices (`scripts/parse_all_samatas.py` keeps them when a priced one arrives),
   so every row weighs one. A € weighting is a later change, on real prices.
3. **Unit-compatible or it does not count.** His `m2` row is never compared
   against our `vnt` row, even inside the same concept. Multi-unit cells
   (`"m2; b/m"`, `"m2/m"`) are compatible with either component.
4. **His granularity wins; ours is summed.** Inside one concept we sum OUR side
   (he can add our sienų + lubų rows to check his single „glaistymas/dažymas"
   row) but never HIS. When he bills a family on several rows and we emit fewer
   — GKP ceilings split by carcass height, tiles split by format — his extra
   rows have no number he can check, and that is a real miss even when the
   family total agrees. Those rows are paired greedily (best relative error
   first, deterministic tie-break) and the leftovers are `missing` with
   `reason="granularity…"`. Summing both sides instead would flatter us badly:
   on objektas_a it reads 49 % within ±10 % against 26 % here, and it would make
   the week-2 work of emitting rows under HIS labels invisible to the metric.
   The Σ-vs-Σ family agreement is not thrown away — it is reported per concept
   (`Scorecard.concepts`, `families_within_10`) as the second, softer number.
5. **Deterministic.** No randomness, no ordering by dict iteration; first-match
   wins on both sides, in the concept table's own order.

Buckets are disjoint and sum to the number of the contractor's priced rows:

    within_10    |app−his| ≤ 10 % of his quantity
    within_25    10 % < … ≤ 25 %
    way_off      > 25 %
    missing      no app row reproduces THIS row: none matched, none had a
                 quantity, none had a comparable unit, or the family exists but
                 is aggregated coarser than he bills it
    unmapped     no concept covers this contractor row (the coverage gap)
    no_truth_qty his own sąmata gives no number — unscorable, excluded from the
                 share denominator rather than counted as our miss

Plus `app_extra`: app rows no contractor row maps to (either no concept matches
their label, or their concept has no contractor row in this project).

The module is pure: lists in, verdicts out. No file I/O except the one lazy,
cached import of the frozen concept table; no network, no API spend.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "RowVerdict", "ConceptVerdict", "Scorecard",
    "BUCKETS", "SCORED_BUCKETS",
    "app_concept_of", "load_concepts", "normalize_unit", "priced_rows",
    "score_rows",
]

# Ordered worst-last so a table can print them in a stable, meaningful order.
BUCKETS = ("within_10", "within_25", "way_off", "missing", "unmapped",
           "no_truth_qty")
# The buckets that go into the share denominator. `no_truth_qty` is excluded:
# a row his own sąmata leaves blank is not something we can be wrong about.
SCORED_BUCKETS = ("within_10", "within_25", "way_off", "missing", "unmapped")

_REPO = Path(__file__).resolve().parents[2]
_RECONCILE = _REPO / "scripts" / "reconcile_samata_lines.py"

# ── Units ─────────────────────────────────────────────────────────────────────
# Canonical tokens, so his spelling and ours can be compared. `b/m` and `bv/m`
# are bėgamas metras — a linear metre, the same dimension as our `m`.
# `komp`/`kompl` (komplektas) folds into the count class with `vnt`: both sides
# are counting installed items and only the wording differs — the concept table,
# not the unit, is what decides WHICH family is being compared.
_UNIT_CANON: dict[str, str] = {
    "m2": "m2", "m²": "m2", "kv.m": "m2", "kvm": "m2", "kv m": "m2",
    "m": "m", "b/m": "m", "bv/m": "m", "bm": "m", "pog.m": "m", "l.m": "m",
    "m3": "m3", "m³": "m3", "kub.m": "m3",
    "vnt": "vnt", "vnt.": "vnt", "kompl": "vnt", "kompl.": "vnt",
    "komp": "vnt", "komp.": "vnt", "kmpl": "vnt", "kompletas": "vnt",
    "kg": "kg", "t": "t", "l": "l",
    "d.d": "d.d", "d.d.": "d.d", "dd": "d.d", "darbo diena": "d.d",
    "val": "val", "val.": "val",
}
_UNIT_SPLIT = re.compile(r"[;,/]")


def normalize_unit(unit: str | None) -> frozenset[str]:
    """Canonical unit tokens for one unit cell.

    Returns a SET because the contractor bills some rows in two units at once
    (`"m2; b/m"`, `"m2/m"`); such a row is comparable against either. The whole
    string is looked up first so `b/m` is read as one token and not split into
    `b` and `m`. An unknown unit yields an empty set — which makes every
    comparison against it a unit mismatch, i.e. `missing`, never a silent hit.
    """
    if not unit:
        return frozenset()
    s = " ".join(str(unit).split()).strip().lower()
    if s in _UNIT_CANON:
        return frozenset({_UNIT_CANON[s]})
    out = {_UNIT_CANON[p] for part in _UNIT_SPLIT.split(s)
           if (p := part.strip()) in _UNIT_CANON}
    return frozenset(out)


# ── The frozen concept table ──────────────────────────────────────────────────
_concepts_cache: list | None = None


def load_concepts() -> list:
    """Import the FROZEN contractor-family → app-family table.

    `scripts/` is not a package, so the module is loaded by path. It must be
    registered in `sys.modules` BEFORE `exec_module`, otherwise its
    `@dataclass` decorator cannot resolve its own module and raises.
    Import is lazy + cached so `import row_scorecard` stays side-effect free.
    """
    global _concepts_cache
    if _concepts_cache is None:
        name = "_row_scorecard_concepts"
        mod = sys.modules.get(name)
        if mod is None:
            spec = importlib.util.spec_from_file_location(name, _RECONCILE)
            if spec is None or spec.loader is None:  # pragma: no cover
                raise RuntimeError(f"cannot load concept table from {_RECONCILE}")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        _concepts_cache = list(mod.CONCEPTS)
    return _concepts_cache


_SUBTOTAL = re.compile(r"^viso\b", re.IGNORECASE)


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", (str(s or "")).replace("\n", " ")).strip()


def priced_rows(line_items: Iterable[dict]) -> list[dict]:
    """Drop the „Viso už skyrių“ subtotal rows — they are sums of rows we
    already score, so counting them would double-weight whole sections."""
    return [it for it in line_items if not _SUBTOTAL.match(_norm(it.get("name")))]


def app_concept_of(app_rows: Sequence[dict],
                   table: Sequence) -> list[str | None]:
    """Concept key of each app row, by POSITION — first match wins, in the
    concept table's own order.

    Extracted so `samata_template.render_samata` decides which app row belongs
    to which family by exactly the rule the scorecard grades by. Two copies of
    this loop would let the template fill a cell the scorecard then calls
    `missing`, which is the one divergence that would make week 2's number
    unreadable.

    The table's order is honoured on the app side as well as his, which is what
    stops one app row being counted inside two concepts (e.g. "LED nišų
    glaistymas/dažymas" matches both `nisos_led_dazymas` and the generic
    `dazymas`) and double-counting its quantity.

    A row that already KNOWS its concept says so in `_concept`, and that wins
    over the regex — a sheet rendered through the contractor's template carries
    HIS wording, which the `app` patterns are not written against, so scoring it
    by label would read every row as unmapped. The key is still checked against
    the table, so a stray value can name a concept but never invent one.
    `pozicijos[]` and `darbu_sarasas[]` never carry the field, so the corpus
    numbers are untouched.
    """
    keys = {c.key for c in table}
    out: list[str | None] = []
    for p in app_rows:
        declared = p.get("_concept")
        if isinstance(declared, str) and declared in keys:
            out.append(declared)
            continue
        out.append(next((c.key for c in table
                         if c.app is not None and c.app.search(_app_name(p))),
                        None))
    return out


# ── App-row accessors ─────────────────────────────────────────────────────────
# `pozicijos[]` (builder output) and `darbu_sarasas[]` (the v8-compat mirror)
# carry the same values under two spellings; the scorecard reads either.
def _app_name(row: dict) -> str:
    return _norm(row.get("aprasymas") or row.get("pavadinimas"))


def _app_unit(row: dict) -> str | None:
    return row.get("vnt") or row.get("mato_vnt")


def _app_qty(row: dict) -> float | None:
    q = row.get("kiekis")
    if q is None or isinstance(q, bool):
        return None
    try:
        return float(q)
    except (TypeError, ValueError):
        return None


def row_eur(item: dict) -> float | None:
    """The contractor's row total in € — `prices.darbu_viso + medziagu_viso`
    from the (gitignored, never tracked) priced parse; falls back to
    quantity × (darbu_vnt + medziagu_vnt). None when the row carries no prices,
    so a count-weighted scorecard stays possible on the tracked, price-free
    files."""
    pr = item.get("prices") if isinstance(item, dict) else None
    if not isinstance(pr, dict):
        return None
    def _f(v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None
    viso = [x for x in (_f(pr.get("darbu_viso")), _f(pr.get("medziagu_viso"))) if x is not None]
    if viso:
        return round(sum(viso), 2)
    q = _truth_qty(item)
    vnt = [x for x in (_f(pr.get("darbu_vnt")), _f(pr.get("medziagu_vnt"))) if x is not None]
    if q is not None and vnt:
        return round(q * sum(vnt), 2)
    return None


def _truth_qty(item: dict) -> float | None:
    q = item.get("quantity")
    if q is None or isinstance(q, bool):
        return None
    try:
        return float(q)
    except (TypeError, ValueError):
        return None


# ── Results ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RowVerdict:
    """One contractor row and what we did with it."""
    nr: str | None
    name: str
    section: str | None
    unit: str | None
    quantity: float | None          # HIS number
    concept: str | None             # frozen-table key, None when unmapped
    bucket: str
    app_quantity: float | None      # OURS: the paired row, or the family sum
    pct_error: float | None         # (ours − his) / his × 100, signed
    reason: str | None              # why it is `missing` / `no_truth_qty`
    split_family: bool              # he bills this family on several rows
    app_labels: tuple[str, ...]     # the app row(s) behind app_quantity
    eur: float | None = None        # HIS row total € (darbai + medžiagos) when the priced parse is used


@dataclass(frozen=True)
class ConceptVerdict:
    """The Σ-vs-Σ family comparison — the softer, granularity-blind number.

    A family can be `within_10` here while every one of his rows is `missing`
    above: that is exactly the case where our total is right and our row shape
    is not, which is what the family-template work has to fix.
    """
    key: str
    n_contractor_rows: int
    n_app_rows: int
    contractor_quantity: float | None
    app_quantity: float | None
    pct_error: float | None
    bucket: str
    reason: str | None


@dataclass(frozen=True)
class Scorecard:
    n_rows: int                     # his priced rows, all buckets
    n_scored: int                   # …minus the ones his sąmata leaves blank
    buckets: dict[str, int]
    rows: list[RowVerdict]
    concepts: list[ConceptVerdict]
    app_extra: list[dict]           # our rows no contractor row maps to
    unmapped_families: list[str]    # his row labels no concept covers
    granularity_rows: int = 0       # `missing` only because he splits finer

    @property
    def within_10_share(self) -> float | None:
        """Share of his scorable rows we reproduce within ±10 %. THE number."""
        if not self.n_scored:
            return None
        return self.buckets["within_10"] / self.n_scored * 100

    @property
    def within_25_share(self) -> float | None:
        """Cumulative: within ±25 % includes the ±10 % rows."""
        if not self.n_scored:
            return None
        n = self.buckets["within_10"] + self.buckets["within_25"]
        return n / self.n_scored * 100

    @property
    def eur_scored_total(self) -> float | None:
        """Σ of his row totals (€) over scorable rows that carry prices."""
        vals = [r.eur for r in self.rows if r.bucket in SCORED_BUCKETS and r.eur is not None]
        return round(sum(vals), 2) if vals else None

    @property
    def eur_within_10_share(self) -> float | None:
        """Share of his MONEY (row totals) we reproduce within ±10 % — the
        founder's number. None when the price-free parse was used."""
        total = self.eur_scored_total
        if not total:
            return None
        hit = sum(r.eur for r in self.rows if r.bucket == "within_10" and r.eur is not None)
        return hit / total * 100

    @property
    def families_scored(self) -> int:
        return sum(1 for c in self.concepts
                   if c.bucket in ("within_10", "within_25", "way_off"))

    @property
    def families_within_10(self) -> int:
        return sum(1 for c in self.concepts if c.bucket == "within_10")

    def as_dict(self) -> dict:
        return {
            "n_rows": self.n_rows,
            "n_scored": self.n_scored,
            "buckets": dict(self.buckets),
            "within_10_share": (None if self.within_10_share is None
                                else round(self.within_10_share, 2)),
            "within_25_share": (None if self.within_25_share is None
                                else round(self.within_25_share, 2)),
            "granularity_rows": self.granularity_rows,
            "eur_scored_total": self.eur_scored_total,
            "eur_within_10_share": (None if self.eur_within_10_share is None
                                    else round(self.eur_within_10_share, 2)),
            "families_scored": self.families_scored,
            "families_within_10": self.families_within_10,
            "n_app_extra": len(self.app_extra),
            "unmapped_families": list(self.unmapped_families),
        }


def _bucket_for(pct: float) -> str:
    a = abs(pct)
    if a <= 10.0:
        return "within_10"
    if a <= 25.0:
        return "within_25"
    return "way_off"


def score_rows(contractor_items: Sequence[dict],
               app_rows: Sequence[dict],
               *,
               concepts: Sequence | None = None) -> Scorecard:
    """Bucket every contractor row against the app's row list.

    `contractor_items` — parsed sąmata `line_items` (page/nr/section/name/unit/
    quantity). Subtotal rows are dropped here, so raw input is fine.
    `app_rows` — `pozicijos[]` or `darbu_sarasas[]`.
    `concepts` — for tests only; defaults to the FROZEN table.
    """
    table = list(load_concepts() if concepts is None else concepts)
    items = priced_rows(contractor_items)

    # ── First-match-wins on both sides, in the concept table's own order. ─────
    # The table is ordered so specific variants precede the generic patterns
    # they would otherwise be swallowed by; honouring that order on the app side
    # too also stops one app row being counted inside two concepts (e.g.
    # "LED nišų glaistymas/dažymas" matches both `nisos_led_dazymas` and the
    # generic `dazymas`), which would double-count its quantity.
    # Rows are addressed by POSITION, never by `id()`: a caller may legitimately
    # hand us the same dict object twice (two identical checklist rows), and two
    # rows sharing an id would silently collapse into one verdict.
    concept_of_row: list[str | None] = []
    c_rows: dict[str, list[int]] = {}
    unmapped: list[int] = []
    for i, it in enumerate(items):
        name = _norm(it.get("name"))
        key = next((c.key for c in table if c.contractor.search(name)), None)
        concept_of_row.append(key)
        (c_rows.setdefault(key, []).append(i) if key is not None
         else unmapped.append(i))

    a_rows: dict[str, list[int]] = {}
    a_concept_of = app_concept_of(app_rows, table)
    for j, key in enumerate(a_concept_of):
        if key is not None:
            a_rows.setdefault(key, []).append(j)

    # ── Parents (2026-09-05): HIS one row for work WE emit as several. ──────
    # A concept that names `parts` pools the parts' app rows when he billed
    # the parent and not that part — „Praustuvo potinkinės sistemos įrengimas"
    # against our potinkinė + virštinkinė rows. Where he bills a part on its
    # own row, that row keeps its app rows and the parent does not get them.
    # Rows lent to a parent are not „ours nobody bills" below.
    lent: set[int] = set()
    for c in table:
        parts = tuple(getattr(c, "parts", ()) or ())
        if not parts or not c_rows.get(c.key) or a_rows.get(c.key):
            continue
        pooled = [j for part in parts if not c_rows.get(part)
                  for j in a_rows.get(part, [])]
        if pooled:
            a_rows[c.key] = pooled
            lent.update(pooled)

    # ── Score each concept once, Σ-vs-Σ. ─────────────────────────────────────
    concept_verdicts: list[ConceptVerdict] = []
    by_key: dict[str, ConceptVerdict] = {}
    for c in table:
        crows = c_rows.get(c.key)
        if not crows:
            continue
        arows = a_rows.get(c.key, [])
        scorable = [i for i in crows if _truth_qty(items[i]) is not None]
        his = sum(_truth_qty(items[i]) or 0.0 for i in scorable)
        his_units: set[str] = set()
        for i in scorable:
            his_units |= normalize_unit(items[i].get("unit"))

        reason: str | None = None
        ours: float | None = None
        pct: float | None = None
        if not scorable:
            bucket, reason = "no_truth_qty", "contractor row carries no quantity"
        elif c.app is None and not arows:
            # No app pattern and nothing pooled from `parts` — an admitted gap.
            bucket = "missing"
            reason = f"admitted gap — {c.note or 'no app family emits this'}"
        else:
            usable = [j for j in arows
                      if _app_qty(app_rows[j]) is not None
                      and (normalize_unit(_app_unit(app_rows[j])) & his_units)]
            if not arows:
                bucket, reason = "missing", "no app row matched this family"
            elif not usable:
                no_qty = [j for j in arows if _app_qty(app_rows[j]) is None]
                bucket = "missing"
                reason = ("app row has no quantity (checklist — „suveskite patys“)"
                          if len(no_qty) == len(arows)
                          else "app row unit is not comparable")
            elif not his:
                bucket, reason = "missing", "contractor quantity is zero"
            else:
                ours = sum(_app_qty(app_rows[j]) or 0.0 for j in usable)
                pct = round((ours - his) / his * 100, 3)
                bucket = _bucket_for(pct)
        v = ConceptVerdict(
            key=c.key, n_contractor_rows=len(crows), n_app_rows=len(arows),
            contractor_quantity=round(his, 3) if scorable else None,
            app_quantity=None if ours is None else round(ours, 3),
            pct_error=pct, bucket=bucket, reason=reason,
        )
        concept_verdicts.append(v)
        by_key[c.key] = v

    # ── Score HIS rows one by one, at HIS granularity. ───────────────────────
    row_result: dict[int, tuple[str, str | None, float | None,
                                float | None, tuple[str, ...]]] = {}
    granularity_rows = 0
    for c in table:
        crows = c_rows.get(c.key)
        if not crows:
            continue
        v = by_key[c.key]
        arows = a_rows.get(c.key, [])
        labels_all = tuple(sorted(_app_name(app_rows[j]) for j in arows))
        scorable = [i for i in crows if _truth_qty(items[i]) is not None]
        for i in crows:
            if _truth_qty(items[i]) is None:
                row_result[i] = ("no_truth_qty",
                                 "contractor row carries no quantity",
                                 None, None, ())
        if not scorable:
            continue
        if v.bucket == "missing" and v.app_quantity is None:
            # The whole family failed for one shared reason (admitted gap, no
            # app row, checklist-only, incomparable unit) — every row inherits it.
            for i in scorable:
                row_result[i] = ("missing", v.reason, None, None, ())
            continue

        if len(scorable) == 1:
            # One row of his against the whole family of ours: he can add our
            # sienų + lubų lines together, so the sum is a fair counterpart.
            row_result[scorable[0]] = (v.bucket, v.reason, v.app_quantity,
                                       v.pct_error, labels_all)
            continue

        # He splits this family finer than we emit it. Pair greedily on the
        # smallest relative error, unit-compatible, each app row used once;
        # ties break on (his nr, our label, positions) so the result never
        # depends on dict ordering or on object identity.
        pairs: list[tuple[float, str, str, int, int]] = []
        for i in scorable:
            his_q = _truth_qty(items[i]) or 0.0
            if not his_q:
                continue
            u = normalize_unit(items[i].get("unit"))
            for j in arows:
                q = _app_qty(app_rows[j])
                if q is None or not (normalize_unit(_app_unit(app_rows[j])) & u):
                    continue
                pairs.append((abs((q - his_q) / his_q * 100),
                              str(items[i].get("nr") or ""),
                              _app_name(app_rows[j]), i, j))
        pairs.sort()
        used_c: set[int] = set()
        used_a: set[int] = set()
        for _abs_pct, _nr, label, i, j in pairs:
            if i in used_c or j in used_a:
                continue
            used_c.add(i)
            used_a.add(j)
            his_q = _truth_qty(items[i]) or 0.0
            our_q = _app_qty(app_rows[j]) or 0.0
            pct = round((our_q - his_q) / his_q * 100, 3)
            row_result[i] = (_bucket_for(pct), None, round(our_q, 3), pct,
                             (label,))
        for i in scorable:
            if i in used_c:
                continue
            granularity_rows += 1
            row_result[i] = (
                "missing",
                f"granularity — he bills this family on {len(scorable)} rows, "
                f"we emit {len(arows)}",
                None, None, labels_all)

    verdicts: list[RowVerdict] = []
    buckets = {b: 0 for b in BUCKETS}
    for i, it in enumerate(items):
        key = concept_of_row[i]
        if key is None:
            bucket, reason, ours_q, pct, labels = (
                "unmapped", "no concept covers this family", None, None, ())
        else:
            bucket, reason, ours_q, pct, labels = row_result[i]
        buckets[bucket] += 1
        verdicts.append(RowVerdict(
            nr=it.get("nr"), name=_norm(it.get("name")),
            section=it.get("section"), unit=it.get("unit"),
            quantity=_truth_qty(it), concept=key,
            bucket=bucket, app_quantity=ours_q, pct_error=pct, reason=reason,
            split_family=bool(key and by_key[key].n_contractor_rows > 1),
            app_labels=labels,
            eur=row_eur(it),
        ))

    # ── Our rows nobody bills: unmatched, or matched to an absent family. ────
    extra: list[dict] = []
    for j, p in enumerate(app_rows):
        key = a_concept_of[j]
        if (key is not None and c_rows.get(key)) or j in lent:
            continue
        extra.append({
            "aprasymas": _app_name(p), "vnt": _app_unit(p),
            "kiekis": _app_qty(p), "skyrius": p.get("skyrius"),
            "saltinis": p.get("saltinis"),
            "concept": key, "reason": ("no contractor row in this family"
                                       if key else "no concept covers this row"),
        })

    n_scored = sum(buckets[b] for b in SCORED_BUCKETS)
    return Scorecard(
        n_rows=len(items), n_scored=n_scored, buckets=buckets, rows=verdicts,
        concepts=concept_verdicts, app_extra=extra,
        # De-duplicated, first-seen order: he bills the same family on several
        # lines (three tile formats, two GKP heights) and the coverage gap is a
        # gap per FAMILY, not per line.
        unmapped_families=list(dict.fromkeys(_norm(items[i].get("name"))
                                             for i in unmapped)),
        granularity_rows=granularity_rows,
    )
