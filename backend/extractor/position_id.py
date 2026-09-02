"""Stabilus pozicijos identifikatorius — the durable name of a sąmata row.

WHY (2026-09-02, Patikra P0): until now a position's only identity was its
Lithuanian label. Everything that has to point AT a row — the price the user
typed, a verification stamp, the ripple diff after a recompute, a React key —
had to match on that string, which is why `api/recompute_quantities` keeps a
three-way label index plus a hand-maintained rename map. `ARCHITECTURE.md`
queued "stable line IDs" for exactly this.

THE KEY. `position_id(skyrius, aprasymas)` hashes two things:

  1. the row's section, migrated through `migrate_skyrius_row` — so the
     2026-09-02 sienų/lubų split does not change the id of a row that simply
     moved from the merged section into its surface's own;
  2. the label with its TIER SUFFIX stripped (`tier_key` — the same
     normalisation the price index uses) plus a canonical token naming which
     tier it was.

Point 2 is a deliberate departure from the first sketch of this design, which
wanted the id to be identical across an iki-3m ↔ virš-3m re-tiering. It cannot
be: on the reference project BOTH tier lines exist at once ("Sienų
glaistymas/dažymas (iki 3m aukščio)" and "(virš 3m aukščio)"), as do "GKP lubų
montavimas (standartinis aukštis)" and "(virš 3 m aukščio)" — a tier-blind hash
gives those pairs ONE id, which breaks the uniqueness every consumer of an id
depends on. So the height tier is part of the key and a re-tiered line keeps
being handled by the label passes that already handle it today.

What the id DOES survive: the Q-level suffix ("Sienų šlifavimas" ↔ "Sienų
šlifavimas Q4 (80–120 grit, 100% paviršius)" — never both at once), the section
split, and every rename listed in the merge's legacy map (those are applied
through `LEGACY_LABEL_KEYS` below, kept in step with
`api/recompute_quantities._LEGACY_LABEL_MAP`).

Ids are ASSIGNED in ONE pass at the very end of `_build_pozicijos_from_rooms`,
after consolidation, the Medžiagos extraction and `apply_confidence`, so every
row is already in its final section under its final label.
"""
from __future__ import annotations

import hashlib
import re

# The height/Q-level tier suffixes. Shared with `api/recompute_quantities`
# (`_tier_key`) so the id and the price index can never drift apart.
_TIER_SUFFIX_RE = re.compile(
    r"\s*\((?:iki|virš)\s*3\s*m[^)]*\)"          # (iki 3m aukščio) / (virš 3 m aukščio)
    r"|\s*\(standartinis aukštis\)"               # GKP tier label
    r"|\s*—\s*papildomas darbas dėl aukščio"      # height-premium tail
    r"|\s*q4\s*\([^)]*\)",                         # Q4 sanding suffix
    re.IGNORECASE,
)

# Which tier a stripped suffix names. `q4` maps to nothing on purpose: the Q
# level is a project-wide assumption, so the Q4 line and its plain sibling never
# coexist and folding them keeps a price through a Q toggle.
_TIER_TOKENS = (
    (re.compile(r"iki\s*3\s*m", re.IGNORECASE), "iki3m"),
    (re.compile(r"virš\s*3\s*m", re.IGNORECASE), "virs3m"),
    (re.compile(r"standartinis aukštis", re.IGNORECASE), "std"),
    (re.compile(r"papildomas darbas", re.IGNORECASE), "priedas"),
)

# Legacy labels the canonical builder no longer emits → their successor, at the
# tier-stripped level. A literal copy of `api/recompute_quantities`'s map (that
# module imports this one, never the other way round — the extractor may not
# depend on the API layer). `test_position_id` asserts the two stay identical.
LEGACY_LABEL_KEYS = {
    "praustuvės maišytuvo montavimas":
        "potinkinio praustuvės maišytuvo potinkinės dalies montavimas",
    "dušo maišytuvo sistemos montavimas":
        "potinkinio dušo maišytuvo potinkinės dalies montavimas",
    "dėžučių iš gkp formavimas wc mechanizmams paslėpti":
        "pertvaros sutvirtinimas wc mechanizmams montuoti (gkp dėžutė)",
    "sienų, lubų glaistymas/dažymas": "sienų glaistymas/dažymas",
    "sienų, lubų šlifavimas": "sienų šlifavimas",
}

_WS_RE = re.compile(r"\s+")


def tier_key(s: str | None) -> str:
    """Label with ONLY the height/Q-level tier suffixes stripped, lowercased."""
    return _TIER_SUFFIX_RE.sub("", (s or "").strip().lower()).strip()


def tier_token(s: str | None) -> str:
    """Canonical name of the tier(s) stripped from `s` — "" when none."""
    tokens: list[str] = []
    for hit in _TIER_SUFFIX_RE.findall(s or ""):
        for pattern, token in _TIER_TOKENS:
            if pattern.search(hit) and token not in tokens:
                tokens.append(token)
    return "+".join(tokens)


def id_key(skyrius: str | None, aprasymas: str | None) -> str:
    """The exact string that gets hashed. Exposed for tests and debugging."""
    # Imported here: `vision_call` imports this module, so a module-level import
    # back into it would be circular.
    from .vision_call import migrate_skyrius_row

    section = migrate_skyrius_row(skyrius, aprasymas).strip().lower()
    base = _WS_RE.sub(" ", tier_key(aprasymas))
    base = LEGACY_LABEL_KEYS.get(base, base)
    return f"{section}\x1f{base}\x1f{tier_token(aprasymas)}"


def position_id(skyrius: str | None, aprasymas: str | None) -> str:
    """12 hex chars of sha1 over `id_key`. Same row → same id, every build."""
    return hashlib.sha1(id_key(skyrius, aprasymas).encode("utf-8")).hexdigest()[:12]


def assign_position_ids(pozicijos: list[dict]) -> None:
    """Give every position its `id`, in place. Runs ONCE, at the end of the build.

    Two rows that hash the same would be indistinguishable to everything that
    keys on an id, so the second and later get a deterministic `-N` suffix. That
    net should never fire — `test_position_id` asserts it does not on the
    reference project — but a silent duplicate id is worse than an ugly one.
    """
    seen: dict[str, int] = {}
    for p in pozicijos or []:
        if not isinstance(p, dict):
            continue
        base = position_id(p.get("skyrius"), p.get("aprasymas"))
        n = seen.get(base, 0)
        seen[base] = n + 1
        p["id"] = base if n == 0 else f"{base}-{n + 1}"
