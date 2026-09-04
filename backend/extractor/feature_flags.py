"""Feature flags read from environment variables.

Each flag controls one accuracy-affecting code path so we can A/B test
and one-line-revert if needed. Defaults to False (off) for safety.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §8.
"""
import os

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

# (env_var_name, default_when_unset)
_FLAG_DEFINITIONS = {
    "per_room_ceiling":      ("ENABLE_PER_ROOM_CEILING", True),          # Sprint 0 Fix 4 → default ON 2026-05-06 (per-room aukštis virš 3m extraction)
    "paint_class_inference": ("ENABLE_PAINT_CLASS_INFERENCE", False),    # Sprint 0 Fix 5
    "verify_pass":           ("ENABLE_VERIFY_PASS", False),              # Sprint 3
    # Sprint 4 Block B: activated default-on after wall_adjacency
    # validated on P1+P3+P5 (grindjuostės ratio drops to 0.5-0.6 m/m²
    # from 0.98 broken double-count). Override with ENABLE_POLYGON_PREPASS=0
    # if regression suspected.
    "polygon_prepass":       ("ENABLE_POLYGON_PREPASS", True),           # Sprint 2 → 4
    "sonnet_pass1":          ("ENABLE_SONNET_PASS1", False),             # Sprint 4
    "grid_overlay":          ("ENABLE_GRID_OVERLAY", False),             # Sprint 3
    "proxy_gt":              ("ENABLE_PROXY_GT", False),                 # Sprint 4
    # 2026-06-06: collapse the per-coat glaistymas/dažymas split (Q1/Q2/sluoksnis,
    # walls+ceilings) into the contractor's combined "Sienų, lubų glaistymas/
    # dažymas (iki/virš 3m)" line (Rangovas A samata items 16/17). Display-only;
    # santrauka totals unchanged. Disable: ENABLE_CONSOLIDATE_PAINT_LINES=0
    "consolidate_paint_lines": ("ENABLE_CONSOLIDATE_PAINT_LINES", True),
    # 2026-06-05: floor SYNTHETIC square perimeters (perim ≈ 4·√area) on plans
    # with NO eksplikacija table, for the wall-paint path only. Gated on
    # plotas_saltinis so eksplikacija/inline_label rooms are NEVER touched →
    # zero regression on read-from-table projects (verified: objektas_a, objektas_b,
    # romainiai → 0 rooms fire). Recovers no-eksplikacija paint: objektas_c
    # -20.3%→-13.5%, objektas_d -14.0%→-5.4%. Disable: ENABLE_PERIMETER_FLOOR_SYNTHETIC=0
    "perimeter_floor_synthetic": ("ENABLE_PERIMETER_FLOOR_SYNTHETIC", True),
    # 2026-06-09: run the high-variance Pass-1 (+ adjacency) N times and
    # median-vote into one consensus extraction. Stabilises kampai (the
    # pusiniai term survives a single adjacency-bail run) and wires the
    # adjacency pass into production so n_partition_walls is populated on
    # real uploads (not just the offline benchmark).
    # → DEFAULT ON after the live A/B on objektas_a (2026-06-09): voted vs single-pass
    #   moved combined paint −5.4%→+2.3%, kampai −32%→−10.6%, recovered per-room
    #   ceiling heights [2.8,3.0,3.4] and n_partition_walls 0→34, at only +13%
    #   wall-clock (once-only downstream passes dominate; consensus already carried
    #   heights so zoom skipped). Disable: ENABLE_EXTRACTION_VOTING=0.
    #   Rounds: VOTING_N (default 3, 2-5).
    "extraction_voting": ("ENABLE_EXTRACTION_VOTING", True),
    # 2026-07-29: run the Pass-1 voting rounds CONCURRENTLY instead of one
    # after another. Measured on the 17-page production run that took 1613 s
    # end to end: the three rounds are ~220 s each and ran strictly serially,
    # so they alone were ~660 s — 41% of the whole extraction — spent waiting
    # on calls that do not depend on one another.
    #
    # ACCURACY IS UNCHANGED BY CONSTRUCTION: identical prompts, identical
    # model, identical round count, and the results are re-ordered back into
    # round order before voting, so the median sees exactly the same input it
    # sees today. What changes is only how long we wait.
    #
    # The cost is prompt cache: today round 1 writes the image prefix and
    # rounds 2-3 read it at 0.1x. Fired together, all three pay full price.
    # PARALLEL_VOTING_WARM=1 keeps round 1 alone first (cache warm, rounds 2..n
    # then concurrent) — less latency won, no extra spend.
    # DEFAULT OFF until measured on a real PDF. Enable: ENABLE_PARALLEL_VOTING=1
    "parallel_voting": ("ENABLE_PARALLEL_VOTING", False),
    # 2026-08-23: identity-safe room matching inside the Pass-1 voter.
    #
    # PROBLEM. extraction_voter groups rooms across the N voting rounds by
    # `nr:<nr>`. On a plan WITH an eksplikacija table the nr is read from the
    # table and is the same physical room in every round. On a plan WITHOUT one
    # the model INVENTS the numbering, and two rounds can number the same rooms
    # differently — so the voter medians two DIFFERENT rooms, and the median of
    # two values is their mean, manufacturing a number no round produced.
    # objektas_c (no eksplikacija) is the worst case in the corpus: round A's nr06
    # is a 4.5 m2 bathroom, round B's nr06 is the 42 m2 open-plan living room
    # (confirmed independently by the adjacency pass: npw 2 vs 5), and the voter
    # emitted a 23.25 m2 "vonia" with an impossible perimeter. 25 of the 452
    # voted rooms that still carry per-round values in this repo (5.5%) have a
    # pairwise area spread > 35%; every one is on a no-eksplikacija plan.
    #
    # FIX. Keep the nr path when the numbering is complete, unique per run,
    # identical across runs AND geometrically coherent; otherwise match by
    # optimal assignment over area/perimeter/name/paskirtis/bbox with a hard
    # area veto. See backend/extractor/vision/room_matcher.py.
    #
    # EVIDENCE (offline, $0). The raw voting rounds are never persisted, so the
    # rounds were RECONSTRUCTED from the saved `_vote.values` blocks. That
    # reconstruction is validated: fed back through the UNCHANGED voter it
    # reproduces the stored production rooms and the stored eval numbers
    # exactly (objektas_c: 6/6 rooms identical, headline 7.462%, category 47.658%).
    #   * blast radius — of the 48 saved voted runs in the repo, 41 keep the nr
    #     path and are byte-identical; the 7 that switch are ALL objektas_c (the
    #     one no-eksplikacija project in the corpus; 6 distinct files).
    #     Incoherent groups (two rooms >35% apart in area medianed together)
    #     go 2-6 -> 0 in every one of them.
    #   * over those 6 distinct objektas_c runs: mean headline MAE
    #     19.40% -> 16.50%, mean category MAE 47.13% -> 45.59%. Headline is
    #     better on 3 and worse on 3, but the wins are big (-4.7, -12.8, -2.3
    #     pp) and the losses small (+1.6, +0.4, +0.2 pp). Per-metric mean
    #     |error|: 7 better (lubos 26.6 -> 21.6, grindys 30.4 -> 25.6, kampai
    #     42.7 -> 41.0, combined paint 11.8 -> 8.4), 1 unchanged, 2 slightly
    #     worse (plytelės 42.7 -> 44.4, rotband 120.0 -> 120.4).
    #   * objektas_d: whole parsed dict bit-identical (table-anchored nrs).
    #
    # WHY IT IS STILL DEFAULT OFF. On the single named benchmark run
    # (ground_truth/objektas_c) headline MAE goes 7.462% -> 9.077%. The whole
    # regression is one metric: sienų dažomas plotas -0.11% -> -3.88%. That
    # -0.11% is luck, not accuracy — the incoherent grouping inflates the
    # floored perimeter (perimeter_floor_synthetic takes max(perim, 4*sqrt(area)),
    # which is convex, so mismatched pairs score HIGHER) by 2.6 m, which happens
    # to cancel a systematic wall under-read. Removing the mismatch removes the
    # accidental compensation. Everything else on that run improves, some of it
    # enormously (plytelės +66.7% -> -5.2%, grindys -33.4% -> -14.5%: the old
    # output claims 92 m2 of tiling in a 93 m2 flat because it believes in a
    # 23.25 m2 bathroom that no round ever saw).
    # The offline replay ALSO cannot test the case that matters most: rooms that
    # today fall out as singletons (objektas_c drops 8 of 20) would rejoin and vote
    # 3-of-3, and their values were never saved. So the production delta is
    # real but unmeasured. Flip this ON for one paid objektas_c + objektas_a A/B before
    # making it the default. Enable: ENABLE_ROBUST_ROOM_MATCHING=1
    "robust_room_matching": ("ENABLE_ROBUST_ROOM_MATCHING", False),
    # 2026-08-23: the WIDENED acceptance paths of the deterministic
    # eksplikacija parser (extractor/pdfplumber_eksplikacija.py).
    #
    # PROBLEM. The 2026-08-23 tolerance rewrite bundled two very different
    # kinds of change. One kind FIXES things and is unconditionally right: the
    # header-driven column map (stop reading the perimeter column as the
    # area), merged-cell position preservation, LT/DE/US decimal + NBSP
    # tolerance, refusing a row with two plausible numbers and no header, and
    # the `_meta` visibility counters. The other kind ACCEPTS MORE: a
    # single-cell row shape, the cross-sheet merge, and a room-name test
    # unioned with the ≥80-label paskirtis classifier. Nothing in the six
    # registry fixtures exercises the second kind, so the corpus gate is blind
    # to it — and on the repo's own real PDFs it goes badly wrong:
    #
    #     03_SA.pdf        34 rows ->  285   (rows off 9 different tables)
    #     1_BD.pdf         15      ->   56   ("2030 1100 2000 2470 2000 950
    #                                         B3 Miegamasis" as a room name)
    #     Projektas..pdf   24      ->   26   — and all 24 are DIFFERENT rows:
    #                                         the 14 real apartment rooms are
    #                                         replaced by the basement table
    #                                         plus "Brėžinys: Rūsio planas.
    #                                         M 1:150" as a 53 m² room.
    #
    # The Projektas case is the dangerous one: the cross-sheet merge picks the
    # LARGEST table as primary and then drops any secondary table whose room
    # numbers collide with it — which on a building where every storey numbers
    # its rooms 1-1…1-6 means a whole storey of real rooms is binned, silently.
    #
    # WHY A FLAG AND NOT A REVERT. The wide paths are not wrong in principle;
    # they are untested. Objektas D is a genuine single-column eksplikacija
    # that only the single-cell path can read, and its four areas match the
    # cached Vision read exactly. Keeping them behind a flag preserves that
    # work and lets it be re-enabled per project or after a real corpus is
    # built, without shipping the over-acceptance to a contractor now.
    #
    # THE COST OF THE CONSERVATIVE DEFAULT: objektas_d goes back to a pdfplumber
    # MISS and falls through to the Vision eksplikacija reader — one extra
    # paid sub-call on that one project shape, same numbers. That is the
    # trade: a known small cost against an unbounded silent-wrong-area risk.
    #
    # Enable: ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE=1
    "eksplikacija_wide_acceptance": (
        "ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE", False),
}


def _resolve(env_value: str, default: bool) -> bool:
    v = (env_value or "").strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    return default


def get_flags() -> dict[str, bool]:
    """Return current feature flag state as {flag_name: bool}.

    Reads from environment variables; defaults per-flag (most are False;
    polygon_prepass defaults True after Sprint 4 Block B validation).
    Truthy: "1"/"true"/"yes"/"on". Falsy: "0"/"false"/"no"/"off".
    Any other value (incl. empty) → flag's default.
    """
    return {
        name: _resolve(os.environ.get(env, ""), default)
        for name, (env, default) in _FLAG_DEFINITIONS.items()
    }


# Back-compat alias for any old code reading _FLAG_ENV_NAMES
_FLAG_ENV_NAMES = {name: env for name, (env, _default) in _FLAG_DEFINITIONS.items()}


def voting_n(default: int = 3) -> int:
    """Number of Pass-1 rounds to run when extraction_voting is on.

    Read from VOTING_N; clamped to [2, 5] (1 defeats the purpose, >5 burns
    budget with diminishing returns). Invalid/unset → default (3).
    """
    try:
        n = int(os.environ.get("VOTING_N", "").strip() or default)
    except (ValueError, TypeError):
        n = default
    return max(2, min(5, n))
