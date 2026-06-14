# Door + Fixture Recall — Results (2026-06-14)

Process: LLM council (5 advisors → peer review) + deep-research workflow (5 facets, cited) → premise-check on the real PDFs → TDD build → live verification. Plan: `2026-06-14-door-fixture-recall.md`.

## The unanimous insight (council 5/5 + research)
**Read the TEXT, not the glyph.** Door frame type is structurally *not* encoded in the plan symbol (a frameless and a standard door draw identically) — it lives in drawing text (tags, annotations, notes). Reading text is Claude's ~90% regime vs ~40% for drawing graphics. **Rejected** (unanimous): the premium-"all frameless" heuristic (N=2 overfit → invisible green over-count), silent `max(plan,schedule)` (over-inflates when text over-lists), more voting (variance ≠ recall), zero-shot detectors (line-art weak; our cv2 over-counted 100×).

## Premise-check on the real PDFs (the Outsider's blind spot, verified)
LT TP PDFs have **no US-style door schedule** with a frame-type column. Door type lives in: plan annotations ("Durų anga iki lubų, skirta beapvadinėms durims"), door tags (Beržų p6: LD-1 ×7 / LD-2 ×3 / LD-3 ×2), and numbered notes ("18. Stumdomos durys"). Fixtures: symbols + appliance labels on the santechnika plan, **no count table**. So the fix is text-annotation/tag reading, not table-schema reading — same principle, adapted source.

## Shipped + measured

### Frameless doors — the big win (commit `feat(doors)`)
`door_type_reader.py`: focused high-res (≤1568px, dodges Claude's silent downscale) Vision pass on door-tag/annotation pages → frameless count. `reconcile_frameless` **raises + flags geltona** when text > glyph, never silently lowers; governing-note default applies only on premium archetype, flagged.

- **Live on Beržų:** reader found **7 frameless** (read the annotation pointing at rooms 104/106–111 + the LD tags) vs the glyph pass's **2**.
- **"Durų angų paruošimas beapvadinėms durims": 10.2 m (−74%) → 35.7 m (−8.9% vs contractor 39.2)** — the worst line in the project, fixed.
- Flagged **🟡** with `"Anotacijose/žymėse rasta 7 beapvadinių durų, pradinis pass rado 2 — patikrink"` (honest disclosure, not a silent overwrite).

### Sanitary fixtures — modest, honest (commit `feat(fixtures)`)
`sanitary_fixture_reader.py`: point-list-then-count (research #3) on the santechnika plan; `reconcile_fixture_counts` raises `detected_symbols_summary` to the higher count (skylių formula consumes it), never lowers, reports raised keys.

- **Live probe on Beržų:** praustuvės **3 → 4** (enumerated each: 105 virtuvė, 106 skalbyklė, 107 vaikų san, 111 tėvų vonia — the 5th genuinely not clearly on the plan). Skylių gręžimas improves toward truth (−29% → ~−11%).
- The harder case (research-confirmed: no fixture schedule); the residual stays flagged. Full closure needs human ground truth / better detection — out of reach now.

## Honesty caveats (skeptic-flagged)
- `contractor_samata_parsed.json` is AI-*parsed*, not human ground truth → these deltas are **directional**, not a published recall %. Human GT remains the standing keystone.
- The ~2.25× "table vs graphics" ratio is single-source/directional; the *direction* is solid and corroborated by our own live result (2→7 doors).

## Net effect on the Beržų line-by-line (vs the pre-fix comparison)
Durys beapvadinės **−74% → −9%** (biggest line moved). Skylių **−29% → ~−11%**. Both now honestly flagged 🟡 with specific reasons. Deterministic core unchanged (paint −5%, GKP +1.6%, etc.). 824 non-network tests pass.
