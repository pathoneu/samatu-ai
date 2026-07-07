# Door-Type + Fixture Recall via Text-First Reading — Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans. Checkbox steps.

**Goal:** Fix the two measured recalls on Beržų (frameless doors −74% / 10.2 vs 39.2 m; fixtures −29% / sinks 3-vs-5) by reading door TYPE and fixture COUNT from **text on the drawing** (tags, annotations, labels — ~90% Claude regime) instead of classifying/counting glyphs (~40% regime, and door type is structurally NOT in the glyph). Reconcile against the plan-detected counts and **surface disagreement as a confidence flag — never silently pick a winner**.

**Council (5/5 unanimous) + deep research (cited) + repo premise-check converged on this.** Rejected: premium-"all frameless" heuristic (N=2 overfit → invisible green over-count), `max(plan,schedule)` silent merge (over-inflates when text over-lists), more voting (variance ≠ recall), zero-shot detectors (line-art weak; our cv2 over-counted 100×).

**Reality (verified in the PDFs, NOT US-style schedules):** door type = plan annotations ("Durų anga ... skirta beapvadinėms durims") + door tags (LD-1 ×7 / LD-2 ×3 / LD-3 ×2 on the išklotinės page) + numbered notes ("18. Stumdomos durys"). Fixtures = symbols + appliance labels on the santechnika plan (no count table).

**Verification (honest):** `ground_truth/<slug>/contractor_samata_parsed.json` is the oracle — BUT it is AI-parsed, not human ground truth, so results are **directional** (did frameless move 2→~8?), not a published recall %. (Human GT remains the standing keystone.)

---

### Task 1: `door_type_reader.py` — focused, high-res, text-first door read
**Files:** Create `backend/extractor/door_type_reader.py`; Test `backend/tests/test_door_type_reader.py`
- [ ] Module: `read_door_types(pdf_bytes, rooms, page_classifications=None, client=None) -> dict`. Clone the multi-page reader pattern from `apdailos_reader.py` (page-find + high-DPI render + Vision call + JSON parse). **Render the door-layout / floor-plan pages at high DPI and keep each image ≤1568px in the LONG dimension** (research #2: Claude silently downscales larger → door tags become sub-pixel). Find pages whose text contains door tags (`LD-\d`, `\bD-?\d`) or "beapvad"/"stumdom"/"durų anga".
- [ ] System prompt (verbatim intent): "Skaitai LT brėžinio DURŲ ŽYMĖJIMUS ir ANOTACIJAS (NE durų grafinį simbolį). Suskaičiuok durų žymes (pvz. LD-1, D-2) ir perskaityk kiekvienos TIPĄ iš teksto/anotacijų: `beapvadines` (paslėpta stakta — anotacija „skirta beapvadinėms durims"), `stumdomos`, `standartines`. Jei brėžinyje yra bendra nuoroda „visos vidaus durys — beapvadinės" — pažymėk `bendras_tipas`. Grąžink TIK JSON."
- [ ] Output schema: `{doors:[{zyme, tipas, kiekis}], beapvadines_count, standartines_count, stumdomos_count, bendras_tipas: "beapvadines"|null, pastabos}`.
- [ ] `merge_door_types_into_rooms(rooms, result, archetipas)`: returns a reconciliation dict; does NOT silently overwrite. (Tested in Task 2.)
- [ ] Tests: page-find picks the tag page over a title page; JSON parse; build_user_text lists rooms; high-DPI cap keeps ≤1568px.

### Task 2: reconcile-and-surface (the merge discipline)
**Files:** Modify `vision_call.py` (door-type wiring + pozicija); Test `test_door_type_reader.py`
- [ ] `reconcile_frameless(plan_frameless, reader_frameless, bendras_tipas, n_interior_doors) -> {count, confidence, reason}`:
  - reader ≈ plan → `count=reader`, **zalia**.
  - reader > plan → `count=reader`, **geltona**, reason `f"Anotacijose/žymėse rasta {reader} beapvadinių durų, pradinis pass rado {plan} — patikrink"`. (Raise; the text is authoritative for type.)
  - `bendras_tipas=="beapvadines"` AND archetipas∈{premium} → frameless = `n_interior_doors` (excl. garažas/tambūras/exterior), **geltona**, reason quotes the governing note. *Narrative-gated, flagged, raise-only — NOT the blunt archetype default.*
  - reader < plan (conflict) → keep plan count, **geltona**, reason surfaces BOTH. Never silently lower.
- [ ] Wire after the doors pass in `extract_interior`; feed the reconciled frameless count into the `pasleptu_duru_staktu` / "Durų angų paruošimas beapvadinėms durims" line.
- [ ] Tests for each branch (agree→zalia, reader>plan→geltona+raise, narrative→geltona, conflict→both surfaced). No network.

### Task 3: fixture-count reconciliation (secondary)
**Files:** Modify `vision_call.py` (skylių + fixture lines); Test `test_finish_semantics.py` or new
- [ ] In the skylių/fixture path, where counts come from `detected_symbols_summary`: when a fixture-label read (or the existing symbols) disagrees with the wet-room-derived expectation, **surface** rather than silently use the lower. Minimal first slice: when `detected_symbols_summary` fixture count < n_wet_rooms-implied minimum, flag the dependent lines geltona with the discrepancy. (Full sanitary-label reader deferred — fixtures have no clean count table; lower ROI than doors.)
- [ ] Test: low symbol count vs wet-room expectation → dependent pozicija flagged geltona.

### Task 4: live verification on Beržų (+ bacveviciaus)
**Files:** `scripts/verify_door_recall.py`
- [ ] Run `read_door_types` live on the Beržų PDF; assert beapvadinės moves from 2 toward ~8 (contractor 39.2 m ÷ ~5 m ≈ 8). Compare reconciled "Durų angų paruošimas beapvadinėms durims" vs contractor 39.2.
- [ ] Re-score the full voted extract with the reconciliation wired; confirm the durys line improves and is flagged honestly; **zero regression** on the already-good quantities (paint, kampai, GKP).
- [ ] Write results to `docs/superpowers/research/2026-06-14-door-recall-results.md` — directional (oracle is AI-parsed), with the 🟡-reconciliation surfaced.

**Out of scope / deferred:** clean schedule-table reader (no such table in LT TP PDFs), full sanitary-label reader, global downscale-fix of the main pipeline (do the targeted high-DPI render in the door reader only), detectors, more voting.
