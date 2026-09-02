"""Contribution ledger — how a sąmata line proves its own number.

WHY (2026-09-02, Patikra P0). The builder aggregates ~30 families over the
rooms with `Σ`, keeps no trace of who contributed what, and hands the UI a bare
number. The contractor's question is never "what is the total" — it is *which
rooms are in this, why is the garažas in it, and where do I change the input
that is wrong*. The two halves of that chain already existed (per-room
`calculation_trace`, per-position `kiekis`); they were never joined.

They are joined HERE, by the builder, at emit time. The one architecture this
module exists to reject is the 2026-04-26 one (`interior_v8/universal_engine.
_build_trace_links`), which reverse-engineered which rooms a position covered by
substring-matching Lithuanian words in its label — a second, divergent copy of
the builder's own predicates that drifted the moment either side changed. A
ledger is EMITTED or it is not trustworthy.

────────────────────────────────────────────────────────────────────────────
THE SHAPE (frozen — the frontend renders these keys verbatim)
────────────────────────────────────────────────────────────────────────────

    "contributions": [{
        "room_nr": "110", "room_name": "Miegamasis", "page": 2,
        "value": 58.0, "unit": "m",
        "terms": {"vidiniai kampai": 11.2, "angų atbrailos": 15.3},  # optional
        "included_because": "Sienos dažomos",        # LT, guide-not-confess
        "geometry": "polygon" | "marker" | "none",
    }],
    "excluded": [{"room_nr": "105", "room_name": "Garažas",
                  "excluded_because": "Šios patalpos sienos nedažomos"}],
    "roll_up": [{"op": "sum", "label": "Σ 11 patalpų", "value": 501.3,
                 "note": "…"}],                       # note optional

`roll_up[].op ∈ {sum, cap, share, coefficient, constant, anchor}`.

**Every `value` in `roll_up` is the RUNNING RESULT after that step**, never a
delta — so the chain reads „Σ 11 patalpų 501,30 → riba 0,65 m/m² 107,67" and
**the last value equals `kiekis`, always**. A delta belongs in `note`.

`sum` is the only op whose value the contributions have to reproduce: when the
FIRST step is a `sum`, `Σ contributions[].value` equals it (±0,01). Every other
op is an external fact the line states rather than derives — `anchor` most of
all, because since 2026-09-02 the ceiling quantity is the eksplikacija's own „Iš
viso" minus the rooms nobody paints, which is deliberately NOT Σ-decomposable.
That is why the guard test replays `roll_up`, never a raw Σ.

A family with no per-room driver (elektra, santechnikos symbol counts, the
project-level formulas) emits `contributions: []` with a populated `roll_up`:
honestly un-decomposable, not silently empty. A hand-added row has neither.
"""
from __future__ import annotations

from typing import Any

# What the compat emit and both merge layers must carry onto `darbu_sarasas`.
LEDGER_KEYS = ("contributions", "excluded", "roll_up")

# `Σ terms` may differ from the contribution's own value by this much before the
# terms are dropped as untrustworthy (see `terms_or_none`).
_TERMS_TOLERANCE = 0.02

# How closely a replayed `roll_up` must reproduce `kiekis`.
REPLAY_TOLERANCE = 0.01


def room_geometry(room: dict) -> str:
    """What can actually be pointed at on the drawing for this room.

    "polygon" — a traced outline; "marker" — the printed room-number anchor
    only; "none" — neither, so the UI must not offer a „parodyti brėžinyje".
    """
    if room.get("polygon_pct"):
        return "polygon"
    if room.get("marker_pct"):
        return "marker"
    return "none"


def terms_or_none(value: float, terms: dict[str, float] | None
                  ) -> dict[str, float] | None:
    """`terms`, but only while they still add up to the number they explain.

    A room saved by an older engine can carry sub-terms that no longer sum to
    its total. Showing them anyway would put a visibly wrong equation in front
    of the contractor, which is worse than showing none.
    """
    if not terms:
        return None
    clean = {k: round(float(v), 2) for k, v in terms.items() if v is not None}
    if not clean:
        return None
    if abs(sum(clean.values()) - float(value)) > _TERMS_TOLERANCE:
        return None
    return clean


def contribution(room: dict, value: float, unit: str, included_because: str,
                 terms: dict[str, float] | None = None) -> dict[str, Any]:
    """One room's share of a line, with the predicate that let it in."""
    out: dict[str, Any] = {
        "room_nr": str(room.get("nr") or "").strip(),
        "room_name": (room.get("pavadinimas") or "").strip(),
        "page": room.get("puslapio_nr"),
        "value": round(float(value), 2),
        "unit": unit,
        "included_because": included_because,
        "geometry": room_geometry(room),
    }
    kept = terms_or_none(value, terms)
    if kept:
        out["terms"] = kept
    return out


def excluded(room: dict, excluded_because: str) -> dict[str, Any]:
    """One room this line deliberately leaves out, and why."""
    return {
        "room_nr": str(room.get("nr") or "").strip(),
        "room_name": (room.get("pavadinimas") or "").strip(),
        "excluded_because": excluded_because,
    }


def step(op: str, label: str, value: float, note: str | None = None
         ) -> dict[str, Any]:
    """One roll-up step. `value` is the running result AFTER the step."""
    out: dict[str, Any] = {"op": op, "label": label,
                           "value": round(float(value), 2)}
    if note:
        out["note"] = note
    return out


def sum_step(contributions: list[dict], label: str,
             note: str | None = None) -> dict[str, Any]:
    """The Σ step, valued at exactly what the contributions add up to."""
    return step("sum", label, sum(float(c["value"]) for c in contributions), note)


def rooms_label(n: int) -> str:
    """„Σ 11 patalpų" — the genitive after Σ, the way a contractor reads it.

    Genitive singular after a count ending in 1 (but not 11): „Σ 21 patalpos".
    """
    tail, hundred = abs(n) % 10, abs(n) % 100
    word = "patalpos" if (tail == 1 and hundred != 11) else "patalpų"
    return f"Σ {n} {word}"


def attach(poz: dict, contributions: list[dict], excluded_rooms: list[dict],
           roll_up: list[dict], kiekis: float | None = None) -> dict:
    """Put the ledger on a position and make the chain end at its `kiekis`.

    The last step is FORCED onto the billed quantity: every quantity in this
    codebase is rounded at least twice on its way to a line, so `Σ` of rounded
    per-room values can land a cent away from the number the contractor is
    billed. A chain whose last value is not the billed one is a chain the panel
    would render as a contradiction, so the difference is stated as its own
    step rather than hidden.
    """
    poz["contributions"] = contributions
    poz["excluded"] = excluded_rooms
    target = poz.get("kiekis") if kiekis is None else kiekis
    if roll_up and isinstance(target, (int, float)):
        last = float(roll_up[-1]["value"])
        diff = round(float(target) - last, 2)
        if abs(diff) > 0.005:
            roll_up = roll_up + [step(
                "sum", "Suapvalinta", float(target),
                f"Apvalinimo skirtumas {diff:+.2f}".replace(".", ","))]
    poz["roll_up"] = roll_up
    return poz


def replay(contributions: list[dict] | None, roll_up: list[dict] | None
           ) -> float | None:
    """Walk the chain and return what it claims. None when there is no chain.

    The guard test compares this with `kiekis`. It asserts against `roll_up`,
    never against a raw Σ — the anchored ceiling line fails a naive Σ by
    construction, and that is the honest answer, not a bug.
    """
    if not roll_up:
        return None
    running: float | None = None
    for i, s in enumerate(roll_up):
        value = float(s["value"])
        if i == 0 and s.get("op") == "sum":
            total = round(sum(float(c.get("value") or 0)
                              for c in (contributions or [])), 2)
            if abs(total - value) > REPLAY_TOLERANCE:
                raise AssertionError(
                    f"Σ contributions {total} ≠ first sum step {value} "
                    f"({s.get('label')})")
        if s.get("op") == "cap" and running is not None and value > running + REPLAY_TOLERANCE:
            raise AssertionError(
                f"cap step raised the quantity: {running} → {value}")
        running = value
    return running
