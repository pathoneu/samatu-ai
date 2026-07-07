# Opus 4.8 migration — variance findings + improvement plan (2026-06-17)

After migrating the whole pipeline to Opus 4.8, ran the Beržų fixture 3× (voting on) + a 12-agent review/research/council. The variance data and the code review tell one story.

## The killer finding: the residuals are VARIANCE, not bias

| line | run1 | run2 | run3 | mean | spread | vs contractor |
|---|---|---|---|---|---|---|
| paint iki-3m | 354 | 328 | 330 | 337 | 8% | −9% **stable** |
| **paint virš-3m** | 207 | 138 | 144 | 163 | **43%** | −24% ⚠ |
| LED | 42 | 38 | 48 | 43 | 23% | +1% ⚠ |
| kampai | 410 | 425 | 412 | 416 | 4% | −16% **stable (biased)** |
| **angokraščiai** | 81 | 36 | 41 | 53 | **85%** | — ⚠ |
| **durys beapvad.** | 15.3 | 31 | 21 | 22.5 | **70%** | −43% ⚠ |
| rotband | 119 | 90 | 93 | 100 | 29% | −28% ⚠ |

**paint TOTAL swings −4% (run1) → −20% (runs 2/3)** — run 1 was a lucky draw. The earlier "paint −4%, excellent" was the best of 3.

**Diagnosis (unanimous):** Opus 4.8 has **no temperature knob** (it 400s) — voting is the ONLY stability lever. Pass-1 quantities (paint_iki, kampai) go through N=3 median voting → stable. But the **readers run single-pass AFTER voting** (door_type, sanitary) and the **dimension-dependent lines** (paint_virš = height detection, angokraščiai = opening-dim recall) get NO variance reduction → they jitter. The −61% door run was the low end of a single-sample swing, not a fixed bias.

## Prioritized plan (chairman synthesis)

**#1 — Vote the door_type + sanitary readers (THE headline fix).** Wrap `read_door_types` + `read_fixtures` in N=3 self-consistency, aggregate by **MODE** (median tiebreak — NOT max, which would covertly oracle-fit toward 39.2), flag the spread when reads disagree. The only recall-critical readers bypassing voting. Files: `door_type_reader.py`, `sanitary_fixture_reader.py`, `vision_call.py` (~:2895/:2931). **Acceptance = a *variance* test:** door reader 10× before/after, stdev drops ≥2×. No ground truth needed. **S–M.**

**#2 — Reader image cap 1568→2576px.** The cap's "no provider downscale" comment is **false on Opus 4.8** (max long edge is 2576). The readers reading ~30px tags throw away 2.7× the pixels — a migration-created regression. Centralize `PROVIDER_MAX_IMG_PX` in `prompt.py`. **Measure recall before paying the tokens.** **S.**

**#3 — Wire the human-correction corpus into `eval_harness.py` as a 2nd oracle + tier-split the score.** Kill the blended MAE (kampai is both calibration target AND scored → contamination). Per-class bands (areas ≤3%, counts exact, linear ≤8%; drop the dishonest 0.5% green). Confirmed-value counter gates when frozen formulas thaw. **M.**

**#4 — Prompt-cache Pass-1 images across voting rounds.** Rounds 2–3 are byte-identical → one `cache_control` breakpoint → reads at ~0.1×. Zero accuracy change, funds #1–2. `prompt.py:build_user_content`. **Do FIRST (10 min).** **S.**

**#5 (optional) — Zoom pass effort high→medium + skip low-voter-spread rooms.** ~96s for 1 refinement. Identical numbers, faster. **S–M.**

## Leave FROZEN (anti-N=2-fitting — unanimous)
- **kampai** (`universal_rules.py:1054` `kampai += perim` unconditional; `n_walls_estimate` never set so `4×H`+`perim` always both present). Structurally wrong AND calibrated to Beržų 493.35. Decompose only after N≥3–5 human-confirmed corner counts (wire `n_outer_corners` from `cv_polygon.auto_room_polygon`); it will read WORSE on the AI oracle — that's honest.
- **rotband** (0.30 area share). Wall thickness does NOT fix it (it's an area share, not a length). Freeze until GKP/masonry split + human truth.
- **silikonavimas** (`perim × 2.3`), paint/LED (inside noise floor — report ranges, never chase).
- **Garažas 0.7988 factor** — a 0.9% residual chased to 4 decimals; revert once per-class bands land.

## Opus 4.8 specifics
- No `temperature` → voting is the only determinism lever → #1 is architecturally forced, not optional.
- 1568px reader cap now provably stale (4.8 max 2576) → #2 is a migration-created regression.
- `effort: medium` is the 4.8 sweet spot for perception (#5).
- Pre-migration error-pattern intuitions (door under-fire, kampai bias) describe the OLD model — re-baseline on 4.8 before trusting any of it. Human-confirmed *values* carry over; AI-error *patterns* don't.

## What to watch when testing
Report **ranges across runs**, never point estimates. Confirm #1 aggregates by mode (count must not drift up toward 39.2). #2: recall must actually improve at 2576 before paying tokens. #4: `cache_read_input_tokens > 0` on rounds 2..N.
