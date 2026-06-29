# Beržų line-by-line audit — app output vs Rangovas A samata

**Created 2026-06-06.** Every-line compare of the app's 62 pozicijos vs the contractor's 53-line samata, reading the actual calc code. Living document.

---

## ⛔ 2026-06-09 VERIFIED CORRECTION — READ THIS FIRST (supersedes the verdict below)

**The original audit (everything under "## Verdict" onward) was run with a `_build_pozicijos_from_rooms` call that did NOT pass `detected_symbols_summary`.** That made every symbol-driven line hit its fallback or vanish. Re-running the **true live pipeline (WITH symbols)** overturns several headline findings:

| Original audit claim | Verified live (with symbols) | Status |
|---|---|---|
| difūzorių montavimas — MISSING (symbol==0) | emitted, 6 vnt (symbol=6) | ❌ artifact — line IS present |
| lubinių šviestuvų montavimas — MISSING | emitted, 35 vnt (symbol=35) | ❌ artifact — line IS present |
| skylių gręžimas — 4 vs 56 (−93%, "symbol path silently fails") | live = 40 vs 56 (−29%) | ❌ artifact; path fires. Real gap = recall |
| angokraščiai GKP — 138.42 (+54.8%) | 78.05 (RC3 fix shipped 5ca45ff) | ✅ fixed; now −12.7% (mild under) |
| Rotband — 220.74 (+59%), "share 0.50 stale" | share 0.50→**0.30** (commit, 2026-06-09) | ✅ fixed; now 132.44 (−4.5%) |
| basin mixers 2 vs 5 | RC1 → 3 (max of klozetas/praustuves symbol) | ✅ partial; symbol recall caps at 3 |

**Verified deterministic accuracy (against GT `gt_totals`, contractor-confirmed green):**
- walls_paint 447.73 vs GT 460.71 → **−2.8%** ✅
- ceiling_paint 165.64 vs GT 165.6 → **+0.0%** ✅
- combined paint 613.37 vs GT 584.81 → **+4.9%** ✅
- kampai 501.3 vs 493.35 → **+1.6%** ✅
- Rotband (after fix) 132.44 vs 138.69 → **−4.5%** ✅

**The deterministic math is SOUND.** The two remaining "deterministic-looking" gaps are actually **Vision**, not code:
- **iki/virš-3m split skew** (iki +22%, virš −28%, *combined accurate*): the split method is whole-room, identical to the contractor's. The skew is 100% from Vision room-dims — the app marks only Svetainė (3.40m) as >3m; the contractor's high zone is bigger (Vision got Svetainė smaller than reality and/or missed a 2nd tall room). NOT a split bug.
- **durų angų / beapvadinės durys −56%** (17.1 vs 39.2): Vision tagged 3 doors `pasleptos_duris` but the contractor prepped ~7. Vision under-classifies frameless doors. NOT deterministic — forcing "all interior doors frameless" would overfit berzas.

**True remaining gaps are ALL Vision recall/stability** (the "double down on vision" bucket):
1. Room dims / ceiling heights → iki/virš split + combined paint −10…−14% on bacveviciaus/ciurliu/lazunu
2. Frameless-door classification (3 vs ~7)
3. Symbol undercounts: praustuves 3<5, difuzoriai 6<15, sviestuvai 35<38, skylių 40<56
4. Run-to-run instability (kampai fresh 325 vs cached 501 — wall_adjacency bails silently)

**Lesson:** verify each audit finding against the *full live pipeline* (with symbols) before treating it as a code bug. Isolated calc calls miss the symbol layer entirely.

### 🔴 ROOT CAUSE of the kampai 325-vs-501 instability (2026-06-09, verified)

The user uploads a project → app produces kampai **325** ; contractor truth **493** ; benchmark/cached **501**. Why three different numbers:

- Cached kampai 494.7 decomposes into: inner 126 + reveals 101 + **pusiniai 96.4** (`n_partition_walls`=34) + perim 171.
- **`n_partition_walls` is populated ONLY by the offline script `scripts/apply_adjacency.py`**, which runs a dedicated Vision adjacency pass (`extractor/vision/adjacency_extractor.extract_adjacency`) on the floor-plan page and writes the counts into `ground_truth/<slug>/ai_extract.json`.
- **Production `extract_interior()` NEVER runs that pass.** `grep adjacency_extractor backend/extractor/vision_call.py` → nothing. The deterministic `geometry_solver.detect_shared_walls` also can't help — it needs `polygon_walls`/`start_vertex_xy_mm` in a common frame, which only the heavier `room_graph_extractor` Vision pass produces.
- Therefore in production every room has `n_partition_walls=0` → `pusiniai=0` → kampai loses ~96 m (≈20%). The user's 325 = 398 (no pusiniai) minus further room/element recall shrink (~73 m).

**Consequences:**
1. The whole `pusiniai` mechanism (and the validated 2026-06-01 "default `count_partition_corners=True`" decision at `universal_rules.py:900-908`) is **dead code in production** — the input it needs is never computed.
2. **The totals benchmark overstates production kampai accuracy** by ~96 m, because `eval_harness` reads the offline-enriched `ai_extract.json` that already has `apply_adjacency` baked in. Benchmark kampai +1.6% ; real production kampai ≈ −19%.

**Fix options (decision pending):**
- **A. Wire the adjacency Vision pass into `extract_interior`** (feature-flagged, graceful fallback to n_partition_walls=0 + low-confidence flag on failure). +1 Vision call/extraction (~$0.05–0.20). Makes prod kampai match truth; closes the benchmark-vs-prod gap. *Recommended.*
- **B. Keep prod cheap**: drop/neutralize the dead pusiniai path, flag kampai low-confidence, accept ≈ −19% (or recalibrate the legacy perim term — fragile single-project fudge).
- **C. N-pass voting** over the whole extraction for full stability (bigger build, ~3× cost) — addresses room/element recall variance too, not just pusiniai.

---

---

## 🚨 2026-06-09 PART 2 — THE BENCHMARK WAS MEASURING LOST CODE (live A/B + .pyc forensics)

A live re-extraction of the berzas PDF (single-pass production, `/tmp/berzas_A_single_pass.json`)
vs the cached benchmark extract exposed that **production is massively degraded vs the benchmark,
because several pipeline passes silently broke and the benchmark reads pre-breakage cached extracts.**

**Live single-pass production vs contractor truth (the numbers a real user gets):**
- kampai **313.5 (−36.5%)** — reproduces the user's "got 325" report. n_partition_walls=0.
- combined paint **438.6 (−25%)** ; walls_paintable 273 vs GT 460.7 (**−41%**).
- ceiling heights: **uniform 2.82 m** on all 11 rooms (cached: 2.8/3.0/3.4).

**Root causes (all adversarially verified by the recover-lost-readers workflow):**

1. **`apdailos_reader.py` + `doors_reader.py` were NEVER committed and are LOST.** `git log --all`
   returns nothing; only stale `.pyc` remained in `__pycache__`. The committed `vision_call.py` calls
   them (Step 2.85/2.86) inside `try/except` that swallowed the `ModuleNotFoundError` as "non-fatal".
   So for weeks: no `sienu_apdailos_breakdown` → calc falls to the legacy paskirtis path that hardcodes
   `walls_paint=0` for tamburas/garazas and full-tile-clips wet rooms → **−41% walls paint**; and no
   door recount → doors stuck at pass-1's 9–10 (truth 14).
   **The commit that claimed "Beržų MAE 3.25%→1.15%" (`c91dd3b`) depended entirely on these two
   uncommitted modules.** The benchmark still reports ~1.1–2% because `eval_harness --totals-only`
   reads the *cached* `ai_extract.json` that was built when the modules existed locally.
   → **FIXED 2026-06-09**: both modules reconstructed faithfully from the surviving `.pyc` (verbatim
   SYSTEM_PROMPTs, output schemas, signatures, MODEL/MAX_TOKENS) + the universal_rules consumer
   contract. ImportError on a reader is now a LOUD regression warning.

2. **Per-room ceiling zoom ran 1/11 rooms → uniform 2.82 m.** Two compounding bugs: (A) the zoom loop
   mutated a stale `rooms` binding while `_apply_per_room_heights` had reassigned `parsed["patalpos"]`
   to a new list — so zoom recovery was silently discarded; (B) `_can_skip_zoom` skipped every
   eksplikacija-matched room, but ceiling height is NOT an eksplikacija primitive.
   → **FIXED 2026-06-09**: rebind `rooms = parsed["patalpos"]` before the zoom loop; don't skip zoom
   when `lubu_aukstis_saltinis != "per_room"`.

3. **Adjacency pass not in production** (the kampai pusiniai gap from Part 1) + my initial voting wiring
   ran adjacency on `pages[0]` (a title sheet) instead of the floor page → 0 matches.
   → **FIXED 2026-06-09**: voting path resolves the floor page (scale_source_page / modal puslapio_nr)
   and applies adjacency there.

**Benchmark integrity (CRITICAL, confirmed):** `eval_harness --totals-only` scores against the
enriched cached `ai_extract.json`, NOT fresh production. Honest berzas headline MAE ≈ **14.95%**, not
the published 1.99% — a **~7.5× understatement** on enrichment-dependent projects. The "~3× overall"
across all 11 projects is plausible but UNVERIFIED (fresh extracts exist only for berzas). **TODO**:
regenerate every `ground_truth/<slug>/ai_extract.json` with the restored pipeline, OR flag any extract
lacking apdailos/adjacency markers as `stale_enriched` and exclude it from the headline MAE. Also: the
eval "honest filter" silently drops headline metrics a fresh extract emits as exactly 0.0 — for non-berzas
projects that would HIDE a collapsed metric; remove/flag that when scoring real production extracts.

**Live re-verification of the full restoration: in progress (`/tmp/berzas_restore_verify.log`).**

### 2026-06-09 PART 3 — benchmark-honesty regeneration ATTEMPTED, blocked on API credit

Full write-up: **`docs/superpowers/research/2026-06-09-benchmark-honesty-regen.md`**.

Acted on the PART-2 TODO ("regenerate every `ai_extract.json` with the restored
pipeline"). Backed up all cached extracts → `eval_runs/cached_baseline_backup_2026-06-09/`
(sha256-verified; git HEAD also preserves them). Fixed the eval "honest filter"
(`eval_harness.py`): a *fresh* extract emitting `0.0` vs a real >0 truth now scores
as the genuine −100% collapse **and** prints a `🔴 COLLAPSED METRICS` footnote
(silent-drop kept only for legacy `replay`). Wrote `scripts/regenerate_truth_extracts.py`
(`run_vision_on_truth_set.py` can't refresh berzas — it filters out `has_cached_extract`).

**The live run ran out of Anthropic API credit after $2.31.** Result:
- ✅ **ciurliu, lazunu** regenerated honestly. ciurliu MAE **11.53% → 27.42%** (enriched
  cache overstated accuracy **2.4×**, partly a lost room 7→6). lazunu **10.61% → 10.24%**
  (enrichment barely mattered there).
- ⚠️ **berzas** died on voting round 3; apdailos+doors passes failed → paint-degraded
  artifact → **rolled back to enriched baseline** (not scored — its collapse was a credit
  artifact, not the pipeline).
- ❌ **bacveviciaus, romainiai** never written (all Vision calls 400'd) → enriched baseline.

So the benchmark is **partially honest** (overall 6.658% → 9.479%, a mixed figure).
**To finish: top up credits, re-run `scripts/regenerate_truth_extracts.py --only berzas`
(+ bacveviciaus, romainiai), then `eval_harness.py --totals-only`.**

---

> ⚠️ VALUES below are from the **cached** berzas extract AND a no-symbols `_build_pozicijos` call. **Several findings below are corrected by the tables above — do not act on the verdict/per-line claims without cross-checking the 2026-06-09 corrections.** Per-line fresh-vs-cached deltas TBD.


## Verdict
The app reproduces the contractor samata reasonably at the AGGREGATE/total level but diverges badly LINE-BY-LINE, especially on structure, fixture counts, and height/zone splits. Of the 53 contractor lines, only ~13 are clean matches; the app over-quotes on roughly 6 lines (most importantly Rotband +59% and both angokraščiai lines +55%), under-quotes on ~10 (basin mixers 2 vs 5, beapvadinės durys -56%, skylių gręžimas 4 vs 56, high-ceiling zone splits), and entirely MISSES ~19 contractor lines (all recessed fixtures — 38 šviestuvai, 15+21 difūzoriai, 20 m TRACK; all wall-GKP work — niches, thickening, glued leveling; bidė, dryer, exterior tap; tile skirting and large-format tile). It also emits ~14 EXTRA lines the contractor doesn't itemize — mostly legitimate bill-of-materials (lapai/CD/UW/savisriegiai/plytelės×1.08/fugavimas) plus two real double-count risks (the kampai triple-emission and the height-premium stacking) and two possibly-invented lines (Lubų karnizas ~€700, Slenksniai). The single worst structural gap is SECTION 1 (GKP), where the data model has no concept of wall GKP, recessed fixtures, or track lighting, so 9 of 14 lines are missing. The headline bugs are all in code and verified: rotband_share=0.50 is stale (vision_call.py:1145), the inline reveal recompute (vision_call.py:1257+) ignores the calibrated per-room angokrasciu_gkp_m field (universal_rules.py:1027), kampai depends on flaky wall_adjacency, and the skylių-gręžimas symbol path silently fails to fire. Bottom line: totals look ~right by luck of cancelling errors; the app is NOT yet trustworthy as a line-by-line samata against this contractor.


## Counts
Across all 53 contractor lines:
- #match = 13 (lines 1,3,7,30,31,33,44,47,48,49,50,52,53 — incl. loose/count matches; latakai 33 matches but in a different skyrius)
- #over = 6 (line 2 GKP-zone is UNDER but TOTAL ceiling GKP is under; OVER lines = 14 angokr GKP +54.8%, 15 Rotband +59.2%, 16 paint-iki3m +22.1%, 36 45°-pjovimas +15%, plus angokraščiai glaistymas twin +54.8%, and aggregate wall-tile +9%)
- #under = 11 (line 2 GKP virš-3m -19.5%, 17 paint-virš3m -28%, 18 beapvadinės durys -56.4%, 26 floor-tile -20%, 29 lentynėliai -20%, 32 skylių gręžimas -93%, 34 silikonavimas -36%, 40 praustuvo maišytuvas -60%, 41 praustuvo virštinkinė -60%, plus per-bathroom wall-tile san107 -37%/san111 -25%)
- #missing-in-app = 19 (lines 4,5,6,8,9,10,11,12,13 in §1; 20,21,22 in §2; 27,28,35 in §3; 37,45,46,51 in §4) — recessed fixtures, wall GKP, track, tile skirting, large-format tile, bidė, dryer, exterior tap, reveal sealing
- #extra-in-app ≈ 14 (§1: GKP lapai, CD profiliai, UW profiliai, siūlių glaistymas, savisriegiai, reviziniai dureliai; §2: Glaistymo kampai vidiniai, Glaistymo kampai išoriniai [double-count of montavimas], Lubų karnizo montavimas, Lubų karnizo dažymas, Grindjuosčių mont.+dažymas; §3: plytelės-material ×1.08, fugavimas lines, Slenksniai; §4: Pastolių nuoma, Statybvietės sutvarkymas, Apsauginės dangos)
NOTE: several contractor lines are not strictly 1:1 (app splits by room-class, contractor by tile-format / potinkinė-virštinkinė), so over/under counts above blend line-level and aggregate-level verdicts; see master table.


---
# FULL PER-LINE ANALYSIS (every section, every line)


## SECTION 1 — GKP montavimas (Gipso kartono montavimas). Contractor samata lines 1-14 vs app skyrius "GKP montavimas" (11 lines). NOTE: this is the worst-aligned section in the whole audit — the app's data model only tracks CEILING GKP (gkp_lubu_standart_m2 / gkp_lubu_virs_3m_m2) plus a few reveal/box/niche lines. It has NO concept of GKP partitions, wall reinforcements, recessed light fixtures (difuzoriai/šviestuvai/TRACK), or duct boxes. As a result 9 of 14 contractor lines are MISSING-in-app, and the app emits 7 EXTRA bill-of-materials lines (CD/UW profiliai, savisriegiai, siūlių glaistymas, lapai) that the contractor never itemizes because they are bundled into the m² install rate.


### Per-line
nr | samata item | samata kiekis | app match | app kiekis | STATUS | note
1 | GKP montavimas ant lubų, dvigubas karkasas 2,8m aukštis | 102.78 m² | "GKP lubų montavimas (standartinis aukštis)" | 104.43 m² | MATCH (+1.6%) | App's standard-height ceiling-GKP total (gkp_lubu_standart_m2, universal_rules.py:827) lands within 5% of the contractor's 2.8m line. Clean win. Caveat: this is partly coincidence — app's "standartinis" = all rooms with H≤3m, contractor's "2,8m" is a specific height band; numerator alignment is luck of room mix.
2 | GKP montavimas ant lubų, dvigubas karkasas 3,4m aukštis | 62.82 m² | "GKP lubų montavimas (virš 3 m aukščio)" | 50.54 m² | UNDER (-19.5%) | App high-ceiling slice (gkp_lubu_virs_3m_m2, universal_rules.py:828/825) is 50.54 vs 62.82. The app's >3m threshold (high_ceiling_threshold_m) vs contractor's "3,4m" band don't carve the same rooms; app under-attributes ~12 m² to the high zone. Sum check: app total ceiling GKP = 104.43+50.54 = 154.97 m² vs contractor 102.78+62.82 = 165.60 m² → app UNDER -6.4% on total ceiling GKP (the zone split is just more wrong than the total).
3 | Nišų formavimas iš GKP (paslėptam apšvietimui, užuolaidų karnizams) | 42.3 b/m | "Nišų formavimas GKP konstrukcijoje" | 41.88 m | MATCH (-1.0%) | nisu_metrai (vision_call.py:617 _calc_nisu_metrai_m, summed at :1366/:1371). Excellent match. Unit "b/m" (bėg.m) == app "m". Same source feeds LED nišų glaistymas/dažymas in the paint skyrius (also 41.88) — consistent.
4 | GKP "dėžučių" montavimas ant lubų (žeminimas, aukštinimas) | 11.16 m | (none) | — | MISSING-in-app | App has NO ceiling-soffit/box line. gkp_extra_area_m2 (universal_rules.py:834) exists as a per-room override for "karobkė" soffits but is never populated by extraction and is folded into the m² standard line, not a separate "dėžutės" m line. The contractor bills this as linear m of dropped/raised ceiling boxes. No equivalent.
5 | Nišų pertvarose įrengimas | 9.11 m | (none) | — | MISSING-in-app | Wall-niche recesses. App only models LED/curtain ceiling niches (nisu_metrai), not partition-wall niches. No field, no line.
6 | Pertvarų storinimas miegamajame led apšvietimui | 6.24 m² | (none) | — | MISSING-in-app | Wall thickening for LED. App data model has no wall-GKP / wall-thickening concept (sienos_gkp_m2 is hardcoded 0 — see vision_call.py:1404 and build_gkp_pozicijos comment :776). MISSING.
7 | Pertvaros sutvirtinimas WC mechanizmams | 2 vnt | partially → "Dėžučių iš GKP formavimas WC mechanizmams paslėpti" (2 vnt) | 2 | MATCH-ish (count) | App's WC-mechanism box line (vision_call.py:1652-1661, n_wet_klozetas, 1 per wet room) = 2 vnt, numerically equal. Semantically the app line is the GKP enclosure box ("dėžutė"), contractor line 7 is the partition reinforcement for the concealed cistern. Arguably the app's box line double-serves as both #7 (reinforcement) and #12-style boxing — count matches but it's a loose mapping.
8 | Gipso kartono klijavimas sienai išlyginti katilinėje | 9.64 m² | (none) | — | MISSING-in-app | Glued GKP to level a katilinė wall. App katilinė ("katiline") paskirtis uses Rotband wall-leveling (universal_rules.py:197 ceiling gkp), not glued wall GKP. No wall-GKP line exists → MISSING.
9 | Priglaistomų gipsinių difūzorių montavimas (apvalių) | 15 vnt | (none in GKP skyrius) | — | MISSING-in-app | Round plaster-in diffusers. App routes difuzoriai to "Elektros instaliacijos darbai" skyrius (vision_call.py:1848-1860) and ONLY when symbols.difuzoriai is detected (==0 on this fixture → no line emitted at all). MISSING from GKP and effectively missing from output.
10 | Lubinių priglaistomų šviestuvų montavimas | 38 vnt | (none in GKP skyrius) | — | MISSING-in-app | Plaster-in ceiling lights. Same as #9: app emits "Lubinių priglaistomų šviestuvų montavimas" only under Elektros skyrius and only if symbols.sviestuvai>0 (vision_call.py:1825-1830). Not detected on this fixture → MISSING.
11 | Magnetinės TRACK apšvietimo sistemos montavimas | 20.06 m | (none) | — | MISSING-in-app | Magnetic track lighting. App has NO track-lighting concept anywhere. MISSING.
12 | Dėžutės montavimas ortakiams garaže paslėpti | 1 vnt | (none) | — | MISSING-in-app | Duct-boxing in garage. App garažas is betonas-ceiling, walls_paint=0 (universal_rules.py:201); gkp_extra_area_m2 soffit override exists but is never populated. No duct-box line. MISSING.
13 | Angokraščių sandarinimas | 89.39 m | partially → covered by app's "Angokraščių glaistymas-dažymas" 138.42 m (paint skyrius) — no GKP-skyrius sealing line | — | MISSING-in-app (as distinct line) | Contractor itemizes reveal SEALING (sandarinimas, line 13) separately from reveal GKP-finishing (line 14), both at 89.39 m. App collapses to ONE structural GKP line (#14 below) and one paint line; no separate sealing line. See also kiekis mismatch in #14.
14 | Angokraščių apdirbimas GKP | 89.39 m | "Angokraščių apdirbimas GKP (struktūra)" | 138.42 m | OVER (+54.8%) | app angokrasciai_m (vision_call.py:1257-1286, Σ(2H+W) over langas/duris/pasleptos_duris that pass reveal threshold). App OVER by +54.8%. Contractor 89.39 m vs app 138.42 m. The app counts reveal contour for ALL qualifying openings incl. interior windows/doors; contractor's GKP reveal line is only 89.39 m (likely excludes some interior openings or door-only). NOTE the universal_rules.py:958 comment claims angokrasciu_m = 89.51 vs truth 89.39 (+0.13%) — but the ACTUAL app output here is 138.42, meaning the production path (_build_pozicijos_from_rooms reveal loop at :1257, which uses _opening_adds_reveal gating) diverges from the calc_room_quantities angokrasciu_m field (:959). Two different reveal computations exist and they disagree by 55% — this is a real bug surface.


### Missing in app
9 of 14 contractor lines have NO app equivalent — this section is mostly uncovered:
- Line 4 (GKP dėžučių ant lubų, 11.16 m) — dropped/raised ceiling boxes. App has gkp_extra_area_m2 override but it is never populated and is m² not m. HIGH value (~real labor).
- Line 5 (Nišų pertvarose, 9.11 m) — wall niches. No wall-niche field.
- Line 6 (Pertvarų storinimas LED, 6.24 m²) — wall thickening. App's sienos_gkp_m2 is hardcoded 0.
- Line 8 (GKP klijavimas sienai katilinėje, 9.64 m²) — glued wall GKP. No wall-GKP line.
- Line 9 (Difūzorių montavimas, 15 vnt) — only emitted under Elektros skyrius and only if symbol-detected; ==0 here → absent.
- Line 10 (Lubinių šviestuvų montavimas, 38 vnt) — same: Elektros-only, symbol-gated, absent.
- Line 11 (Magnetinė TRACK sistema, 20.06 m) — no concept anywhere.
- Line 12 (Dėžutė ortakiams garaže, 1 vnt) — no duct-box line.
- Line 13 (Angokraščių sandarinimas, 89.39 m) — no separate reveal-sealing line (app only has structural + paint reveal lines).
Combined, the missing lines represent the bulk of this section's labor (38 recessed lights + 15 diffusers + 20 m track + 4 box/niche/thickening lines). The app's "GKP montavimas" skyrius is essentially only ceiling-sheet area + reveals + 2 box counts.


### Extra in app
App emits 7 GKP-skyrius lines that the contractor does NOT itemize (they are bundled into the per-m² ceiling-GKP install rate). These are bill-of-materials/sub-task lines, mostly legitimate-but-noisy for a contractor-style KŽ:
- "GKP lapai luboms (9.5 mm)" 57 vnt (build_gkp_pozicijos, vision_call.py:805-813) = ceil(154.97/3.0×1.10)=57. Sound math, but a material count the contractor folds into the m² line. NOISE for contractor comparison; legit for a material list.
- "GKP karkaso CD profiliai (laikantieji)" 247.95 m = gkp_total×1.6 (vision_call.py:1411). Material, not a billed work line.
- "GKP karkaso UW profiliai (pakraščio)" 61.99 m = gkp_total×0.4 (vision_call.py:1412). Material.
- "GKP siūlių glaistymas + armavimo juostelė" 232.45 m = gkp_total×1.5 (vision_call.py:1422). Sub-task bundled into install.
- "Savisriegiai GKP montavimui" 4649 vnt = int(gkp_total×30) (vision_call.py:1426). Material (=154.97×30=4649). Correct arithmetic.
- "Reviziniai dureliai" 2 vnt (vision_call.py:1432, 1 per wet room) — LEGIT line the contractor happens not to list in SECTION 1 (it's a real item; not a double-count).
- "Angokraščių apdirbimas GKP (struktūra)" 138.42 m — this is the app's match for line 14 but at the wrong (over) quantity; counted above, not double-listed here.
Verdict: the 5 material/profile/screw lines (lapai/CD/UW/siūlės/savisriegiai) are NOT double-counts of each other (each is a distinct BoM item derived from the same gkp_total), but as WORK lines they are noise vs the contractor's labor-rate model. They inflate the line count and, if priced as separate labor, would double-bill against the m² install line.


### Calculation-method issues
Per app line, source + soundness:
- "GKP lubų montavimas (standartinis/virš 3m)": gkp_lubu_standart/virs_3m from universal_rules.py:813-828. Gated to ceiling_type in ("gkp","tempiamos"); vonia/wc/san are "pakabinamos" (line 190-192) so excluded — correct (painter doesn't install suspended ceilings). High/low split uses high_ceiling_threshold_m (>3m) vs contractor's 2,8m/3,4m bands → split is method-mismatched (drives line-2 UNDER). Total ceiling GKP (154.97) is sound; the zone partition is not.
- "Nišų formavimas": _calc_nisu_metrai_m (vision_call.py:617). Correctly sums ilgis_m WITHOUT multiplying by kiekis (fix documented at :620-623). Sound. 41.88 vs 42.3 = good.
- "Angokraščių apdirbimas GKP (struktūra)": vision_call.py:1257-1286 loop. PROBLEM: this production path (Σ(2H+W) for all langas/duris/pasleptos_duris passing _opening_adds_reveal) yields 138.42 m, while calc_room_quantities.angokrasciu_m (universal_rules.py:959, which excludes EXTERIOR windows via is_exterior at :973-976) is documented to yield 89.51 m. The two reveal calculators disagree because the _build_pozicijos path at :1267 includes "langas" WITHOUT checking the _exterior flag (unlike universal_rules.py:974). That is almost certainly the +55% over-count root cause: exterior facade windows are being counted into interior reveal GKP. This is the single highest-impact bug in the section.
- "GKP lapai/CD/UW/siūlės/savisriegiai": all linear scalings of gkp_total (×1.6, ×0.4, ×1.5, ×30) and ceil(area/3×1.1). Arithmetic verified correct. Method concern is categorical (materials posing as work lines), not numeric.
- "Reviziniai dureliai" / "Dėžučių WC mechanizmams": both = count of wet rooms (n_wet_klozetas / WET set). 2 vnt each. Sound as counts; the WC-box line is a loose stand-in for contractor line 7.
- Unit integrity: all app lines use correct units (m²/m/vnt) and no unit/quantity mismatches detected. The issue is coverage, not units.


### Section to-fix
HIGH priority:
1. Fix the angokraščiai over-count (line 14): the _build_pozicijos_from_rooms reveal loop (vision_call.py:1267) counts "langas" without honoring the _exterior flag, producing 138.42 m vs contractor 89.39 m (+55%). Make it use the SAME exterior-window exclusion as universal_rules.py:973-976 (or reuse room["angokrasciu_gkp_m"] directly instead of recomputing). One source of truth for reveals.
2. Add a separate "Angokraščių sandarinimas" line (contractor line 13, 89.39 m) — currently no reveal-sealing line exists; contractor bills it separately from reveal-GKP finishing.

MED priority:
3. Recessed-fixture lines are absent because they are symbol-gated and route to Elektros skyrius: contractor lines 9 (difūzoriai 15), 10 (šviestuvai 38), 11 (TRACK 20.06 m) are the biggest missing labor in this section. Either (a) surface them as placeholder GKP/Elektros lines even when symbol detection returns 0 (so the user can fill kiekis), or (b) improve difuzoriai/sviestuvai/track symbol detection. As-is the app silently drops 53+ fixture installs.
4. Fix the high-ceiling GKP zone split (line 2 UNDER -19.5%): align the >3m threshold logic with how rooms actually carry high coffers, or at least flag that the standartinis/virš-3m split is approximate. Total is fine (-6.4%); the split is the problem.
5. Add wall-GKP support to the data model (sienos_gkp_m2 is hardcoded 0, vision_call.py:1404): unlocks contractor lines 5 (wall niches), 6 (pertvarų storinimas), 8 (glued wall GKP). Currently structurally impossible to emit.

LOW priority:
6. Add a linear ceiling-box line for contractor line 4 (GKP dėžutės ant lubų, 11.16 m) and line 12 (duct box in garage) — populate gkp_extra_area_m2 / a new box field from extraction instead of leaving the override empty.
7. Categorize the 5 BoM lines (lapai/CD/UW/siūlės/savisriegiai) as MATERIALS, not work positions, so a contractor-mode KŽ collapses them into the m² install rate and doesn't risk double-billing labor against the install line.


## SECTION 2 — Sienų lubų glaistymas dažymas (contractor items 15–23) vs app skyrius "Sienų lubų glaistymas dažymas"


### Per-line
nr | samata item | samata kiekis vnt | app match (aprasymas) | app kiekis | STATUS | note

15 | Sienų lyginimas sausu gipsiniu tinku "Rotband" | 138.69 m2 | "Sienų lyginimas Knauf Rotband" | 220.74 m2 | OVER (+59.2%) | Computed walls_paint(441.48) × rotband_share(0.50). The 50% default was calibrated (2026-05-27 comment, vision_call.py:1140-1145) against walls_paint=277.33 → 138.69. But the current pipeline now yields walls_paint≈441.48 (≈59% growth), so 50% of it = 220.74. Contractor 138.69 = only 31.4% of today's walls_paint. Calibration is stale.

16 | Sienų, lubų glaistymas/dažymas (iki 3m aukščio) | 371.4 m2 | "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)" | 453.42 m2 | OVER (+22.1%) | Consolidated line from _consolidate_paint_pozicijos (vision_call.py:983-1071). iki_3m = dazymo_total(607.11) − virs_3m(153.69). The combined dažymas total (607.11) MATCHES contractor 16+17 sum (584.81) at +3.8% — the problem is the height-zone SPLIT is wrong, not the total.

17 | Sienų, lubų glaistymas/dažymas (virš 3m aukščio) | 213.41 m2 | "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)" | 153.69 m2 | UNDER (−28.0%) | virs_3m = Σ(walls+ceiling per room where lubu_aukstis_m>3.0) (vision_call.py:1012-1017). App classifies less area as high-zone than contractor. Misallocation between 16/17; combined total is fine.

18 | Durų angų paruošimas beapvadinėms durims | 39.2 m | "Durų angų paruošimas beapvadinėms durims" | 17.1 m | UNDER (−56.4%) | Built from pasleptu_duru_staktu_m (vision_call.py:1281-1307): only sums elementai with tipas=="pasleptos_duris" using (2H+W). App found ~17.1m of paslėptų durų vs contractor's 39.2m. Either Vision under-detected pasleptos_duris (most doors tagged "duris" not "pasleptos_duris"), or contractor counts ALL beapvadinės doors. Likely extraction-tagging gap.

19 | Dažymo kampų montavimas | 493.35 m | "Dažymo kampų montavimas" | 501.3 m | MATCH (+1.6%) | kampai_total = _sum("kampu_metrai") (vision_call.py:1234,1248-1249). Per-room kampai = inner_corners(n_walls×H) + opening_reveals + pusiniai(n_partition_walls×H, default ON) + perim (universal_rules.py:911-931). NOTE per task brief: fresh extraction drops this 501→325 because pusiniai depends on flaky wall_adjacency (n_partition_walls). Current 501.3 is a MATCH only because cached adjacency populated n_partition_walls; it is fragile.

19a (split of item 19) | — | — | "Glaistymo kampai vidiniai" | 350.91 m | EXTRA (sub-split, not double-count of total) | kampai_total × 0.7 (vision_call.py:1236). Pure 70/30 heuristic split of the same total. Contractor item 19 is ONE line; app emits 3 lines (vidiniai+išoriniai+montavimas) for it.

19b (split of item 19) | — | — | "Glaistymo kampai išoriniai" | 150.39 m | EXTRA (sub-split) | kampai_total × 0.3 (vision_call.py:1237). 350.91+150.39 = 501.3 = same total as "Dažymo kampų montavimas". So the kampai total IS counted twice in the bill (once as vidiniai+išoriniai, once as montavimas) — see calc_method_issues. Material/labour separation is intended but risks double-billing if priced naively.

20 | Priglaistomų gipsinių šviestuvų apdirbimas | 38 vnt | (none in this skyrius) | — | MISSING-in-app | App emits "Difūzorių apdirbimas" + "Lubinių priglaistomų šviestuvų montavimas" only under SK_EL (Elektros), gated on symbols.sviestuvai/difuzoriai. No glaistymas-skyrius apdirbimas line for priglaistomi šviestuvai. The 38 priglaistomų šviestuvų apdailos (glaistytojo darbas) is absent from this section.

21 | Magnetinės TRACK apšvietimo sistemos apdirbimas | 20.06 m | (none) | — | MISSING-in-app | No TRACK/magnetinės sistemos line anywhere in the app generator. Both the GKP-section montavimas (item 11) and this glaistymas apdirbimas (item 21) are unmodeled.

22 | Priglaistomų gipsinių difūzorių apdirbimas | 21 vnt | (none in this skyrius) | — | MISSING-in-app | App's "Difūzorių apdirbimas (priglaistomas)" lives in SK_EL (vision_call.py:1856-1859), driven by symbols.difuzoriai which is 0 in this extract → not emitted. Glaistytojo difūzorių apdirbimas (21 vnt) missing from glaistymas section.

23 | Nišų iš GKP paslėptam led apšvietimui glaistymas dažymas | 42.3 m | "LED nišų glaistymas" 41.88 + "LED nišų dažymas" 41.88 | 41.88 m (×2 lines) | MATCH (−1.0%) | nisu_total = _sum("nisu_metrai") (vision_call.py:1366,1376-1379). Contractor bundles glaistymas+dažymas into ONE line (42.3m); app splits into 2 lines at same 41.88m each. Kiekis matches; line-count differs.


### Missing in app
Three contractor SECTION-2 lines have NO equivalent in the app's glaistymas/dažymas skyrius:

1. Item 20 — Priglaistomų gipsinių šviestuvų apdirbimas, 38 vnt. The glaistytojo finishing work around 38 flush-mount fixtures. App only has electrical "montavimas" lines (SK_EL), never the glaistymas-trade apdirbimas. Missing because difuzoriai/sviestuvai symbol counts feed SK_EL, not SK_GD, and the glaistymas-side apdirbimas line was never built. This is real billable glaistytojo labour (~38 vnt × per-unit rate).

2. Item 21 — Magnetinės TRACK apšvietimo sistemos apdirbimas, 20.06 m. No TRACK-system concept exists in the generator at all (neither montavimas item 11 nor apdirbimas item 21). Completely unmodeled premium feature.

3. Item 22 — Priglaistomų gipsinių difūzorių apdirbimas, 21 vnt. Same root cause as item 20: difūzorių apdirbimas is only emitted under SK_EL gated on symbols.difuzoriai (=0 here), so nothing appears. The glaistytojo difūzorių finishing (21 vnt) is absent.

These three are systematically missing because the app routes flush-fixture/diffuser/track work to the Elektros skyrius (driven by drawing-symbol counts that came back empty), and never mirrors the glaistytojo apdirbimas side into the Sienų lubų glaistymas dažymas section the way the contractor itemizes it. Combined they are a meaningful labour gap (59 vnt + 20m of apdirbimas).


### Extra in app
App lines in skyrius "Sienų lubų glaistymas dažymas" with no direct SECTION-2 contractor equivalent:

LEGITIMATE (map to other contractor sections, correctly placed here by LT convention):
- "Angokraščių glaistymas-dažymas" 138.42 m — matches contractor SECTION 1 item 13 "Angokraščių sandarinimas" 89.39m... actually NO: app 138.42 vs contractor 89.39 = +54.8% OVER. This is the glaistymas-side of angokraščiai; the GKP-side twin ("Angokraščių apdirbimas GKP" 138.42, SK_GKP) maps to item 14 (89.39). BOTH app angokrasčiai lines are +54.8% over contractor's 89.39 because vision_call.py:1257-1286 uses (2H+W) per opening with the _opening_adds_reveal gate and likely counts more openings / larger reveal contour than the contractor. Flag as OVER, not noise.
- "Grindjuosčių sumontavimas" 107.67 m + "Grindjuosčių dažymas" 107.67 m — grindjuostės belong to a flooring/apdaila section; contractor SECTION 2 has none (their grindjuostės appear in SECTION 3 item 35 "Grindjuosčių supjovimas ir suklijavimas" 22.72m, a different plytelių-grindjuostė concept). App's 107.67m painted skirting is a legit interior item but has no SECTION-2 counterpart; not noise.
- "Lubų karnizo sumontavimas" 115.71 + "Lubų karnizo dažymas" 115.71 — ceiling cornice. NO contractor equivalent anywhere in the samata. Either contractor didn't quote cornice (design has none) or app is inventing it from karnizas_total=_sum("lubu_karnizo_m"). Potential FALSE-POSITIVE / over-scope — flag for verification.

DOUBLE-COUNT RISK (within section):
- "Glaistymo kampai vidiniai" 350.91 + "Glaistymo kampai išoriniai" 150.39 sum to 501.3 = exactly the "Dažymo kampų montavimas" 501.3. The same kampai metrai are represented in two parallel line sets. Intended as material (kampuotės) vs labour split, but if a pricer multiplies all three by a €/m rate the kampai are billed ~2×. Contractor has ONE line (item 19). This is the biggest noise/double-count risk in the section.


### Calculation-method issues
Per app line, method + soundness:

1. Rotband (vision_call.py:1135-1158): walls_paint × rotband_share(default 0.50). UNSOUND — share is a fixed % of a quantity (walls_paint) that has grown 59% since the 0.50 was calibrated to 138.69 (then walls_paint=277.33, now ≈441.48). A fixed fraction of a moving base cannot stay calibrated. Should be an absolute share of block/concrete-wall area, or re-derived (current correct share ≈0.314).

2. Combined dažymas iki/virš 3m (vision_call.py:983-1071, 1012-1017): total dazymo = Σ walls_paintable + Σ ceiling_paintable = 607.11, MATCHES contractor 584.81 (+3.8%) — SOUND on total. Height split is BINARY per room (whole room → high if lubu_aukstis_m>3.0). UNSOUND allocation: a room with a partial 3.4m coffer dumps ALL its walls+ceiling into virš-3m (or none). universal_rules.py:819-828 has high_ceiling_area_m2 partial support for GKP, but the PAINT split (vision_call.py:1012) ignores it and uses room-level lubu_aukstis_m only. Result: −28% in virš-3m, +22% in iki-3m. The split logic should mirror the partial-area approach used for GKP.

3. walls_paint vs lubos_paint sanity: implied lubos_paint=165.63 ≈ the known fixture ceiling truth 165.61 — ceiling side is excellent. walls_paint=441.48 is the over-rich number driving both Rotband over-quote and the combined total's +3.8%.

4. Kampai (universal_rules.py:911-931): kampai = inner_corners(n_walls×H) + opening_reveals + pusiniai(n_partition_walls×H) + perim. The "+ perim" added on top of inner_corners (4×H per rectangle) is a legacy belt-and-suspenders term (comment admits "can be removed once adjacency wiring lands"). pusiniai default-ON depends on n_partition_walls from a flaky wall_adjacency pass — per the task brief this collapses 501→325 on fresh extraction. UNSOUND/FRAGILE: the MATCH (+1.6%) is luck of cached adjacency. Then the total is SPLIT 70/30 into vidiniai/išoriniai (fixed ratio, vision_call.py:1236-1237) AND re-emitted whole as "montavimas" — a fixed area split into 3 lines, with the full total appearing twice (double-count risk).

5. Angokraščių glaistymas-dažymas (vision_call.py:1257-1293): Σ over elementai of (2H+W)×kiekis gated by _opening_adds_reveal. Note universal_rules.py:958-976 computes a DIFFERENT angokrasciu field (angokrasciu_gkp_m) that the comment claims hits 89.51m vs truth 89.39 (+0.13%) — but vision_call.py does NOT use that per-room field; it recomputes inline and gets 138.42 (+54.8%). UNSOUND DUPLICATION: two angokraščiai formulas in the codebase disagree by 55%, and the bill uses the worse one. The accurate per-room angokrasciu_gkp_m is computed and then ignored.

6. LED nišų (vision_call.py:1376-1379): nisu_total split into glaistymas+dažymas, two lines same m. SOUND quantity (−1.0%), just line-count style difference vs contractor's bundled item 23.

7. Durų beapvadinėms (vision_call.py:1281-1307): only pasleptos_duris-tagged elementai. UNSOUND if Vision tags most doors as plain "duris" — undercount −56%. Unit (m) is correct.

Unit checks: all SECTION-2 app lines use correct units (m2 for paint/Rotband, m for kampai/angokraščiai/nišos/durys). No vnt/m²/m mismatches in this section. The unit-correct but VALUE issues are Rotband (+59%), height-split (±25%), angokraščiai (+55%), beapvadinės durys (−56%).


### Section to-fix
HIGH priority:
1. Rotband 50% drift (item 15, +59%). Re-derive rotband_share against the CURRENT walls_paint base, or convert to an absolute block/concrete-wall area input. For this fixture the correct share is ≈0.314, not 0.50. The hardcoded 0.50 with a stale calibration comment is actively over-quoting ~€820 on Rotband alone for this project. vision_call.py:1145.

2. Angokraščiai double-formula divergence (+54.8%). vision_call.py:1257-1286 recomputes reveals inline and gets 138.42 vs the calibrated universal_rules.py:958-976 angokrasciu_gkp_m which the comment says hits 89.39 to the dot. Switch vision_call.py to consume the per-room angokrasciu_gkp_m field (both the SK_GD glaistymas line AND the SK_GKP apdirbimas twin, currently both 138.42). Expected: 138.42→~89.5m, killing a +55% over-quote on TWO lines.

3. Kampai fragility (item 19). The +1.6% MATCH depends on cached wall_adjacency (n_partition_walls); fresh extraction drops to 325 (−34%). Make pusiniai robust (don't silently zero when adjacency bails) and resolve the "+ perim" legacy double-add. Also collapse the vidiniai+išoriniai+montavimas triple so the same 501m isn't billable twice (separate material m from labour m explicitly, or merge to one line like contractor item 19).

MEDIUM priority:
4. Height-zone split (items 16/17, +22%/−28%). Make the paint iki/virš-3m split use partial high-ceiling area (high_ceiling_area_m2, already plumbed for GKP at universal_rules.py:819-828) instead of the binary room-level lubu_aukstis_m>3.0 test at vision_call.py:1012-1017. Combined total is correct, so this is pure reallocation — fixes both lines at once.

5. Beapvadinės durys undercount (item 18, −56%). Audit Vision tagging: if most paslėptos durys come back as plain "duris", the pasleptu_duru_staktu_m sum (vision_call.py:1281) misses them. Either improve detection or let the user flag which doors are beapvadinės.

6. Missing apdirbimas lines (items 20, 21, 22). Add glaistytojo apdirbimas lines for priglaistomi šviestuvai (38 vnt), difūzoriai (21 vnt) and magnetinė TRACK sistema (20.06 m) into SK_GD — currently only the montavimas side exists under SK_EL, and only when drawing-symbols are non-empty (they're 0 here). These are ~59 vnt + 20m of unbilled glaistytojo labour.

LOW priority:
7. Verify "Lubų karnizo" 115.71 (×2 lines) is real — contractor quotes NO ceiling cornice anywhere in the samata. If the design has no karnizas, the app is inventing ~€700 of montavimas+dažymas from karnizas_total. Gate karnizas on actual detection, not a default.


## SECTION 3 — Plytelių klijavimas (contractor items 24–36) vs app skyrius "Plytelių klijavimas + Hidroizoliacija + Grindys". App output = /tmp/berzas_app_lines.json (== ground_truth/berzas/ai_extract.json). Code: backend/extractor/vision_call.py _build_pozicijos_from_rooms L1443–1726 (tiles/hidro/grindys) + universal_rules.py calc_room_quantities L532–1034. Contractor truth: ground_truth/berzas/contractor_samata_parsed.json + truth.json gt_totals.


### Per-line
nr | samata item | samata kiekis vnt | app match | app kiekis | STATUS | note

24 | Dekoro plytelių klijavimas miegamojo vonioje ant sienų 120*60 | 28.8 m² | "Vonios sienų plytelių klijavimas" (san 107+111 only) | 42.04 m² | NOT-1:1 (structural mismatch) | Contractor splits WALL tile by tile-format/zone (item 24 = one 120×60 decor band). App splits by ROOM-class (Vonios vs Kitų), not by format. App "Vonios sienų" 42.04 = san107(20.48)+san111(21.56). Items 24+25(wall part)+27+28 are the contractor's wall-tile universe; not comparable line-for-line. See aggregate row below.

25 | Plytelių klijavimas ant sienų IR grindų 120*120 | 55.62 m² | split across "Vonios/Kitų sienų" + "Vonios/Kitų grindų" klijavimas | (part of 67.12 sienos + 31.89 grindys) | NOT-1:1 | Item 25 mixes WALL+FLOOR in ONE line (55.62). App never mixes wall+floor in a line. No direct match; reconcile only at aggregate.

26 | Plytelių klijavimas ant grindų 90*90 | 16.99 m² | "Vonios grindų"+"Kitų grindų plytelių klijavimas" | 31.89 m² (app floor-tile total) | see aggregate | Floor-tile format split (90×90) not represented in app; app floor tile = 31.89 vs contractor floor truth 39.88 (truth.json plyteles_grindys_total_m2). App UNDER -20% (missing Garažas 10.10 floor).

27 | Didžiaformačių plytelių klijavimas | 4.48 m² | "Didžiaformačių plytelių klijavimas (>600×600)" (didzformat_share path) | NOT EMITTED (0) | MISSING-in-app | Code L1502 needs _plyteliu_specs format_label=="didžiaformatė"; ai_extract has none → didzformat_count=0 → line suppressed. Contractor has 4.48+8.7=13.18 m² large-format. App emits 0.

28 | Didžiaformačių plytelių klijavimas (nišos angokraščiai) | 8.7 m² | (same large-format path) | NOT EMITTED (0) | MISSING-in-app | Niche-reveal large-format tile. App has no niche-reveal tile concept at all. 0.

— AGGREGATE WALL TILE (items 24+25wall+27+28) | contractor truth plyteles_sienos = 61.53 m² (2 documented bathrooms 107+111 only; truth flags incomplete) | app "Vonios sienų"+"Kitų sienų" klijavimas | 67.12 m² | OVER (+9% vs documented 61.53, but truth is incomplete) | Per-room: san107 app=20.48 vs truth 32.73 (UNDER -37%); san111 app=21.56 vs truth 28.80 (UNDER -25%). App also adds Skalbykla 20.58 + Darbo kambarys 4.50 wall tile the contractor did not itemise. Net cancels to +9% by luck. Method divergence = perim×tile_height (app) vs per-wall measured (contractor).

— AGGREGATE FLOOR TILE (items 25floor+26) | contractor truth plyteles_grindys = 39.88 m² | app "Vonios grindų"+"Kitų grindų" klijavimas | 31.89 m² | UNDER -20% | Per-room: Tambūras 8.54→app 11.01 (note: ai_extract uses 11.01 not 8.54 override here), san107 6.59, san111 7.45, Skalbykla 6.84. Missing Garažas floor tile 10.10. Eval --use-gt-inputs scored -0.90% but that used gt overrides; raw extract here = -20% (matches replay -20.04% in audit report L146).

29 | Lentynėlių iš plytelių įrengimas dušo kabinoje | 5 vnt | "Lentynėlių iš plytelių įrengimas dušo kabinoje" | 4 vnt | UNDER -20% | Code L1632: n_full_vonia(paskirtis∈vonia/san)=2 × per_vonia default 2 = 4. Truth=5 (=2.5/vonia). Off by 1; within calibration band, flagged confidence=low.

30 | Nuolydžio formavimas dušo kabinoje | 2 vnt | "Nuolydžio formavimas dušo zonoje" | 2 vnt | MATCH | Code L1620: n_showers(paskirtis∈vonia/san)=2. Exact.

31 | Hidroizoliacijos įrengimas | 2 vnt | "Hidroizoliacijos įrengimas (...)" (skyrius=Hidroizoliacija) | 2 vnt | MATCH | Code L1672: n_wet_zones(WET={vonia,wc,san})=2 (san107+san111). Exact. NOTE Skalbykla has hidro_m2=9.99 in extract but paskirtis=skalbykla ∉ WET → not counted as a zone; contractor also =2 so OK.

32 | Skylių gręžimas plytelėse | 56 vnt | "Skylių gręžimas plytelėse (vamzdžiams, kaiščiams)" | 4 vnt | UNDER -93% (MAJOR) | App used FALLBACK path L1607 (n_holes=1 langas × 4 = 4) NOT the symbol path L1598. detected_symbols_summary IS present (klozetai2/praustuves3/vonios1/wc_remai2) which would give 2·4+3·6+1·8+2·3 = 40 — still under 56 but far closer. The symbol path silently didn't fire → bug. Either way grossly under truth 56.

33 | Latakų įrengimas | 2 vnt | "Linijinio latako montavimas (dušo zonoje)" (skyrius=Santechnikos darbai) | 2 vnt | MATCH (different skyrius) | App emits this under Santechnikos, not Plytelių. Code L1767: n_full_bathroom=2. Quantity matches; section placement differs from contractor (who bundles latakai into tile section).

34 | Kampų silikonavimas | 50.14 m | "Silikonavimas tarp plytelių zonos ir sanit. įrangos" (18.4) + "Plytelių vidinių kampų silikonavimas" (13.8) | 32.2 m combined | UNDER -36% | Code L1572-73: silikon_san=wet_perim×0.8, silikon_kampai=wet_perim×0.6 (wet_perim=23.0 → 18.4+13.8=32.2). Truth=50.14. Per audit L113-115 truth per-room 23.64+31.74=55.38 for 2 baths; app under because wet_perim excludes Skalbykla and uses 1.4× perim vs contractor's higher per-wall corner count.

35 | Grindjuosčių supjovimas ir suklijavimas | 22.72 m | (NONE in Plytelių skyrius) | NOT EMITTED | MISSING-in-app | This is TILE skirting (plytelinės grindjuostės cut+glued), a tile-section line. App's grindjuostės live only in "Sienų lubų glaistymas dažymas" (painted MDF/wood skirting) and are NOT emitted for tile floors (universal_rules L984: grindjuostes=0 when tile_floor=True). So tile skirting 22.72 m is entirely missing.

36 | Plytelių supjovimas 45° kampu, apdirbimas epoksidu | 9.7 m | "Plytelių 45° pjovimas (vidiniai kampai)" 11.2 m; epoxy variant gated off | 11.2 m | MATCH (±5% borderline, +15%) | Code L1545: pjovimas_45=max(wet_perim×0.4, 2·n_wet·tile_h)=max(9.2, 2·2·2.8=11.2)=11.2. Truth 9.7 → +15% OVER (just outside ±5%). Epoxy sub-line (L1556) only fires when paint_class==1; here suppressed, but contractor's "apdirbimas epoksidu" IS the same single line so OK.


### Missing in app
1) Item 27+28 Didžiaformačių plytelių klijavimas (4.48 + 8.7 = 13.18 m²): app emits ZERO. The large-format path (vision_call.py L1506) requires parsed["_plyteliu_specs"] entries with format_label "didžiaformatė"; the berzas extract has none, so didzformat_count=0 and BOTH didžiaformatė lines are suppressed. Large-format tile is a real cost premium (2-3× labor) — this is a material miss, ~13 m² of premium tilework invisible.

2) Item 28 specifically — large-format tile on NICHE REVEALS (angokraščiai). App has no concept of tiled niche/opening reveals at all. 8.7 m² missing.

3) Item 35 Grindjuosčių supjovimas ir suklijavimas (22.72 m) — TILE skirting. App only emits grindjuostės in the paint section and explicitly zeroes them for tile-floored rooms (universal_rules.py L984-988: grindjuostes_base=0 when tile_floor). No tile-skirting line exists anywhere → 22.72 m fully missing.

4) Floor-tile shortfall: app floor tile 31.89 vs contractor 39.88 — the missing ~8-10 m² is the Garažas tiled floor (truth notes "10.10"). Garažas paskirtis default has tile_floor=False, so its floor tile is dropped (universal_rules L855-858). This is a per-room paskirtis-default miss, not a formula error.

5) Per-wall wall-tile precision: san107 app 20.48 vs truth 32.73 (-37%), san111 app 21.56 vs truth 28.80 (-25%). App's perim×tile_height under-reads individual bathrooms; only nets to +9% at the aggregate because app over-adds Skalbykla/Darbo-kambarys wall tile the contractor didn't itemise. Two errors cancelling, not accuracy.


### Extra in app
App lines in this skyrius with NO contractor equivalent:

1) "Vonios sienų plytelės" 45.4, "Kitų sienų plytelės" 27.09, "Vonios grindų plytelės" 15.16, "Kitų grindų plytelės" 19.28 — these are MATERIAL lines (klijavimas_m² × 1.08 waste, code _add_tile_lines L1467). LEGITIMATE as a bill-of-materials but they are NOT separate billable work lines; contractor folds material into the klijavimas rate. If exported as priced rows they DOUBLE-COUNT area against the klijavimas line. Display/BOM only — must not be summed into work total.

2) "Vonios/Kitų sienų/grindų plytelių fugavimas" (42.04/25.08/14.04/17.85) — grouting labor split out as 4 separate lines. Contractor has NO standalone fugavimas line (bundled into klijavimas rate). LEGITIMATE granularity but risks over-itemisation vs this contractor's convention; harmless if priced consistently.

3) "Plytelių vidinių kampų silikonavimas" (13.8) as a SECOND silikonas line — contractor has ONE "Kampų silikonavimas" (50.14). App's two silikonas lines (18.4 + 13.8) are a reasonable internal split BUT together (32.2) still under-shoot the single contractor line. Not noise, just under-summed.

4) Hidroizoliacija material sub-field membrana_kg (=hidro_m2×3.0=146.55 kg) — sound BOM, not a double-count of the vnt line.

No spurious phantom work lines detected; the EXTRA lines are all material/grouting granularity, defensible but convention-dependent.


### Calculation-method issues
TILE AREAS (universal_rules.py calc_room_quantities):
- plyteles_sienos = tile_walls_area; in legacy path L749 = perim × tile_height (whole-room perimeter × a single tile band height). SOUND only when all walls tiled to same height; for real bathrooms with per-wall variation it diverges ±15-37% (audit L112-114). tile_height from Vision plyteles_sienos_aukstis_m (L608) else room-type default.
- plyteles_grindys = full room plotas when tile_floor True (L855-858), else 0 or per-room override. All-or-nothing → misses partially-tiled and drops rooms whose paskirtis default = no tile (Garažas).

TILE LINE ASSEMBLY (vision_call.py _build_pozicijos_from_rooms):
- _add_tile_lines (L1455) emits 3 lines/zone: klijavimas (kiekis=area), plytelės (area×1.08 — MATERIAL, must not double-count), fugavimas (area). Zone split by room-class via _sum_filtered with WET={vonia,wc,san} (L1448-1453). UNIT m² consistent. SOUND, but "plytelės" line shares the same m² and will double-count if summed as work.
- Didžiaformatės (L1506) gated on _plyteliu_specs format_label — fragile, produced 0 here.
- 45° pjovimas (L1545) max(wet_perim×0.4, 2·n_wet·tile_h) — heuristic; +15% here.
- Silikonas (L1572) wet_perim×0.8 + wet_perim×0.6 — wet_perim only sums WET rooms' perimetras (excludes Skalbykla); under-reads.
- Skylių gręžimas: symbol path (L1598) klozetai·4+praustuves·6+vonios·8+wc_remai·3 is SOUND and data exists (=40), but output shows 4 → the FALLBACK (L1607, n_wet-room openings×4) fired instead. UNIT vnt OK; the bug is path selection / symbols not reaching this function at generation time.
- Lentynėliai (L1632) n_full_vonia×2 default — vnt OK, value -1 vs truth.
- Nuolydis (L1620) n_showers — vnt, exact.

HIDRO (vision_call.py L1671): line UNIT = vnt (n_wet_zones=2). _calc_hidroizoliacija_m2 (L642) computes m² (plotas + perim×0.30 + shower_zone×H) but that m² is only stored as _detail_m2/medziagos, the billed kiekis is vnt count. SOUND per contractor convention (item 31 also vnt=2). No double-count.

GRINDYS (vision_call.py L1694):
- isliginamasis = full floor of every non-concrete room (universal_rules L996) → 154.97 m² covers ALL floors incl. tiled ones. SOUND (levelling under both tile and laminate).
- pvc_grindys = plotas only when floor_type=="parquet" (L993) → 123.08 (laminate rooms only, excludes tiled+concrete). Pamušalas + klojimas both = 123.08, SOUND (underlay matches laminate area, not over-counted).
- Slenksniai = max(0, n_rooms-1) = 10 (L1719). CRUDE: assumes one threshold per room boundary; contractor has no slenksniai line in section 3 at all (these are flooring transitions, contractor likely bundled elsewhere). EXTRA vs contractor.


### Section to-fix
HIGH:
1. Skylių gręžimas 4 vs 56 (-93%): debug why the symbol path (vision_call.py L1593-1605) didn't fire when detected_symbols_summary clearly has klozetai/praustuves/etc. The fallback (4) is firing instead of symbol-driven (40). Wire symbols through and recalibrate per-fixture multipliers up toward 56 (contractor counts every pipe+anchor hole; current 4/6/8/3 weights under-count even at full symbol data).
2. Didžiaformatės plytelės = 0 vs 13.18 m² (items 27+28): the large-format path depends on _plyteliu_specs which is empty here. Add a fallback so detected large tiles (from tile schedule or Vision format read) still emit, and add a NICHE-REVEAL tile concept for item 28.
3. Tile skirting (item 35, 22.72 m) entirely missing: add a "Grindjuosčių (plytelinių) supjovimas+klijavimas" line for tile-floored rooms — currently universal_rules L984 zeroes grindjuostės on tile floors, so no skirting at all is emitted for bathrooms.

MED:
4. Floor tile -20% (31.89 vs 39.88): fix Garažas (and similar) dropped tile floor — paskirtis default tile_floor=False drops ~10 m². Either detect tiled garage from Vision or widen the per-room override surfacing.
5. Silikonas -36% (32.2 vs 50.14): wet_perim excludes Skalbykla and under-weights corners; raise multiplier and include all wet/tiled rooms; reconcile to the single contractor "Kampų silikonavimas" line.
6. Per-bathroom wall-tile divergence (san107 -37%, san111 -25%): only nets to +9% by cancellation against extra Skalbykla/Darbo-kambarys tile. Move to per-wall tile area (Phase-4 elevation extractor) so individual room totals are right, not just the sum.

LOW:
7. Lentynėliai 4 vs 5: bump default toward 2.5/vonia or read from drawing.
8. 45° pjovimas +15% (11.2 vs 9.7): the max(...) heuristic slightly over-shoots; tune the 2·n_wet·tile_h term.
9. Latakai placement: contractor itemises latakai in the tile section; app puts them in Santechnikos. Cosmetic section-mapping mismatch (quantity correct).
10. Slenksniai (10 vnt): app-only line with no contractor equivalent in section 3; verify it isn't double-billing flooring transitions counted elsewhere.
11. Material "plytelės" (×1.08) and "fugavimas" lines: mark clearly as BOM/sub-lines so an exported priced total never sums the ×1.08 material m² as additional work area (double-count risk).


## SECTION 4 (Santechnikos darbai, contractor lines 37–52) + SECTION 5 (Statybvietės išlaidos, line 53). App skyrius = "Santechnikos darbai" + "Pridėtiniai elementai". Generated by _build_pozicijos_from_rooms in backend/extractor/vision_call.py (santechnika block lines 1728–1795; pridėtiniai block 1929–1966).


### Per-line
SECTION 4 — SANTECHNIKA (contractor → app match):

37 | Lauko laistymo čiaupo montavimas | 1 vnt | NO app line | — | MISSING-in-app | App has no exterior-tap concept. Not derivable from interior room paskirtis.

38 | Tėvų vonios maišytuvo POTINKINĖ dalis (štrobavimas) | 1 vnt | "Dušo maišytuvo sistemos montavimas" kiekis=2 (vision_call.py:1762-1764) | part of 2 | UNDER/STRUCTURE-MISMATCH | Contractor splits bath+shower mixers into potinkinė (rough-in/štrobavimas) + virštinkinė (trim) as SEPARATE billable lines (37→44 = 8 distinct mixer lines). App emits ONE bundled "Dušo maišytuvo sistemos montavimas"=2. See calc-method note.

39 | Potinkinio vonios maišytuvo VIRŠTINKINĖS dalies montavimas | 1 vnt | folded into app "Dušo maišytuvo sistemos montavimas"=2 | — | UNDER | Same bundling issue as 38.

40 | Potinkinio PRAUSTUVO maišytuvo POTINKINĖS dalies | 5 vnt | app "Praustuvės maišytuvo montavimas" kiekis=2 (vision_call.py:1755-1756) | 2 | UNDER (−60%) | Contractor=5 basin mixers (potinkinė) + 5 (virštinkinė)=10 basin-mixer ops. App=2 (one per wet room = n_wet_with_klozetas). Massive undercount: contractor has 5 basins across the house, app only counts 2 (= number of bathrooms).

41 | Potinkinio praustuvo maišytuvo VIRŠTINKINĖS dalies | 5 vnt | folded into app "Praustuvės maišytuvo montavimas"=2 | — | UNDER (−60% before counting the 2× split) | Same as 40.

42 | Potinkinio DUŠO maišytuvo POTINKINĖS dalies | 2 vnt | part of app "Dušo maišytuvo sistemos montavimas"=2 | 2 | MATCH on count, but bundled | App count 2 coincidentally equals contractor's 2 potinkinė dušo. But app's single line also has to represent line 43 (virštinkinė ×2) AND lines 38/39 (bath mixer) — so net the bundle is UNDER.

43 | Potinkinio dušo maišytuvo VIRŠTINKINĖS dalies | 2 vnt | folded into app "Dušo maišytuvo sistemos montavimas"=2 | — | UNDER | Same bundle.

44 | WC rėmo montavimas | 2 vnt | app "WC rėmo montavimas" kiekis=2 (vision_call.py:1749-1752) | 2 | MATCH | n_wet_with_klozetas = n_vonia+n_wc+n_san = 2. Exact.

45 | Bide dušiukų POTINKINĖS dalies | 3 vnt | NO app line | — | MISSING-in-app | App has no bidė/higienic-shower concept at all.

46 | Bide dušiukų VIRŠTINKINĖS dalies | 3 vnt | NO app line | — | MISSING-in-app | Same — bidė entirely absent.

47 | Skalbimo mašinos sifono montavimas | 1 vnt | app "Skalbimo mašinos sifono įrengimas" kiekis=1 (vision_call.py:1780-1784) | 1 | MATCH | n_skalbimo_sifonas = max(n_skalbykla, ...) = 1.

48 | Klozeto montavimas | 2 vnt | app "Klozeto montavimas" kiekis=2 (vision_call.py:1753-1754) | 2 | MATCH | Driven by n_wet_with_klozetas=2.

49 | Gyvatuko montavimas, teno pajungimas | 2 vnt | app "Gyvatuko montavimas, teno pajungimas" kiekis=2 (vision_call.py:1765-1766) | 2 | MATCH | n_full_bathroom = n_vonia+n_san = 2.

50 | Skalbimo mašinos montavimas | 1 vnt | app "Skalbimo mašinos montavimas" kiekis=1 (vision_call.py:1788-1791) | 1 | MATCH | Added 2026-05-27 specifically for this fixture; uses n_skalbimo_sifonas=1.

51 | Džiovyklės montavimas | 1 vnt | NO app line | — | MISSING-in-app | App never emits a dryer line. Could be derived from n_skalbykla but isn't.

52 | Medžiagos montavimui | 1 vnt | app "Santechnikos taškų koregavimas" kiekis=1 kompl (vision_call.py:1793-1795) | 1 | LOOSE-MATCH (1 vs 1, unit differs vnt vs kompl) | Both are catch-all baseline lines. Semantically close enough (a 1-unit materials/adjustment placeholder). Treat as MATCH.

SECTION 5 — STATYBVIETĖ:

53 | Šiukšlių išvežimas | 12 m3 | app "Šiukšlių išvežimas (statybinės atliekos)" kiekis=12.4 m3 (vision_call.py:1954-1959) | 12.4 | MATCH (+3.3%, within ±5%) | siuksliu_m3 = bendras_plotas × 0.075. Calibrated to this exact fixture (165.61 m² → 12.4). Unit m3 matches.


### Missing in app
Contractor lines with NO app equivalent (8 of 17 contractor lines in this section are missing or materially undercounted):

1. Line 37 Lauko laistymo čiaupas (1 vnt) — exterior garden tap. App has zero concept; not derivable from interior paskirtis. Low €, but a real missed line.

2. Lines 38/39 Vonios (bath) maišytuvas potinkinė+virštinkinė (1+1) — bundled away into the generic "Dušo maišytuvo sistemos montavimas"=2. App cannot distinguish a tub filler from a shower mixer.

3. Lines 40/41 Praustuvo (basin) maišytuvas potinkinė+virštinkinė (5+5=10 ops) — THE BIGGEST GAP. App emits "Praustuvės maišytuvo montavimas"=2 (one per wet room). Contractor has 5 basins (basins also live in bedrooms/dressing areas, not just the 2 full baths). App undercounts basin mixers by ~80% (2 vs 10 billable ops, or 2 vs 5 fixtures).

4. Lines 45/46 Bidė dušiukai potinkinė+virštinkinė (3+3=6 ops) — completely absent. No bidet/hygienic-shower line exists anywhere in the generator.

5. Line 51 Džiovyklės montavimas (1 vnt) — dryer hookup. Absent; could be tied to n_skalbykla but isn't.

Net: the contractor itemizes santechnika as ~30 discrete fixture operations (potinkinė/virštinkinė split, per-fixture). The app produces ~10 lines at fixture-count granularity. Even ignoring the potinkinė/virštinkinė doubling, the app under-represents the real fixture count (esp. basins: 2 vs 5).


### Extra in app
App lines in this skyrius with NO contractor equivalent:

SANTECHNIKA:
1. "Linijinio latako montavimas (dušo zonoje)" kiekis=2 (vision_call.py:1767-1768) — EXTRA but LEGIT. Contractor line 33 "Latakų įrengimas"=2 exists but is filed under SECTION 3 Plytelių (tile work), not santechnika. So it IS in the contractor samata, just in a different skyrius. NOT a double-count of THIS section, but cross-check: the app may ALSO emit a tile-section latakas — verify no duplication across skyriai. Count (2) matches contractor's 2.

2. "Santechnikos taškų koregavikas" / "Santechnikos taškų koregavimas" kiekis=1 kompl (baseline) — EXTRA baseline placeholder. Maps loosely to contractor line 52 "Medžiagos montavimui". Acceptable, but it's a hardcoded "baseline" line (saltinis=baseline) with no drawing evidence — flag as soft.

PRIDĖTINIAI ELEMENTAI:
3. "Pastolių nuoma (aukštesnių nei 3m)" kiekis=3 d.d (vision_call.py:1941-1946) — EXTRA, not in contractor section 4/5. Contractor has NO scaffolding line at all (he prices high-ceiling work into the m² rate of items 17/2/etc). Potential DOUBLE-CHARGE risk: the app ALSO emits "Sienų/lubų ...(virš 3m aukščio)" m² premium lines AND GKP virš-3m lines. Pastolių as a separate d.d line on top of those premium m² lines may over-quote. LEGIT as a line type but watch for triple-counting the height premium.

4. "Statybvietės sutvarkymas po darbų" kiekis=1 kompl — EXTRA, no contractor equivalent. Reasonable LT-standard add-on (site cleanup). Noise-ish: a 1-kompl placeholder, no €-basis shown.

5. "Apsauginės dangos / juostos darbų metu" kiekis=165.64 m2 — EXTRA, no contractor equivalent. = bendras_plotas (floor area). Legit concept (PE film + masking tape) but the m² basis (= full floor area) is an assumption, not measured.


### Calculation-method issues
HOW each app line is computed and soundness:

SANTECHNIKA — all driven by per-room paskirtis classification (normalize_paskirtis, universal_rules.py:410-447), counted at vision_call.py:1734-1738:
- n_vonia/n_wc/n_san/n_virtuve/n_skalbykla = count of rooms by paskirtis.
- n_wet_with_klozetas = n_vonia+n_wc+n_san (line 1741) → drives WC rėmas, Klozetas, Praustuvės maišytuvas, Praustuvė (all = 2).
- n_full_bathroom = n_vonia+n_san (line 1743) → drives Dušo maišytuvas, Gyvatukas, Linijinis latakas (all = 2).
- n_skalbimo_sifonas = max(n_skalbykla, 1 if full bathroom & no skalbykla) (line 1779) → Skalbimo sifonas + Skalbimo montavimas (=1).
- "Santechnikos taškų koregavimas" = hardcoded 1 kompl (line 1793).

SOUNDNESS PROBLEMS:
(a) ONE-FIXTURE-PER-WET-ROOM assumption is the core flaw. The app assumes exactly 1 toilet + 1 basin + 1 mixer per wet room. Real high-end house (this fixture) has 5 basin mixers but only 2 toilets → basins decoupled from toilets. App ties praustuvė count to klozetas count (both = n_wet_with_klozetas=2), so it structurally cannot reach 5 basins. This is a hard undercount, not a tuning issue.
(b) NO potinkinė/virštinkinė split. Contractor bills rough-in and trim as two visits/lines per mixer; app emits one. Even with correct fixture counts the app produces ~half the contractor's billable line count. This is a billing-granularity choice — defensible as "1 mixer = 1 job" but it diverges from how this contractor prices.
(c) UNIT consistency is fine (all vnt; kompl for the catch-all). No m²/m/vnt mismatches in santechnika.
(d) No double-counting WITHIN santechnika — each fixture line is independent. Linijinis latakas=2 is the only potential cross-skyrius dup (contractor files latakas under tiles, line 33).

PRIDĖTINIAI:
- Pastolių: high_ceiling_dazymo / 50, min 1 (lines 1934-1940). Fixture → 3 d.d. METHOD is arbitrary (50 m²/d.d divisor, no source). RISK: stacks on top of virš-3m m² premium lines → possible double-charging the height premium.
- Šiukšlių: bendras_plotas × 0.075, min 1.0 (line 1954). SOUND and calibrated to this exact fixture (12.4 vs truth 12 = +3.3%). But 0.075 is fit-to-one-PDF — overfit risk on other projects.
- Statybvietės sutvarkymas: hardcoded 1 kompl.
- Apsauginės dangos: = bendras_plotas m² (line 1963). Assumption that protective film area = full floor area. Reasonable but unmeasured; no contractor line to validate against.


### Section to-fix
PRIORITIZED FIX LIST:

HIGH:
1. Decouple basin (praustuvė) count from toilet (klozetas) count. App ties both to n_wet_with_klozetas=2; contractor has 5 basins vs 2 toilets. Add a separate basin/mixer count — ideally from detected_symbols_summary (praustuves) which is ALREADY read for skylių gręžimas (vision_call.py:1595), but is NOT used to drive the praustuvė santechnika line. Wire sym.get("praustuves") into "Praustuvės maišytuvo montavimas"/"Praustuvės montavimas" counts. This alone moves 2→5 and closes the single biggest gap.

2. Add bidė / higieninis dušiukas line(s). Contractor 45/46 = 3+3. Completely missing. At minimum emit "Bidė dušiuko montavimas" gated on a symbol or per-full-bathroom default (e.g. 1 per vonia → 2, still short of 3 but non-zero). Currently €0 quoted for a real 6-operation item.

MEDIUM:
3. Split mixers into potinkinė (rough-in/štrobavimas) + virštinkinė (trim) lines to match this contractor's billing granularity. Contractor lines 38-43 are 6 lines; app collapses to "Dušo maišytuvo sistemos montavimas"=2. Even a 2-line split (potinkinė ×N + virštinkinė ×N) per mixer type would roughly double the captured labor and align with the samata structure.

4. Verify Pastolių (Pridėtiniai) does not triple-count the >3m height premium. App emits: virš-3m glaistymas/dažymas m² line + GKP virš-3m m² line + Pastolių 3 d.d. Contractor has NONE of these as separate lines (prices height into base rate). Decide one mechanism (premium m² OR scaffolding d.d), not both, or document that they're complementary.

LOW:
5. Add "Lauko laistymo čiaupas" (line 37) and "Džiovyklės montavimas" (line 51) — tie dryer to n_skalbykla (=1). Small € but both are deterministically derivable (dryer from skalbykla room; tap could be a 0/manual default).
6. Re-validate the šiukšlių 0.075 m³/m² ratio and the 50 m²/d.d pastolių divisor against a second contractor PDF — both are currently fit to this single fixture and at overfit risk.
7. Make "Santechnikos taškų koregavimas" (baseline 1 kompl) and "Statybvietės sutvarkymas" (1 kompl) clearly labelled as non-measured baseline placeholders in the UI (they have saltinis=baseline / no drawing evidence).


---
# PRIORITIZED TO-FIX (master)
PRIORITIZED TO-FIX NOTES (running list, high→low). Each: WRONG app line/value | code location | concrete fix.

=== HIGH ===

H1. Angokraščiai double-formula divergence (+54.8% on TWO lines). WRONG: "Angokraščių apdirbimas GKP (struktūra)" = 138.42 m (SK_GKP) and "Angokraščių glaistymas-dažymas" = 138.42 m (SK_GD); contractor lines 14 & 13 = 89.39 m. CODE: vision_call.py:1257-1286 recomputes Σ(2H+W) inline over langas/duris/pasleptos_duris with _opening_adds_reveal, counting EXTERIOR windows; the calibrated per-room field universal_rules.py:1027 angokrasciu_gkp_m (excludes exterior via is_exterior, hits 89.5 m to the dot, exposed as angokrasciu_gkp_m_total at vision_call.py:430/2058) is computed then IGNORED. FIX: make both lines consume room["angokrasciu_gkp_m"] / the _total field instead of recomputing inline. One source of truth. Kills a +55% over-quote on two lines simultaneously.

H2. Rotband 50% share is stale (+59.2%, ~€820 over). WRONG: "Sienų lyginimas Knauf Rotband" = 220.74 m² vs contractor 138.69. CODE: vision_call.py:1145 rotband_share default 0.50 × walls_paint. The 0.50 was calibrated 2026-05-27 when walls_paint=277.33 (→138.69); pipeline now yields walls_paint≈441.48, so 0.50× = 220.74. Correct share for this fixture ≈0.314. FIX: stop deriving Rotband as a fixed fraction of a moving base — either re-derive against current walls_paint, or (better) make it an absolute block/concrete-wall area input read from extraction. Update the stale calibration comment.

H3. Skylių gręžimas symbol path silently fails (-93%). WRONG: "Skylių gręžimas plytelėse" = 4 vnt vs contractor 56. CODE: fallback path vision_call.py:1607 (n_holes = 1 langas × 4 = 4) fired instead of the symbol path vision_call.py:1598; detected_symbols_summary IS present (klozetai2/praustuves3/vonios1/wc_remai2 → 2·4+3·6+1·8+2·3 = 40). FIX: debug why symbols don't reach this branch at generation time; wire them through so the symbol path fires (→~40), then recalibrate per-fixture multipliers upward toward 56 (current 4/6/8/3 still under-count even with full symbol data).

H4. Basin (praustuvė) count tied to toilet count (-60%, biggest santechnika gap). WRONG: "Praustuvės maišytuvo montavimas" = 2 vs contractor 5 (lines 40/41). CODE: vision_call.py:1755 driven by n_wet_with_klozetas=2; basins are structurally chained to toilets. detected_symbols_summary.praustuves=3+ is ALREADY read for skylių gręžimas (vision_call.py:1595) but NOT used here. FIX: decouple basin count from klozetas — wire sym.get("praustuves") into the praustuvė lines. Moves 2→5, closes the single biggest fixture gap.

H5. Kampai instability + redundant triple-emission (the two known items). WRONG #1 (fragility): "Dažymo kampų montavimas" = 501.3 m matches contractor 493.35 ONLY with cached adjacency; fresh extraction drops to 325 m (-34%) because pusiniai_m = n_partition_walls × H (universal_rules.py:923) silently zeroes when the flaky wall_adjacency pass finds no neighbours (gated by count_partition_corners default True, line 909). WRONG #2 (double-count): "Glaistymo kampai vidiniai" 350.91 (×0.7) + "Glaistymo kampai išoriniai" 150.39 (×0.3) = 501.3 = the SAME total re-emitted whole as "Dažymo kampų montavimas" (vision_call.py:1236-1249) → the same metrai are billable twice. FIX: (a) make pusiniai robust — don't silently zero when adjacency bails (fall back to a perimeter-based estimate); (b) resolve the legacy "+ perim" double-add at universal_rules.py:931; (c) collapse the vidiniai+išoriniai+montavimas triple into one labour line + one explicit material line so 501 m isn't priced ~2×, matching contractor's single line 19.

H6. Large-format tile = 0 (items 27+28, 13.18 m² missing premium tilework). WRONG: "Didžiaformačių plytelių klijavimas" not emitted. CODE: vision_call.py:1502 didzformat_count requires _plyteliu_specs entries with format_label "didžiaformatė"; berzas extract has none → count 0 → line suppressed (vision_call.py:1506). FIX: add a fallback so detected large tiles (from tile schedule / Vision format read) still emit even with empty _plyteliu_specs; add a niche-reveal tile concept for item 28 (8.7 m²).

=== MEDIUM ===

M1. Paint height-zone split wrong (+22.1% iki-3m / -28% virš-3m). WRONG: "iki 3m" 453.42 vs 371.4, "virš 3m" 153.69 vs 213.41. TOTAL dazymo 607.11 vs 584.81 = +3.8% (fine). CODE: vision_call.py:1012-1017 uses a BINARY room-level lubu_aukstis_m>3.0 test — a room with a partial 3.4m coffer dumps ALL its walls+ceiling into one zone. FIX: mirror the partial high_ceiling_area_m2 approach already plumbed for GKP at universal_rules.py:819-828. Pure reallocation — fixes both lines at once.

M2. GKP high-ceiling zone split wrong (line 2 -19.5%). WRONG: "GKP lubų virš 3m" 50.54 vs 62.82. TOTAL ceiling GKP 154.97 vs 165.60 = -6.4%. CODE: high_ceiling_threshold_m (>3m) vs contractor's 3,4m band carve different rooms (universal_rules.py:825-828). FIX: align the threshold logic with how rooms carry high coffers, or flag the standartinis/virš-3m split as approximate.

M3. Beapvadinės durys undercount (-56.4%). WRONG: "Durų angų paruošimas beapvadinėms durims" 17.1 m vs 39.2. CODE: vision_call.py:1281-1307 sums only elementai tagged tipas=="pasleptos_duris"; Vision likely tags most as plain "duris". FIX: audit Vision tagging; improve paslėptų-durų detection or add a UI flag for which doors are beapvadinės.

M4. Recessed-fixture & track lines missing (items 9/10/11 montavimas, 20/21/22 apdirbimas — ~59 vnt + 20 m unbilled). WRONG: difūzoriai (15+21), šviestuvai (38), TRACK (20.06 m) all absent. CODE: routed to SK_EL gated on symbols.difuzoriai/sviestuvai (=0 here, vision_call.py:1825/1848); glaistytojo apdirbimas side into SK_GD was never built. FIX: (a) surface placeholder GKP/Elektros/SK_GD lines even when symbol detection returns 0 (user fills kiekis), or (b) improve symbol detection; add a TRACK-system concept (montavimas + apdirbimas). As-is the app silently drops ~59 fixture installs.

M5. Silikonavimas undercount (-36%). WRONG: 18.4 + 13.8 = 32.2 m vs contractor 50.14. CODE: vision_call.py:1572-1573 wet_perim×0.8 + ×0.6; wet_perim excludes Skalbykla and under-weights corners. FIX: include all wet/tiled rooms, raise multiplier, reconcile to the single contractor "Kampų silikonavimas" line.

M6. Floor-tile -20% (Garažas dropped). WRONG: floor tile 31.89 vs 39.88; missing Garažas 10.10. CODE: universal_rules.py:855-858 tile_floor default False for garažas paskirtis → floor tile dropped. FIX: detect tiled garage from Vision or widen per-room override surfacing.

M7. Mixer potinkinė/virštinkinė split missing (lines 38-43 = 6 contractor lines → app 1 bundled). WRONG: "Dušo maišytuvo sistemos montavimas" = 2 collapses rough-in + trim + tub-filler. CODE: vision_call.py:1762-1764. FIX: split each mixer type into potinkinė (rough-in/štrobavimas) + virštinkinė (trim) lines to match contractor billing granularity (~doubles captured labour).

M8. Add bidė / higieninis dušiukas lines (items 45/46 = 6 ops, €0 quoted). CODE: no bidė concept anywhere. FIX: emit "Bidė dušiuko montavimas" (potinkinė+virštinkinė) gated on a symbol or per-vonia default; non-zero is better than absent.

M9. Verify Pastolių doesn't triple-count the >3m height premium. WRONG: app emits virš-3m glaistymas/dažymas m² + GKP virš-3m m² + "Pastolių nuoma" 3 d.d (vision_call.py:1934); contractor itemizes NONE separately (prices height into base rate). FIX: pick one mechanism (premium m² OR scaffolding d.d), or document they're complementary so pricing doesn't stack.

M10. Per-bathroom wall-tile precision (san107 -37%, san111 -25%, nets +9% by cancellation). CODE: universal_rules.py:749 perim×tile_height single band; over-adds Skalbykla/Darbo-kambarys tile contractor didn't itemise. FIX: move to per-wall tile area (elevation/išklotinė extractor) so individual room totals are right, not just the sum.

=== LOW ===

L1. Tile skirting missing (item 35, 22.72 m). CODE: universal_rules.py:984 zeroes grindjuostės on tile floors; app's only grindjuostės are painted MDF in SK_GD. FIX: add a "Grindjuosčių (plytelinių) supjovimas+klijavimas" line for tile-floored rooms.

L2. Verify "Lubų karnizo" 115.71 m (×2 lines, ~€700) is real. WRONG: contractor quotes NO ceiling cornice anywhere; app invents from karnizas_total. FIX: gate karnizas on actual detection, not a default.

L3. Add wall-GKP support to data model (unlocks items 5/6/8). CODE: sienos_gkp_m2 hardcoded 0 (vision_call.py:1404). FIX: populate from extraction — currently structurally impossible to emit wall niches, pertvarų storinimas, glued wall GKP.

L4. Add linear ceiling-box line (item 4, 11.16 m) + duct box (item 12, garage). CODE: gkp_extra_area_m2 override never populated. FIX: populate a box field from extraction instead of leaving the override empty.

L5. Add separate "Angokraščių sandarinimas" line (item 13, 89.39 m). Currently collapsed; contractor bills sealing separately from reveal-GKP finishing.

L6. Lentynėliai 4 vs 5 (item 29). CODE: vision_call.py:1632 n_full_vonia×2. FIX: bump default toward 2.5/vonia or read from drawing.

L7. 45° pjovimas +15% (item 36, 11.2 vs 9.7). CODE: vision_call.py:1545 max(...) heuristic overshoots. FIX: tune the 2·n_wet·tile_h term.

L8. Add "Lauko laistymo čiaupas" (item 37) and "Džiovyklės montavimas" (item 51). FIX: tie dryer to n_skalbykla (=1); tap as 0/manual default. Both deterministically derivable.

L9. Categorize the 5 §1 BoM lines (lapai/CD/UW/siūlės/savisriegiai) and the §3 plytelės-material ×1.08 + fugavimas lines as MATERIALS not work positions, so contractor-mode KŽ doesn't double-bill labour against the m² install/klijavimas rate.

L10. Verify Slenksniai (10 vnt, vision_call.py:1719) isn't double-billing flooring transitions counted elsewhere; no contractor equivalent in section 3.

L11. Re-validate overfit constants on a second contractor PDF: šiukšlių 0.075 m³/m² (vision_call.py:1954, +3.3% here) and pastolių 50 m²/d.d divisor — both fit to this single fixture.

L12. Label baseline placeholders ("Santechnikos taškų koregavimas" 1 kompl, "Statybvietės sutvarkymas" 1 kompl, "Apsauginės dangos" =floor area) as non-measured in the UI (saltinis=baseline / no drawing evidence).

---
# ROOT CAUSES (the ~30 line problems collapse into 9)

**RC1 — Fixture counts driven by room-type heuristics, not detected symbols.**
All santechnika counts come from `n_wet_with_klozetas` / `n_full_bathroom` (room-paskirtis counts), so basins are *chained to toilets* → 2 vs 5 (−60%), mixers bundled, bidė absent. The real counts exist in `detected_symbols_summary` (praustuves=3) but are only used for skylių gręžimas, never wired into the fixture lines.
→ Lines: 38–46, 51. Fix: drive fixture lines from `detected_symbols_summary`.

**RC2 — Symbol path silently fails / empty-symbol lines are suppressed.**
Skylių gręžimas falls back to 4 instead of the symbol path (40); difūzoriai/šviestuvai/TRACK emit nothing when symbols=0 instead of a placeholder.
→ Lines: 9,10,11,20,21,22,32. Fix: ensure symbols reach the generation branch; surface placeholder lines at count 0.

**RC3 — Duplicate/divergent formula for the same quantity.**
Angokraščiai computed two ways: the calibrated per-room `angokrasciu_gkp_m` (=89.5, matches truth 89.39) vs an inline recompute (=138.42, +55%) — and the bill uses the **wrong** one, on TWO lines.
→ Lines: 13,14. Fix: both lines consume `angokrasciu_gkp_m`. (Cleanest high-impact fix.)

**RC4 — Stale magic constants tied to moving bases.**
Rotband 0.50 share fit when walls_paint=277; now 441 → +59%. Šiukšlių 0.075, pastolių 50 m²/d.d, silikonas 0.8/0.6, lentynėliai ×2 — all overfit to this one PDF.
→ Lines: 15,34,53, pastolių. Fix: re-derive against current base or make absolute; re-validate on a 2nd contractor.

**RC5 — Flaky geometry dependence with silent zeroing.**
Kampai `pusiniai = n_partition_walls×H` depends on `wall_adjacency`, which bails → pusiniai→0 → kampai 501→**325** on a fresh run. Plus a legacy `+perim` double-add.
→ Line 19. Fix: robust fallback when adjacency bails; remove the legacy double-add.

**RC6 — Binary/all-or-nothing splits instead of partial allocation.**
Paint iki/virš-3m uses a room-level `lubu_aukstis_m>3.0` test (ignoring the partial `high_ceiling_area_m2` already plumbed for GKP); `tile_floor` all-or-nothing drops Garažas; wall-tile = perim×single-band per room.
→ Lines: 2,16,17,26, wall-tile. Fix: partial-area / per-wall allocation.

**RC7 — Whole categories unmodeled in the data model.**
`sienos_gkp_m2` hardcoded 0; no TRACK lighting, recessed-fixture apdirbimas, bidė, large-format tile, niche-reveal tile, tile skirting, exterior tap, dryer. ~19 contractor lines have no representation.
→ Lines: 4,5,6,8,11,12,27,28,35,37,45,46,51. Fix: extend the data model + extraction.

**RC8 — Same quantity emitted as multiple billable lines (double-count risk).**
Kampai emitted 3× (vidiniai+išoriniai+montavimas = 501 twice); angokraščiai twin (SK_GKP+SK_GD); tile material ×1.08 lines; Pastolių stacking on virš-3m premium.
→ Fix: emit each quantity once; separate material from labour explicitly.

**RC9 — Errors cancel at the aggregate, hiding line-level inaccuracy.**
Wall-tile nets +9% (san107 −37%, san111 −25%, +extra Skalbykla); paint total +3.8% but iki/virš split ±25%; kampai total matches but composition wrong. The eval/benchmark passes while individual lines are wrong — *this is why the bugs went unnoticed.*
→ Fix: validate at line level, not just totals.

## Highest-leverage fix order
RC3 (angokraščiai, clean +55%×2) → RC4 (Rotband, clean +59%) → RC1 (basins 2→5) → RC5 (kampai, the flagged one) → RC2 (symbol path) → RC6 (zone splits) → RC8 (de-dup lines) → RC7 (new categories, biggest effort) → RC9 (line-level eval).
