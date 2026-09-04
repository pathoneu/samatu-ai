"""The contractor's own sąmata as the SKELETON of our output.

WHY (2026-09-04, week 2 of `plans/2026-09-04-contractor-trust-4-weeks.md`).
The row scorecard says the complaint is about the LIST, not the reads: 38–58 %
of the rows he bills have no counterpart in ours at all, and no better reader
touches those. The council's resolution was direction A refined by First
Principles — his five SECTION headings are stable across all six of his
sąmatas while row wording overlaps only 25–66 %, so the artefact to derive is a
**family skeleton in his sections and his labels**, never a literal row list.

Three rules this module exists to enforce, all from the council's blind spots:

1. **A cell we cannot stand behind ships BLANK.** At a 14–27 % row hit rate,
   dropping our number into HIS labelled row makes a wrong number *more*
   billable, not less. Only a quantity that is verified (he pressed „Teisinga",
   or typed it himself) or LEDGERED (the row carries its own contribution
   chain) fills a cell. An unverified number is offered as a greyed
   `_siulomas_kiekis` with „Patikrinkite prieš naudodami" — never as the value.
2. **Nothing we computed is lost.** An app row that no template family consumes
   lands in a final „Kita (iš brėžinio)" section under OUR label.
3. **No new fuzzy matching.** Families are grouped by the FROZEN concept table
   in `scripts/reconcile_samata_lines.py` — the same table the scorecard is
   pinned to. Only rows that table does not cover fall back to a label
   signature, and that signature never merges two rows across a unit class.

────────────────────────────────────────────────────────────────────────────
THE SHAPE (this dict IS the stored JSON — `db.upsert_samata_template`)
────────────────────────────────────────────────────────────────────────────

    {
      "version": 1,
      "name": "Rangovo šablonas",
      "sources": ["objektas_a", …],      # sąmatas it was derived from, sorted
      "n_projects": 5,
      "sections": [{
          "key": "gipso",                # first content stem of his heading
          "label": "Gipso kartono montavimas",   # his most frequent wording
          "labels": {"Gipso kartono montavimas": 4},
          "sources": ["objektas_a", …],
          "seen_in": 4,
          "order": 0.0,                  # mean NORMALISED rank, 0 = first
          "_order_sum": 0, "_order_n": 4,          # exact-merge accounting
          "families": [{
              "key": "c:gkp_lubos",      # concept key, or "n:<stems>|<unit>"
              "label": "GKP montavimas ant lubų",  # HIS wording
              "labels": {…}, "units": {"m2": 4},
              "unit": "m2",
              "concept": "gkp_lubos",    # frozen-table key, or None
              "sources": [...], "seen_in": 4, "n_rows": 7,
              "section_rows": {"gipso": 7},        # where he files it
              "order": 0.03, "_order_sum": …, "_order_n": …,
              "daznumas": "įprasta",     # ≥2 sources; 1 source → „kartais"
              "default_on": true,
          }]
      }]
    }

`_order_sum` / `_order_n` / `section_rows` are carried so a merge is EXACT and
order-independent: adding a sixth sąmata re-derives byte-for-byte the same
template as building from all six at once (asserted in
`tests/test_samata_template.py`). `_order_sum` is an INTEGER count of
millionths precisely so that it can be: a float accumulator makes the merge
non-associative at the last bit, and two templates that differ in the 15th
decimal are two different rows in SQLite. Merges de-duplicate on source NAME,
so applying the same sąmata twice is a no-op.

The module is pure: dicts in, dicts out. No file I/O beyond the one lazy,
cached import of the frozen concept table (shared with `row_scorecard`), no
network, no API spend.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Iterable, Sequence

from .position_id import position_id
from .row_scorecard import (
    app_concept_of, load_concepts, normalize_unit, priced_rows,
)

log = logging.getLogger("pathon.samata_template")

__all__ = [
    "TEMPLATE_VERSION", "DEFAULT_ON_MIN_SOURCES", "EXTRA_SECTION",
    "NOTE_BLANK", "NOTE_NO_ROOMS", "NOTE_UNVERIFIED",
    "STATUS_DEFAULT", "STATUS_OPTIONAL",
    "FILL_DONE", "FILL_SUGGESTED", "FILL_EMPTY",
    "build_template", "template_from_samata", "merge_samata", "merge_templates",
    "render_samata", "validate_template",
    "family_key", "section_key", "contractor_family_keys", "offered_families",
    "is_fillable", "is_ledgered", "is_verified",
]

TEMPLATE_VERSION = 1

# A family seen in ≥ this many of his sąmatas is „įprasta" (default-on). With a
# SINGLE source the threshold collapses to 1: a brand-new contractor's one
# sąmata is his whole vocabulary, and defaulting all of it off would hand him an
# empty sheet. See `_status_for`.
DEFAULT_ON_MIN_SOURCES = 2

# A family is ITEMISED when he has billed it on more than one line in at least
# one sąmata (`n_rows > seen_in`) — his own evidence that he thinks of it as
# several lines — and the render then gives it one row per matching app row
# instead of one summed row.
#
# WHY (measured, `research/2026-09-04-template-holdout.md`): collapsing an
# itemised family was the only thing the template made WORSE. He bills GKP
# ceilings by carcass height, tiles by format, the shower mixer by concealed vs
# exposed part; our engine computes the matching split. Handing him ONE summed
# line means the paired row reads „way off" (a sum against one of his lines)
# and his other lines read „missing — granularity" — 11 rows and 3,6 pp of the
# ±10 % share across two projects. It is also the wrong ANSWER: he cannot split
# 154,97 m² back into the 2,8 m and 3,4 m carcasses, and those are different
# work at different rates, while he can always add two of our lines together.
#
# The threshold is his behaviour, not a tuned number. An average („he usually
# splits it") was tried first at 1,5 and missed every family in this corpus,
# which he splits in one project of three or four — the split follows the
# DRAWING (two ceiling heights, three tile formats), not a habit. The second
# condition is ours: we only itemise when we actually computed more than one
# line for the family, so a family he splits and we do not still lands on one
# row.
def _is_itemised(n_rows: int, seen_in: int) -> bool:
    return bool(seen_in) and n_rows > seen_in

EXTRA_SECTION = "Kita (iš brėžinio)"

STATUS_DEFAULT = "įprasta"
STATUS_OPTIONAL = "kartais"

FILL_DONE = "uzpildyta"        # a verified / ledgered number went in
FILL_SUGGESTED = "pasiulymas"  # we have a number but nobody has checked it
FILL_EMPTY = "tuscia"          # we have nothing for this row

# User-visible, Lithuanian, and phrased as what to DO — never as a confession
# about the pipeline (`feedback_reasons_guide_not_confess`).
NOTE_BLANK = "Iš brėžinio nenustatyta — įrašykite"
NOTE_NO_ROOMS = "Brėžinyje patalpų nerasta — įrašykite"
NOTE_UNVERIFIED = "Patikrinkite prieš naudodami"

# Bounds for `validate_template` — a stored template arrives over a PUT, so it is
# attacker-shaped in a way a derived one is not.
MAX_SECTIONS = 60
MAX_FAMILIES_PER_SECTION = 400
MAX_LABEL_LEN = 400
MAX_UNIT_LEN = 32
MAX_KEY_LEN = 200
MAX_SOURCES = 200
MAX_SOURCE_LEN = 120


# ── Normalisation ────────────────────────────────────────────────────────────
# Deliberately crude and deterministic. The concept table does the real
# matching; everything here only has to group HIS OWN wordings of the same job,
# and it must never merge two rows a human would read as different work.

_PAREN_RE = re.compile(r"\([^()]*\)")
_NONALNUM_RE = re.compile(r"[^a-z0-9]+")
_WS_RE = re.compile(r"\s+")

# True function words only. Nothing that could carry meaning in a work title —
# „iki" / „virš" stay in, because they are how he names a height tier.
_STOPWORDS = frozenset({
    "ir", "bei", "su", "is", "ant", "i", "kt", "prie", "po", "per", "uz",
    "nuo", "be", "arba", "ar", "del", "bet", "kaip", "tai",
})

# LT is heavily inflected (montavimas / montavimo / montavimui), so tokens are
# truncated rather than stemmed properly. Six characters keeps „montav" apart
# from „monolit" while folding the case endings.
_STEM_LEN = 6


def _fold(value: Any) -> str:
    """Lowercase, diacritics dropped. „Plytelių" → "pluteliu"-shaped ASCII."""
    s = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def _norm(value: Any) -> str:
    """His label as one line of whitespace — the parsed sąmata keeps the PDF's
    hard line breaks inside a cell."""
    return _WS_RE.sub(" ", str(value or "").replace("\n", " ")).strip()


def _stems(name: Any) -> tuple[str, ...]:
    """Sorted, de-duplicated content stems of a label.

    Parentheticals and any token carrying a digit are dropped: they are where
    the project-specific detail lives (a room name, „2,8m aukštis", „Ø125mm"),
    and two rows that differ only there are the same family billed twice.
    """
    s = _PAREN_RE.sub(" ", _fold(name))
    out: list[str] = []
    for tok in _NONALNUM_RE.sub(" ", s).split():
        if any(ch.isdigit() for ch in tok):
            continue
        if len(tok) < 2 or tok in _STOPWORDS:
            continue
        out.append(tok[:_STEM_LEN])
    return tuple(sorted(set(out)))


def _unit_class(unit: Any) -> str:
    """Canonical unit signature, so a `m2` row and a `vnt` row of the same
    wording never collapse into one family."""
    tokens = normalize_unit(unit)
    return "|".join(sorted(tokens)) if tokens else "?"


def section_key(label: Any) -> str:
    """Group heading key: the FIRST content stem of his heading.

    His sections drift in their tail, never in their head — „Santechnikos
    darbai" vs „Santechnikos darbai/ kondicionavimo darbai", „Grindų
    montavimas" vs „Grindų įrengimas" vs „Grindų durų montavimas". Keying on
    the head noun merges those three pairs and splits nothing across his six
    sąmatas. The risk it accepts — two genuinely different sections that open
    with the same word — does not occur in his corpus and would show up as one
    section carrying two unrelated families, which is visible rather than
    silent.
    """
    head = _fold(label).split("/")[0]
    for tok in _NONALNUM_RE.sub(" ", head).split():
        if any(ch.isdigit() for ch in tok) or tok in _STOPWORDS:
            continue
        return tok[:_STEM_LEN]
    return _fold(label)[:12] or "kita"


def family_key(name: Any, unit: Any, concept: str | None) -> str:
    """Stable family identity.

    A row the FROZEN table covers is keyed by its concept — that table, not this
    module, decides which of his wordings are the same work. Only what it does
    not cover falls back to the label signature, and that fallback is guarded by
    the unit class so a `m` row and a `m2` row of the same words stay apart.
    """
    if concept:
        return f"c:{concept}"
    stems = _stems(name)
    if not stems:
        stems = (_fold(name)[:24] or "?",)
    return "n:" + "-".join(stems) + "|" + _unit_class(unit)


# ── The frozen concept table, resolved defensively ───────────────────────────

def _concept_table() -> list:
    """The frozen table, or an empty list when it cannot be loaded.

    `scripts/` is not part of the Render image's `COPY` set historically, and
    this module runs behind an API endpoint rather than only in the harness. An
    unavailable table must therefore DEGRADE, not 500: every family falls back
    to `concept=None`, which means every cell renders BLANK with „Iš brėžinio
    nenustatyta — įrašykite". Fail-safe — the failure mode is an empty sheet the
    contractor fills himself, never a number nobody stands behind.
    """
    try:
        return load_concepts()
    except Exception as exc:  # noqa: BLE001 — see docstring
        log.error("concept table unavailable, template runs unmapped: %r", exc)
        return []


def _contractor_concept_of(name: str, table: Sequence) -> str | None:
    """First concept whose `contractor` pattern hits, in the table's own order —
    the SAME rule `row_scorecard.score_rows` applies to his side."""
    return next((c.key for c in table if c.contractor.search(name)), None)


# ── Building ─────────────────────────────────────────────────────────────────

# Order accumulators are integers in MILLIONTHS of a normalised rank. Integer
# addition is exact and associative, so `merge(a, b)`, `merge(b, a)` and a
# single build over the union all land on the identical stored blob.
_ORDER_SCALE = 1_000_000


def _rank_micro(index: int, total: int) -> int | None:
    """Position within a list, scaled to 0…1 (in millionths) so files of
    different length are comparable. A single-element list has no meaningful
    position — `None`, and the caller skips it rather than reading it as
    „first"."""
    if total <= 1:
        return None
    return round(index * _ORDER_SCALE / (total - 1))


def _pick_label(counts: dict[str, int]) -> str:
    """The most frequent wording. Ties break on the SHORTEST — his
    project-specific asides („…miegamajame led apšvietimui įrengti") only ever
    make a label longer — and then alphabetically, so the result never depends
    on dict ordering."""
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))[0][0]


def _pick_unit(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _status_for(seen_in: int, n_sources: int) -> tuple[str, bool]:
    """„įprasta" (default-on) or „kartais" (offered, off by default)."""
    threshold = min(DEFAULT_ON_MIN_SOURCES, max(1, n_sources))
    on = seen_in >= threshold
    return (STATUS_DEFAULT if on else STATUS_OPTIONAL), on


def _blank_template(name: str) -> dict:
    return {"version": TEMPLATE_VERSION, "name": name, "sources": [],
            "n_projects": 0, "sections": []}


def _observe(acc: dict, samata: dict, source: str, table: Sequence) -> None:
    """Fold ONE parsed sąmata into the accumulator.

    `acc` holds, keyed by family: which sections it appeared under, its
    wordings, its units, and the running order accounting. Sections are
    accumulated the same way. Nothing is decided here — `_assemble` does that
    once every source has been seen, so the result cannot depend on the order
    the sources arrived in.
    """
    items = priced_rows(samata.get("line_items") or [])
    if not items:
        return

    # His section order in THIS file, and the rows under each section.
    sections: list[str] = []
    rows_by_section: dict[str, list[dict]] = {}
    for it in items:
        label = _norm(it.get("section")) or EXTRA_SECTION
        if label not in rows_by_section:
            sections.append(label)
            rows_by_section[label] = []
        rows_by_section[label].append(it)

    for s_idx, s_label in enumerate(sections):
        s_key = section_key(s_label)
        sec = acc["sections"].setdefault(s_key, {
            "key": s_key, "labels": {}, "sources": set(),
            "_order_sum": 0, "_order_n": 0,
        })
        sec["labels"][s_label] = sec["labels"].get(s_label, 0) + 1
        sec["sources"].add(source)
        rank = _rank_micro(s_idx, len(sections))
        if rank is not None:
            sec["_order_sum"] += rank
            sec["_order_n"] += 1

        rows = rows_by_section[s_label]
        for r_idx, it in enumerate(rows):
            name = _norm(it.get("name"))
            if not name:
                continue
            unit = _norm(it.get("unit")) or None
            concept = _contractor_concept_of(name, table)
            key = family_key(name, unit, concept)
            fam = acc["families"].setdefault(key, {
                "key": key, "concept": concept, "labels": {}, "units": {},
                "sources": set(), "n_rows": 0, "sections": {},
                "_order_sum": 0, "_order_n": 0,
            })
            fam["labels"][name] = fam["labels"].get(name, 0) + 1
            if unit:
                fam["units"][unit] = fam["units"].get(unit, 0) + 1
            fam["sources"].add(source)
            fam["n_rows"] += 1
            fam["sections"][s_key] = fam["sections"].get(s_key, 0) + 1
            f_rank = _rank_micro(r_idx, len(rows))
            if f_rank is not None:
                fam["_order_sum"] += f_rank
                fam["_order_n"] += 1


def _assemble(acc: dict, name: str) -> dict:
    """Turn the accumulator into the stored shape.

    One decision matters here: a family is attached to EXACTLY ONE section — the
    one it appeared under most often. Letting it sit in two would make
    `render_samata` emit the same concept twice and bill the same app rows on
    two lines, which is the one failure mode worse than a blank cell.
    """
    sources = sorted(acc["sources"])
    n_sources = len(sources)

    sec_order: dict[str, float] = {}
    for s_key, sec in acc["sections"].items():
        sec_order[s_key] = (sec["_order_sum"] / sec["_order_n"] / _ORDER_SCALE
                            if sec["_order_n"] else 1.0)

    families_by_section: dict[str, list[dict]] = {}
    for key, fam in acc["families"].items():
        home = sorted(fam["sections"].items(),
                      key=lambda kv: (-kv[1], sec_order.get(kv[0], 1.0), kv[0]))[0][0]
        seen_in = len(fam["sources"])
        daznumas, default_on = _status_for(seen_in, n_sources)
        families_by_section.setdefault(home, []).append({
            "key": key,
            "label": _pick_label(fam["labels"]),
            "labels": dict(sorted(fam["labels"].items())),
            "unit": _pick_unit(fam["units"]),
            "units": dict(sorted(fam["units"].items())),
            "concept": fam["concept"],
            "sources": sorted(fam["sources"]),
            "seen_in": seen_in,
            "n_rows": fam["n_rows"],
            # How many LINES he bills this family on per sąmata, and whether he
            # has ever used more than one. See `_is_itemised`.
            "rows_per_project": round(fam["n_rows"] / seen_in, 3) if seen_in else 1.0,
            "itemised": _is_itemised(fam["n_rows"], seen_in),
            "section_rows": dict(sorted(fam["sections"].items())),
            "order": (round(fam["_order_sum"] / fam["_order_n"] / _ORDER_SCALE, 6)
                      if fam["_order_n"] else 1.0),
            "_order_sum": fam["_order_sum"],
            "_order_n": fam["_order_n"],
            "daznumas": daznumas,
            "default_on": default_on,
        })

    sections: list[dict] = []
    for s_key, sec in acc["sections"].items():
        fams = families_by_section.get(s_key, [])
        fams.sort(key=lambda f: (f["order"], -f["seen_in"], f["label"], f["key"]))
        sections.append({
            "key": s_key,
            "label": _pick_label(sec["labels"]),
            "labels": dict(sorted(sec["labels"].items())),
            "sources": sorted(sec["sources"]),
            "seen_in": len(sec["sources"]),
            "order": round(sec_order[s_key], 6),
            "_order_sum": sec["_order_sum"],
            "_order_n": sec["_order_n"],
            "families": fams,
        })
    sections.sort(key=lambda s: (s["order"], -s["seen_in"], s["label"], s["key"]))

    return {"version": TEMPLATE_VERSION, "name": name, "sources": sources,
            "n_projects": n_sources, "sections": sections}


def _new_acc() -> dict:
    return {"sources": set(), "sections": {}, "families": {}}


def _acc_from_template(template: dict) -> dict:
    """Reverse `_assemble` back into the accumulator, losslessly.

    Everything the assembly needs survives in the stored shape — that is what
    `labels`, `units`, `_order_sum` and `_order_n` are for — so a merge never
    has to re-read the sąmatas a template was built from.
    """
    acc = _new_acc()
    acc["sources"] = set(template.get("sources") or [])
    for sec in template.get("sections") or []:
        s_key = sec.get("key") or section_key(sec.get("label"))
        acc["sections"][s_key] = {
            "key": s_key,
            "labels": dict(sec.get("labels") or {}),
            "sources": set(sec.get("sources") or []),
            "_order_sum": int(sec.get("_order_sum") or 0),
            "_order_n": int(sec.get("_order_n") or 0),
        }
        for fam in sec.get("families") or []:
            key = fam.get("key") or family_key(fam.get("label"), fam.get("unit"),
                                               fam.get("concept"))
            entry = acc["families"].get(key) or {
                "key": key, "concept": fam.get("concept"), "labels": {},
                "units": {}, "sources": set(), "n_rows": 0, "sections": {},
                "_order_sum": 0, "_order_n": 0,
            }
            for lbl, n in (fam.get("labels") or {}).items():
                entry["labels"][lbl] = entry["labels"].get(lbl, 0) + int(n or 0)
            for unit, n in (fam.get("units") or {}).items():
                entry["units"][unit] = entry["units"].get(unit, 0) + int(n or 0)
            entry["sources"] |= set(fam.get("sources") or [])
            entry["n_rows"] += int(fam.get("n_rows") or 0)
            # `section_rows` is HIS filing histogram, not the home section: a
            # family he files under two headings must round-trip with both, or a
            # later merge could move it and the whole template would re-order.
            # Falling back to the home section keeps a template written before
            # this field readable.
            per_section = fam.get("section_rows")
            if not isinstance(per_section, dict) or not per_section:
                per_section = {s_key: int(fam.get("n_rows") or 0)}
            for sk, n in per_section.items():
                entry["sections"][sk] = entry["sections"].get(sk, 0) + int(n or 0)
            entry["_order_sum"] += int(fam.get("_order_sum") or 0)
            entry["_order_n"] += int(fam.get("_order_n") or 0)
            acc["families"][key] = entry
    return acc


def build_template(samatas: Iterable[dict], *,
                   name: str = "Rangovo šablonas") -> dict:
    """Derive a template from one or more parsed sąmatas.

    Each item is a parsed `contractor_samata_parsed.json` dict; its source name
    comes from `slug`, falling back to `source`, then a positional label. A
    repeated source name is folded once — sources are a SET, so building from a
    list that accidentally contains the same sąmata twice gives the same
    template as building from it once.
    """
    acc = _new_acc()
    table = _concept_table()
    for i, samata in enumerate(samatas or []):
        if not isinstance(samata, dict):
            continue
        source = _norm(samata.get("slug") or samata.get("source")
                       or f"sąmata {i + 1}")[:MAX_SOURCE_LEN]
        if source in acc["sources"]:
            continue
        acc["sources"].add(source)
        _observe(acc, samata, source, table)
    return _assemble(acc, name)


def template_from_samata(samata: dict, *,
                         name: str = "Rangovo šablonas") -> dict:
    """The path a NEW contractor takes: upload one priced sąmata → a template.

    With a single source every family is „įprasta": one sąmata carries no
    evidence about which of his lines are occasional, and defaulting them all
    off would hand him a sheet with nothing on it. The distinction appears the
    moment a second sąmata is merged in.
    """
    return build_template([samata], name=name)


def merge_samata(template: dict, samata: dict, *,
                 source: str | None = None) -> dict:
    """Fold one more sąmata into an existing template.

    Idempotent on the source NAME: merging a sąmata whose name the template
    already lists returns it unchanged, so a double-click cannot inflate
    `seen_in` and flip a „kartais" family to „įprasta".
    """
    acc = _acc_from_template(template or {})
    name = _norm((template or {}).get("name")) or "Rangovo šablonas"
    src = _norm(source or samata.get("slug") or samata.get("source")
                or f"sąmata {len(acc['sources']) + 1}")[:MAX_SOURCE_LEN]
    if src in acc["sources"]:
        return _assemble(acc, name)
    acc["sources"].add(src)
    _observe(acc, samata, src, _concept_table())
    return _assemble(acc, name)


def merge_templates(base: dict, incoming: dict, *,
                    name: str | None = None) -> dict:
    """Union of two templates, exact and order-independent.

    `merge_templates(a, b)` and `merge_templates(b, a)` produce the same result
    because every quantity that survives assembly is a sum or a set union, and
    the label/unit/order decisions are re-made from those.
    """
    acc = _acc_from_template(base or {})
    other = _acc_from_template(incoming or {})
    acc["sources"] |= other["sources"]
    for s_key, sec in other["sections"].items():
        target = acc["sections"].setdefault(s_key, {
            "key": s_key, "labels": {}, "sources": set(),
            "_order_sum": 0, "_order_n": 0})
        for lbl, n in sec["labels"].items():
            target["labels"][lbl] = target["labels"].get(lbl, 0) + n
        target["sources"] |= sec["sources"]
        target["_order_sum"] += sec["_order_sum"]
        target["_order_n"] += sec["_order_n"]
    for key, fam in other["families"].items():
        target = acc["families"].setdefault(key, {
            "key": key, "concept": fam["concept"], "labels": {}, "units": {},
            "sources": set(), "n_rows": 0, "sections": {},
            "_order_sum": 0, "_order_n": 0})
        for lbl, n in fam["labels"].items():
            target["labels"][lbl] = target["labels"].get(lbl, 0) + n
        for unit, n in fam["units"].items():
            target["units"][unit] = target["units"].get(unit, 0) + n
        target["sources"] |= fam["sources"]
        target["n_rows"] += fam["n_rows"]
        for s_key, n in fam["sections"].items():
            target["sections"][s_key] = target["sections"].get(s_key, 0) + n
        target["_order_sum"] += fam["_order_sum"]
        target["_order_n"] += fam["_order_n"]
    label = _norm(name or (base or {}).get("name")
                  or (incoming or {}).get("name")) or "Rangovo šablonas"
    return _assemble(acc, label)


# ── Coverage helpers (used by the hold-out measurement) ──────────────────────

def offered_families(template: dict) -> dict[str, tuple[dict, dict]]:
    """family key → (section, family). Every family the template offers."""
    out: dict[str, tuple[dict, dict]] = {}
    for sec in (template or {}).get("sections") or []:
        for fam in sec.get("families") or []:
            out.setdefault(fam.get("key"), (sec, fam))
    return out


def contractor_family_keys(line_items: Sequence[dict]) -> list[str]:
    """The family key of every priced contractor row, in order — the other half
    of a coverage measurement: `key in offered_families(template)`."""
    table = _concept_table()
    keys: list[str] = []
    for it in priced_rows(line_items):
        name = _norm(it.get("name"))
        unit = _norm(it.get("unit")) or None
        keys.append(family_key(name, unit, _contractor_concept_of(name, table)))
    return keys


# ── Fill eligibility ─────────────────────────────────────────────────────────

def is_verified(row: dict) -> bool:
    """The user stood behind this number: „Teisinga ✓", an accepted review, a
    hand-typed override, or a locked gesture count. Same vocabulary
    `api/recompute_quantities` carries across a rebuild."""
    if row.get("user_verified_at"):
        return True
    if row.get("_review_status") == "accepted":
        return True
    if row.get("manual_override") is True:
        return True
    if row.get("quantity_source") == "manual_override":
        return True
    return bool(row.get("override_locked"))


def is_ledgered(row: dict) -> bool:
    """The row proves its own number.

    `contributions` OR `roll_up`: `extractor/ledger.py` is explicit that a family
    with no per-room driver emits `contributions: []` with a populated
    `roll_up` — „honestly un-decomposable, not silently empty" — and a
    hand-added row has neither. Reading only `contributions` would therefore
    treat a fully-ledgered project-level line as unproven.
    """
    return bool(row.get("contributions")) or bool(row.get("roll_up"))


def is_fillable(row: dict) -> bool:
    """May this row's number go into one of HIS cells?"""
    return is_verified(row) or is_ledgered(row)


# ── Rendering ────────────────────────────────────────────────────────────────

def _app_name(row: dict) -> str:
    return _norm(row.get("aprasymas") or row.get("pavadinimas"))


def _app_unit(row: dict) -> str | None:
    return row.get("mato_vnt") or row.get("vnt")


def _app_qty(row: dict) -> float | None:
    q = row.get("kiekis")
    if q is None or isinstance(q, bool):
        return None
    try:
        return float(q)
    except (TypeError, ValueError):
        return None


def _app_price(row: dict) -> float | None:
    p = row.get("kaina")
    if p is None or isinstance(p, bool):
        return None
    try:
        f = float(p)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") and f != 0 else None


_TRAILING_PAREN_RE = re.compile(r"\(([^()]*)\)\s*$")


def _qualifier(app_label: str, *, short: bool) -> str | None:
    """What tells two lines of ONE itemised family apart.

    `short` takes our label's trailing parenthetical („virš 3 m aukščio",
    „120×60") when it has one — the readable form. The caller falls back to
    `short=False`, our whole wording, when the short forms collide. `None` for
    an empty label; the caller then keeps his label bare.
    """
    label = _norm(app_label)
    if not label:
        return None
    if not short:
        # Our whole wording, flattened: it goes inside a parenthesis after HIS
        # label, and „…dažymas (Sienų glaistymas/dažymas (iki 3m aukščio))" is
        # a nested paren in a document that reaches his client.
        return _WS_RE.sub(" ", label.replace(" (", ", ").replace("(", ", ")
                          .replace(")", "")).strip(" ,")
    hit = _TRAILING_PAREN_RE.search(label)
    return (hit.group(1).strip() or None) if hit else label


def _unit_ok(family_unit: Any, row: dict) -> bool:
    """Unit-compatible, or the family's unit is one we cannot canonicalise.

    An unknown family unit falls through to the concept, which already fixes
    WHICH family is being compared — the same reasoning `row_scorecard` gives
    for folding `kompl` into the count class.
    """
    want = normalize_unit(family_unit)
    if not want:
        return True
    return bool(want & normalize_unit(_app_unit(row)))


def render_samata(template: dict,
                  darbu_sarasas: Sequence[dict],
                  rooms: Sequence[dict] | None = None,
                  *,
                  include_optional: bool = True) -> list[dict]:
    """Render one project through the contractor's template.

    Returns rows in HIS sections, under HIS labels, in the row shape the UI and
    the Excel/PDF exports already read (`aprasymas`, `skyrius`, `mato_vnt`,
    `kiekis`, `kaina`, `id`) plus the source flags below.

    A cell is FILLED only when a template family's concept matches an app row
    whose unit is compatible AND which is verified or ledgered (`is_fillable`).
    A matching but unproven row does not fill the cell — its number rides along
    as `_siulomas_kiekis` with „Patikrinkite prieš naudodami", to be shown
    greyed, never as the value.

    `rooms` is only read to phrase the blank note: with no rooms read off the
    drawing, „Iš brėžinio nenustatyta" would be misleadingly specific.

    Every app row a template family CONSUMES (filled or merely suggested) is
    accounted for exactly once; the rest land in „Kita (iš brėžinio)" under our
    own labels, so nothing we computed is dropped and nothing is billed twice.
    """
    rows = [r for r in (darbu_sarasas or []) if isinstance(r, dict)]
    table = _concept_table()
    by_key = {c.key: c for c in table}
    concept_of = app_concept_of(rows, table)

    rows_by_concept: dict[str, list[int]] = {}
    for i, key in enumerate(concept_of):
        if key is not None:
            rows_by_concept.setdefault(key, []).append(i)

    consumed: set[int] = set()
    out: list[dict] = []
    seen_ids: dict[str, int] = {}
    blank_note = NOTE_BLANK if (rooms or []) else NOTE_NO_ROOMS

    def _row_id(section_label: str, label: str) -> str:
        base = position_id(section_label, label)
        n = seen_ids.get(base, 0)
        seen_ids[base] = n + 1
        return base if n == 0 else f"{base}-{n + 1}"

    for sec in (template or {}).get("sections") or []:
        s_label = _norm(sec.get("label")) or EXTRA_SECTION
        for fam in sec.get("families") or []:
            default_on = bool(fam.get("default_on", True))
            if not include_optional and not default_on:
                continue
            f_label = _norm(fam.get("label"))
            if not f_label:
                continue
            f_unit = fam.get("unit")
            concept = fam.get("concept")
            # An unknown concept key (a stored template built against an older
            # table, or a table that would not load) is treated as unmapped —
            # a blank cell, never a guess about which rows it meant.
            candidates = (rows_by_concept.get(concept, [])
                          if concept and concept in by_key else [])
            usable = [i for i in candidates
                      if _app_qty(rows[i]) is not None and _unit_ok(f_unit, rows[i])]

            # A family HE itemises gets one row per app row instead of one
            # summed row — see ITEMISED_MIN_ROWS. `usable` is a subset of
            # `candidates`; a concept row we could not use (no quantity,
            # incompatible unit) is never consumed, so it still reaches „Kita"
            # rather than vanishing.
            if fam.get("itemised") and len(usable) > 1:
                cells = [[i] for i in usable]
            else:
                cells = [usable]

            # HIS label repeats verbatim on every line of an itemised family, so
            # each row carries the detail that tells them apart. Our labels
            # normally end in it („(virš 3 m aukščio)", „(120×60)"); when those
            # parentheticals COLLIDE — the walls and the ceilings both split
            # „iki 3 m" / „virš 3 m" — they distinguish nothing and the whole
            # label is used instead. Two rows may never render the same text.
            qualifiers: list[str | None] = [None] * len(cells)
            if len(cells) > 1:
                short = [_qualifier(_app_name(rows[c[0]]), short=True)
                         for c in cells]
                if len(set(short)) == len(short) and all(short):
                    qualifiers = short
                else:
                    qualifiers = [_qualifier(_app_name(rows[c[0]]), short=False)
                                  for c in cells]

            for cell, qualifier in zip(cells, qualifiers):
                fillable = [i for i in cell if is_fillable(rows[i])]
                source_ids: list[str] = []
                source_labels: list[str] = []
                kiekis: float | None = None
                siulomas: float | None = None
                kaina: float | None = None
                kaina_source: Any = None
                note: str | None = None

                if fillable:
                    pildymas = FILL_DONE
                    kiekis = round(sum(_app_qty(rows[i]) or 0.0 for i in fillable), 3)
                    used = fillable
                elif cell:
                    pildymas = FILL_SUGGESTED
                    siulomas = round(sum(_app_qty(rows[i]) or 0.0 for i in cell), 3)
                    note = NOTE_UNVERIFIED
                    used = cell
                else:
                    pildymas = FILL_EMPTY
                    note = blank_note
                    used = []

                for i in used:
                    consumed.add(i)
                    rid = rows[i].get("id")
                    if rid:
                        source_ids.append(str(rid))
                    source_labels.append(_app_name(rows[i]))
                    if kaina is None:
                        p = _app_price(rows[i])
                        if p is not None:
                            kaina = p
                            kaina_source = rows[i].get("kaina_source")

                label = f"{f_label} ({qualifier})" if qualifier else f_label

                row = {
                    "skyrius": s_label,
                    "aprasymas": label,
                    "mato_vnt": f_unit,
                    "vnt": f_unit,
                    "kiekis": kiekis,
                    "kaina": kaina,
                    "id": _row_id(s_label, label),
                    # ── source flags ──────────────────────────────────────
                    "saltinis": "rangovo_sablonas",
                    "_sablonas": True,
                    "_sablono_eile": fam.get("key"),
                    # The rendered row wears HIS wording, which the concept
                    # table's `app` patterns are not written against — so it
                    # states its own family, and `row_scorecard.app_concept_of`
                    # reads it. Without this a rendered sheet scores as entirely
                    # unmapped and the hold-out measurement is unreadable.
                    "_concept": concept if (concept and concept in by_key) else None,
                    "_daznumas": fam.get("daznumas") or STATUS_DEFAULT,
                    "_numatytoji": default_on,
                    "_pildymas": pildymas,
                    "_pastaba": note,
                    "_patikslinimas": qualifier,
                    "_siulomas_kiekis": siulomas,
                    "_saltinio_id": source_ids,
                    "_saltinio_eilutes": source_labels,
                }
                if kaina is not None and kiekis is not None:
                    row["suma"] = round(kiekis * kaina, 2)
                if kaina_source is not None:
                    row["kaina_source"] = kaina_source
                out.append(row)

    for i, r in enumerate(rows):
        if i in consumed:
            continue
        label = _app_name(r)
        if not label:
            continue
        out.append({
            "skyrius": EXTRA_SECTION,
            "aprasymas": label,
            "mato_vnt": _app_unit(r),
            "vnt": _app_unit(r),
            "kiekis": _app_qty(r),
            "kaina": _app_price(r),
            "id": str(r.get("id") or _row_id(EXTRA_SECTION, label)),
            "saltinis": r.get("saltinis") or "skaiciuota_is_brezinio",
            "_sablonas": False,
            "_sablono_eile": None,
            # A „Kita" row keeps OUR label, so the regex still reads it right —
            # but stating the concept keeps the whole sheet scored one way.
            "_concept": concept_of[i],
            "_daznumas": None,
            "_numatytoji": True,
            "_pildymas": FILL_DONE if is_fillable(r) else FILL_SUGGESTED,
            "_pastaba": None if is_fillable(r) else NOTE_UNVERIFIED,
            "_patikslinimas": None,
            "_siulomas_kiekis": None,
            "_saltinio_id": [str(r["id"])] if r.get("id") else [],
            "_saltinio_eilutes": [label],
            **({"suma": r["suma"]} if r.get("suma") is not None else {}),
            **({"kaina_source": r["kaina_source"]}
               if r.get("kaina_source") is not None else {}),
        })

    for n, row in enumerate(out, start=1):
        row["nr"] = n
        row["eil_nr"] = n
    return out


# ── Validation (the PUT path) ────────────────────────────────────────────────

def validate_template(payload: Any) -> dict:
    """Bound and normalise a template that arrived over the wire.

    Raises `ValueError` with a Lithuanian message the router turns into a 400.
    Unknown keys are dropped rather than kept: unlike a price-list row (whose
    legacy `vnt` still has a reader), nothing consumes an unknown template
    field, and a stored blob is a storage sink if it accepts arbitrary keys.
    """
    if not isinstance(payload, dict):
        raise ValueError("Netinkamas šablono turinys")
    sections_in = payload.get("sections")
    if not isinstance(sections_in, list):
        raise ValueError("Laukas „sections“ turi būti sąrašas")
    if len(sections_in) > MAX_SECTIONS:
        raise ValueError(f"Šablone per daug skyrių (daugiau nei {MAX_SECTIONS})")

    def _text(value: Any, cap: int) -> str:
        return _norm(value)[:cap]

    def _counts(value: Any, cap: int) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        out: dict[str, int] = {}
        for k, v in list(value.items())[:MAX_FAMILIES_PER_SECTION]:
            try:
                n = int(v)
            except (TypeError, ValueError):
                continue
            key = _text(k, cap)
            if key and n > 0:
                out[key] = n
        return dict(sorted(out.items()))

    def _sources(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        seen = {_text(s, MAX_SOURCE_LEN) for s in value if _text(s, MAX_SOURCE_LEN)}
        return sorted(seen)[:MAX_SOURCES]

    def _number(value: Any, default: float = 1.0) -> float:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return default
        return f if f == f and abs(f) != float("inf") else default

    sections: list[dict] = []
    for sec in sections_in:
        if not isinstance(sec, dict):
            raise ValueError("Netinkamas šablono skyrius")
        s_label = _text(sec.get("label"), MAX_LABEL_LEN)
        if not s_label:
            raise ValueError("Šablono skyrius be pavadinimo")
        fams_in = sec.get("families")
        if not isinstance(fams_in, list):
            fams_in = []
        if len(fams_in) > MAX_FAMILIES_PER_SECTION:
            raise ValueError(
                f"Skyriuje „{s_label}“ per daug eilučių "
                f"(daugiau nei {MAX_FAMILIES_PER_SECTION})")
        families: list[dict] = []
        for fam in fams_in:
            if not isinstance(fam, dict):
                raise ValueError(f"Netinkama šablono eilutė skyriuje „{s_label}“")
            f_label = _text(fam.get("label"), MAX_LABEL_LEN)
            if not f_label:
                continue
            concept = _text(fam.get("concept"), MAX_KEY_LEN) or None
            unit = _text(fam.get("unit"), MAX_UNIT_LEN) or None
            key = _text(fam.get("key"), MAX_KEY_LEN) or family_key(
                f_label, unit, concept)
            seen_in = max(0, int(_number(fam.get("seen_in"), 1)))
            default_on = fam.get("default_on")
            daznumas = _text(fam.get("daznumas"), 32)
            if not isinstance(default_on, bool):
                default_on = daznumas != STATUS_OPTIONAL
            n_rows = max(0, int(_number(fam.get("n_rows"), seen_in or 1)))
            families.append({
                "key": key, "label": f_label,
                "labels": _counts(fam.get("labels"), MAX_LABEL_LEN) or {f_label: 1},
                "unit": unit,
                "units": _counts(fam.get("units"), MAX_UNIT_LEN)
                         or ({unit: 1} if unit else {}),
                "concept": concept,
                "sources": _sources(fam.get("sources")),
                "seen_in": seen_in,
                "n_rows": n_rows,
                # Derived, never trusted from the wire: `itemised` decides
                # whether the render splits a family into one row per app row,
                # and a hand-set `true` on a family he bills once would fan a
                # single line of his into several of ours.
                "rows_per_project": round(n_rows / seen_in, 3) if seen_in else 1.0,
                "itemised": _is_itemised(n_rows, seen_in),
                "section_rows": _counts(fam.get("section_rows"), MAX_KEY_LEN),
                "order": _number(fam.get("order")),
                "_order_sum": max(0, int(_number(fam.get("_order_sum"), 0))),
                "_order_n": max(0, int(_number(fam.get("_order_n"), 0))),
                "daznumas": STATUS_DEFAULT if default_on else STATUS_OPTIONAL,
                "default_on": bool(default_on),
            })
        sections.append({
            "key": _text(sec.get("key"), MAX_KEY_LEN) or section_key(s_label),
            "label": s_label,
            "labels": _counts(sec.get("labels"), MAX_LABEL_LEN) or {s_label: 1},
            "sources": _sources(sec.get("sources")),
            "seen_in": max(0, int(_number(sec.get("seen_in"), 1))),
            "order": _number(sec.get("order")),
            "_order_sum": max(0, int(_number(sec.get("_order_sum"), 0))),
            "_order_n": max(0, int(_number(sec.get("_order_n"), 0))),
            "families": families,
        })

    sources = _sources(payload.get("sources"))
    return {
        "version": TEMPLATE_VERSION,
        "name": _text(payload.get("name"), 200) or "Rangovo šablonas",
        "sources": sources,
        "n_projects": max(len(sources), int(_number(payload.get("n_projects"), 0))),
        "sections": sections,
    }
