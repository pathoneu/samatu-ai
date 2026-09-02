# Making every quantity auditable — data reality + three options

**Date:** 2026-09-02 · **Status:** research, nothing implemented · **Surveyed:** `viewer-rebuild` @ `3d82131`
**Trigger:** contractor feedback on the live product. Read §0, then §1 — the options in §3 only make sense once you accept what §1.9 says.

> ⚠️ **Line numbers in `backend/extractor/vision_call.py` and `frontend/src/components/project/AssumptionsPanel.jsx` are "as of 2026-09-02 midday".** The Contractor Feature Batch (`docs/superpowers/plans/2026-09-02-contractor-feature-batch.md`) is editing both files right now — `_build_pozicijos_from_rooms` moved 1932 → 1973 during this survey alone. **Anchor on the symbol names, which are stable; treat the line numbers as a hint.** §6 covers how that batch interacts with everything below.

---

## 0. The ask, and why the obvious v1 is wrong

Contractor, verbatim:

> „parodyti kaip skaiciuojama x dalykai, kiekiai kad butu zmogui lengviau tikrinti klaidas — butu gerai ir reiketu kad AI ant brezinio arba kazkaip programeleje parodytu kaip kur ir ka skaiciavo kad zmogui butu iskart aisku kur ir ka reiketu pataisyti."

Three demands, not one: **how** it was computed, **where** on the drawing, **what to fix**.

Founder, rejecting a "click row → highlight one room" v1:

> „cia su situ reikia labai stipriai pagalvoti, nes siaip skaiciuojasi viskas per visa nama/buta ir dazymo kampu montavimas ir visa kita."

He is right, and the code proves it. On the reference project (Beržų g. 24, 11 rooms) the row **"Dažymo kampų montavimas — 501,30 m"** is
`Σ over 11 rooms of (n_walls_estimate × H + Σ_openings(W + 2H) + n_partition_walls × H + perimetras)`
— four different terms, over every room, three of which have no drawn object behind them at all. Highlighting "one room" answers none of the three demands. A row is not a place; it is a **filtered aggregate over the whole flat**.

---

# 1. DATA REALITY

## 1.1 The chain that produces a number

```
Vision + readers  →  patalpos[] primitives (plotas, perimetras, H, elementai, paskirtis)
        ↓  vision_call._recompute_per_room_via_python            (:1217)
calc_room_quantities per room   backend/extractor/universal_rules.py:1122
        ↓  merged back ONTO the room dict (PRIMITIVE_KEYS guard, :1294)
patalpos[] now carry ~53 computed fields each
        ↓  vision_call._build_pozicijos_from_rooms               (:1973)
pozicijos[]  — 85 flat lines, Σ over rooms, NO back-reference
        ↓  vision_call._consolidate_paint_pozicijos (:1622) / _consolidate_led_niche_pozicijos (:1732)
        ↓  vision_call._emit_v8_compat_fields                    (:867)
darbu_sarasas[]  — what the UI table and every exporter read
```

The two halves of an audit chain already exist. **They are never joined.** That single sentence is the whole finding.

## 1.2 What `calc_room_quantities` persists per room

`calc_room_quantities` (`universal_rules.py:1122`) returns a flat dict (`:1779–1857`) that is merged onto the room and saved in the project blob. Verified against a real blob (`backend/data/demo-berzu-24-snapshot-20260714.json`, 11 rooms) and a fresh extract (`ground_truth/berzas/ai_extract.json`).

**Inputs echoed back (auditable):**
`plotas_m2`, `perimetras_m`, `lubu_aukstis_m`, `plotas_saltinis`, `lubu_aukstis_saltinis`, `door_area_m2`, `window_area_m2` (`:1855–1857`), `elementai[]`, `paskirtis`, `puslapio_nr`.

**Intermediate terms preserved:**

| Term | Field | Line |
|---|---|---|
| gross wall area | `walls_gross_m2` | `:1793` |
| perimeter actually used for walls (may differ from measured) | `_walls_perimetras_m` + `_perimetras_floor_applied` | `:1789–1790` |
| net paintable wall | `walls_paintable_m2` | `:1794` |
| net paintable ceiling | `ceiling_paintable_m2` | `:1822` |
| door / window deduction actually applied | `doors_deducted_m2`, `windows_deducted_m2` | `:1855–1856` |
| paint factor that scaled the walls | `_walls_paint_factor` | `:1802` |
| which evidence decided tile-vs-paint | `_tile_read_source`, `_tile_read_missing`, `_walls_full_tile` | `:1799–1801` |
| why a ceiling was / wasn't painted | `_ceiling_paint_source`, `_ceiling_finish_assumptions` | `:1820–1821` |
| whether virš-3m came from nominal H or an explicit zone | `_virs_3m_source`, `_walls_lower_bound` | `:1811–1812` |
| LT disclosure prose | `_wall_finish_assumptions[]` | `:1803` |

**Intermediate terms DESTROYED (this is the gap):**

| Lost term | Where it lived | Consequence |
|---|---|---|
| `inner_corners_m`, `opening_reveals_m`, `pusiniai_m`, the `+ perim` term | `universal_rules.py:1696–1712`, collapsed into one `kampai_m` at `:1826`; **the sub-fields were deliberately deleted 2026-06-02** — see the comment at `:1829` ("Dead output — collapsed to a single total") | The founder's exact example — kampai — is the ONE family whose term breakdown was intentionally removed. It must be re-added. |
| `n_doors` / `n_windows` | derived by `vision_call._elementai_to_counts` (`:937`), never persisted (explicitly noted in `backend/api/recompute_quantities.py:120–147`) | Re-derived on every call; the row can't say "3 doors × 1,125 m²". |
| `doors_deduction = n_doors × 1.125` (the apdailos-branch deduction) | `universal_rules.py:1240`, `:1263` | `doors_deducted_m2` echoes the **legacy** `n × door_area`, not the 1.125 convention the apdailos branch actually used. The persisted field can contradict the arithmetic. |
| the per-room iki-3m / virš-3m paint split | `_room_virs_3m_paint` — a closure inside `_consolidate_paint_pozicijos` (`vision_call.py:1654`), now **also** a module-level helper at `:1761` (lifted by the in-flight batch) | Both live paint rows exist only as project totals. The lift to module level makes persisting it nearly free. |
| `tile_walls_area` inputs (`share × perim × height`) | `:1327` (apdailos branch), `:1401` (legacy branch) | Tile m² can't be explained. |
| `extra_walls_m2` / `extra_walls_virs_3m_m2` contributions | read `:1245`, added at `:1445` | Silent additions to the wall area. |

There **is** one human-readable derivation string: `room["calculation_trace"]`, written at `vision_call.py:1358`:

> `perim(13.50) × H(2.80) = 37.80 m² − 0 lang./3 dur. atimimai → dažymas 43.14 m². Skaičiavo Python (deterministinis).`

It covers **only the paint area**, only per room, and it is refreshed on Prielaidos edits (`recompute_quantities.py:223`). Per the competitor scan (§2) this is *ahead of the market* — every tool surveyed shows a formula *template*; we render an *evaluation*. It is currently unreachable in the UI (§1.6).

## 1.3 What the position builder does — and throws away

`_build_pozicijos_from_rooms` (`vision_call.py:1973`, ~1230 lines, **64 emit sites**) builds each line with `_sum(field)` (`:1988`) or `_sum_filtered(field, paskirtys)`. The emitted dict is:

```python
{"skyrius", "aprasymas", "vnt", "kiekis", "saltinis",
 optional: "medziagos_*", "confidence", "_confidence_reason",
           "_assumption", "_detalus", "_medziagos", "_detail_m2", "_height_zone"}
```

**No `id`. No room references. No term breakdown.** A position's identity is its Lithuanian label string — `_price_index` / `_norm_label` in `backend/api/recompute_quantities.py:470–509` index a priced row three ways (exact, tier-stripped, paren-stripped) plus a `_LEGACY_LABEL_MAP` (`:441–466`) of renames, purely to stop a relabel from orphaning the user's price. `ARCHITECTURE.md:52` already names the fix — *"stable line IDs (hash of room + line-type + base description) — a queued task."*

Corroborating dead surface: `recompute_quantities.py:339–405` implements `add_symbol` / `remove_symbol` / `color_zone` / `override_pozicija` keyed on `target_pozicija_id`, but nothing in the builder sets `id` and **no frontend caller exists** (grep: zero hits for `target_pozicija_id` in `frontend/src`). A per-position id contract was designed and never wired.

`_emit_v8_compat_fields` (`:867`) then copies pozicijos → `darbu_sarasas` through an explicit allow-list (`:888–909`) that carries `confidence` and `_confidence_reason` **but drops `_assumption`, `_detalus`, `_medziagos`, `_detail_m2`, `_height_zone`**. Since both live tables read `darbu_sarasas`, those five fields are lost before they reach the UI.

## 1.4 Position family × decomposability

Measured on the reference project by re-running `_build_pozicijos_from_rooms` in-process over the saved rooms (85 lines with full reader context; 70 without symbol context). Legend: **Σ-room** = the total is exactly `Σ` of a field already persisted on each room, so a contribution table is pure arithmetic today.

| Family (example line, reference project) | Per-room decomposable today? | Drawing geometry available? | Assumption-driven terms in the number |
|---|---|---|---|
| **Sienų, lubų glaistymas/dažymas iki 3 m — 403,37 m²** and **virš 3 m — 203,74 m²** | **Partly.** `walls_paintable_m2` + `ceiling_paintable_m2` are Σ-room and reconcile to 607,11 m² exactly. The **iki/virš split is not persisted** — `_room_virs_3m_paint` (`vision_call.py:1654` / `:1761`). | Room polygon (5/11 rooms) or printed-number marker (11/11) | H source; `_walls_paint_factor`; door deduction convention 1,125 m²/door; `_tile_read_source`; perimeter floor (`_perimetras_floor_applied`) |
| **Sienų lyginimas Knauf Rotband — 132,44 m²** | Yes, pro-rata: `walls_paint × rotband_share` (`:2058`, emit `:2065`), default 0,30 | inherits paint rooms | the 30 % share itself — a pure assumption, already disclosed in `_assumption` |
| **Dažymo kampų montavimas — 501,30 m** | **Room-level only** (Σ `kampu_metrai` ✓, `:2159`). **Term-level NO** — the 4 addends were deleted (`universal_rules.py:1829`) | rooms; the reveal term needs opening positions (**absent**, §1.5); the pusiniai term needs the shared-wall list (**computed then discarded**, §1.5) | `n_walls_estimate` defaults to 4; `count_partition_corners` defaults True; `n_partition_walls` from a Vision adjacency guess |
| **Angokraščių glaistymas-dažymas — 78,05 m** (+ identical GKP line) | Yes, Σ `angokrasciu_gkp_m` (`:2178`) | per-room only; the per-opening `W + 2H` contributions are recomputed from `elementai[]`, which has **no coordinates** | exterior-window rule (`_exterior` flag); schedule-anchored vs read dimensions (`_schedule_anchored`) |
| **Durų angų paruošimas beapvadinėms durims — 17,10 m** | **NO.** Computed inline over `elementai` (`:2181–2192`), then **rescaled** to a text-reader count (`:2199–2206`) | none | the avg-reveal 5,1 m fallback; the `_door_types` reconciliation |
| **Grindjuosčių sumontavimas/dažymas — 107,67 m** | **Yes but capped.** Σ `grindjuosciu_m` = 111,87 m, then clamped to `0,65 × Σ plotas` = 107,67 m (`:2237–2267`). Each room gets `_grindjuosciu_capped=True`; `_meta` keeps pre/post. Decomposition needs pro-rating **and** disclosure. | rooms | the 0,65 m/m² empirical cap; `− 0,85 m` per door; +10 % waste |
| **Lubų karnizo sumontavimas/dažymas — 115,71 m** | Yes, Σ `lubu_karnizo_m` | rooms | which paskirtys get a cornice; +5 % waste |
| **LED nišų glaistymas/dažymas — 41,88 m** | Yes, Σ `nisu_metrai` | per-room; niche `elementai` carry `_source`/`_confidence` but no coordinates | niche inference (`niche_inference.py`), enumerated-exclusion gate |
| **GKP lubų montavimas std 104,43 / virš-3m 50,54 m²** | Yes, Σ of the two fields | rooms | `ceiling_type` read vs default; the 3,0 m boundary; `high_ceiling_area_m2` (never produced by any Vision lane) |
| GKP sheets / CD / UW / joints / screws (5 lines) | Derived from `gkp_total` by constants (`:2330–2360`) | inherits | 3,0 m²/sheet, ×1,10, 1,6 / 0,4 / 1,5 m/m², 30 screws/m² |
| **Plytelės — 18 lines** (`Vonios sienų…`, `Kitų grindų…`) | Yes, `_sum_filtered` by paskirtis (`:2374–2379`) | rooms; **`_wall_elevations[]` gives page + `wall_id` + mm tile bands** — the best non-room anchor we have | tile height/share resolution chain; the 1,08 waste; the "Kitų" residual bucket |
| **Silikonavimas — 43,89 + 33,16 m** | **NO — and it contradicts the per-room field.** Positions use `tiled_perim × 2,3` = 77,05 m where `tiled_perim` includes rooms with `plyteles_share ≥ 0,6` (`:2471–2477`); Σ per-room `silikonavimas_m` (wet-only, `universal_rules.py:1854`) = 52,90 m. Two definitions, one persisted, the other billed. | rooms | ×2,3 coefficient; the 4:3 split; the ≥0,6 tiled predicate |
| **Plytelių grindjuosčių supjovimas — 23,60 m** | **NO.** Inline per-room loop (`:2613`+), contributions discarded | rooms | wet-room exclusion; −0,85 m/door; +10 % |
| **Plytelių 45° pjovimas — 9,20 m** | **NO.** `max(wet_perim × 0,4, 2 × n_wet × tile_h)` (`:2484`) | wet rooms | both branches are heuristics |
| **Skylių gręžimas plytelėse — 4 vnt** | **NO.** `klozetai×4 + (praustuves+plautuves)×6 + vonios×8 + wc_remai×3` from **project-level integers** (`:2548`) | **none** | every multiplier |
| **Hidroizoliacija — 2 vnt** (`_detail_m2` 20,4) | Room **count** decomposable; the m² is Σ `hidroizoliacija_m2` | wet rooms | which paskirtys count as wet; the splash-zone geometry |
| **Santechnika — 14 lines** (WC rėmas, klozetas, maišytuvai, plautuvė…) | **Room-count lines yes** (`n_vonia`, `n_wc`… `:2732`+); **symbol-count lines NO** (`detected_symbols_summary` is a dict of integers, `prompt.py:290`) | **none** — see §1.5 | potinkinis/virštinkinis assumption (disclosed, `_record_san_assumptions` `:2868`); every paskirtis default |
| **Elektra — rozetės 66, šviestuvai 35, LED 42 m…** | **NO.** Project-level symbol integers (`:2889`+) | **none** | the legend-anchor gate for difuzoriai |
| **Ventiliacija — ortakiai D125 30 m** | **NO.** `difuzoriai_n × 5,0 m` heuristic fallback (`:3015`) | none | the whole line is a fallback |
| **Pastolių nuoma — 4 d.d.** | Yes, via `_room_virs_3m_paint` / 50 (`:3159`) | high rooms | 50 m²/d.d. |
| **Šiukšlių išvežimas 12,4 m³ / Apsauginės dangos 165,61 m²** | Project-level formula on `bendras_plotas_m2` (`:3170`+) | whole plan | 0,075 m³/m² |
| **12 checklist rows** (`kiekis=None`, `saltinis:"checklist"`) | N/A — the honest TODO rows | none | the `_assumption` text says where to look |

Reference-project totals: **85 positions** — `skaiciuota_is_brezinio` 49, `paskirtis_default` 13, `checklist` 12, `simboliai_brezinyje` 9, `baseline` 1, `lubu_aukstis>3m` 1. Confidence: **35 žalia / 37 geltona / 13 raudona**; 19 carry `_assumption`.

**Score: of ~30 families, ~14 are Σ-room decomposable from persisted data today, ~6 need a small persistence addition, ~10 (all symbol/elektra/santechnika/plytelių-operations) have no per-room decomposition at all because their driver is a project-level integer.**

⚠️ **Existing blobs can already fail the Σ check.** The saved demo snapshot's `pozicijos` were built by an older engine than its room fields (it still carries `Glaistymo kampai vidiniai/išoriniai`, retired in RC8 2026-06-06): Σ `kampu_metrai` = 501,30 vs the stored row 387,10. **Any "total = Σ parts" panel must be computed by the same backend pass that builds the total, never re-derived on the client.**

## 1.5 Geometry inventory — what can actually be drawn

**What we have (verified in a real blob):**

| Artefact | Field | Space | Coverage on reference project |
|---|---|---|---|
| Room outline | `polygon_pct` (0..1) + `polygon_pdf` (points) + `page_width_pdf`/`page_height_pdf` + `polygon_source` + `polygon_confidence` (`main.py:7574–7581`) | percent = **display space, rotation already applied** (poppler bakes `/Rotate`; `lib/pageRotation.js:5–11`) | **5 / 11 rooms** |
| Printed room-number anchor | `marker_pct` + `marker_source:'plan_label'` (`main.py:7513–7521`) — deliberately never falls back to a bbox centroid | percent | **11 / 11 rooms** |
| Room → page | `puslapio_nr` (`prompt.py:106`) | — | 11/11 (all page 2) |
| Coarse room box | `bbox_pct` (`prompt.py:107–117`) | percent | most rooms |
| Eksplikacija table row | `eksplikacija_row_bbox` + page dims (`pdfplumber_eksplikacija.py:614–623`, merged `vision_call.py:4071`); page in `_eksplikacija` / `eksplikacija_source_page` | **PDF points** | rooms matched to the table |
| Page classification | `puslapiai[] {nr, tipas, pavadinimas, confidence}` | — | all pages |
| Tile evidence | `_wall_elevations[] {page, room_name, wall_id, tile_zones[from_mm,to_mm], niches[], confidence}` (`wall_elevation.py:26–54`) | page + wall id, **no pixels** | projects with išklotinės |
| Ceiling-height marker | per room `_height_marker_evidence {chosen_m, page, markers[], values_m}` (`height_markers.py:618–623`, `:942`) | page only | rooms with a marker |
| User measurements / counts | `{id, kind, page, points[], classification, color, confidence, source}` (`lib/measurements.js:51–62`) | **PDF points** | user-authored |

**What we do NOT have — the three hard gaps:**

1. **Openings have no position.** The `elementai` schema (`prompt.py:161–181`) is `{tipas, kiekis, plotis_mm, aukstis_mm, ilgis_m}` — no bbox, no point, not even a wall id. Every reveal / corner / opening-deduction term is therefore un-pointable. This is the single largest blocker to "show me where the angokraščiai are".
2. **Symbols have no position.** `detected_symbols_summary` (`prompt.py:290`) is a dict of integers. Worse, the enumerated evidence **is produced and then thrown away**: `sanitary_fixture_reader` returns `prietaisai: [{tipas, vieta}]` (`:77`, `:236`), and the call site keeps only `counts` (`vision_call.py:4755`). Elektra/ventiliacija never enumerate at all.
3. **Shared-wall detail is computed and discarded.** The production adjacency pass returns per-room neighbour lists with `shared_wall_count`, `wall_types` and an `evidence` string (`vision/adjacency_extractor.py:37–56`), but `apply_adjacency_to_rooms` (`:213–251`) writes only `n_partition_walls`, `_exterior_wall_count`, `_adjacency_confidence`; the payload `adj` is dropped at the call site (`vision_call.py:3636`). The pusiniai-corner term's own explanation is one line of persistence away.

**One large latent asset.** A full wall-level graph exists as a cached, real output for our own PDFs: `.vision_cache/room_graph/*.json` (8 files) contains `vertices[{id,x_pct,y_pct}]`, `walls[{id,start_vertex,end_vertex,angle_deg,thickness_mm,is_exterior,room_ids}]`, `rooms[{nr,polygon_walls[]}]`, `openings[{id,wall_id,type,is_exterior,hidden}]` — i.e. **every opening attached to a specific, drawable wall segment**. On the reference plan: 26 vertices, 33 walls, 11 rooms, 16 openings. But `plan_assembler.py:10–26` states it plainly: *"EXPERIMENTAL — NOT IN PRODUCTION PATH… never beat the production `extract_interior()` flow in real Vision tests."* Not free; not fantasy either.

## 1.6 Provenance already on rows — and what reaches the user

**Backend produces:**
- `confidence` ∈ `zalia|geltona|raudona` + `_confidence_reason` (LT prose) — `extractor/confidence.py:168`, class table at `:30–104` (label-substring matched; calibration facts kept as comments, never in the user string, guarded by a vocabulary test — see the 2026-08-31 note at `:32–44`).
- `saltinis` ∈ `skaiciuota_is_brezinio | paskirtis_default | simboliai_brezinyje | checklist | baseline | lubu_aukstis>3m`.
- `_assumption` (19 rows), `_detalus` (the collapsed split labels), `_medziagos`, `_detail_m2`.
- Project-level `_lt_warnings[]` (`lt_rules.py:118`), which already carry a machine-readable `code` + `field` + `value` + `expected` so a warning can offer a jump (`:172–182`), and forward the per-room `_wall_finish_assumptions` / `_ceiling_finish_assumptions` prose (`:227–252`).

**Frontend renders (live interior path only):** confidence dot + `_confidence_reason` in a `title=` (`WorkspacePanel.jsx:905–907`, `:963`), the same reason **visibly** in the review queue (`ReviewQueueSidebar.jsx:312–313`), `ProvenanceChip` + `EksplikacijaSourcePopover` on room rows (`WorkspacePanel.jsx:496–511`, `:652–657`), `ConfidenceBadge` with a per-source area breakdown and a "patvirtinti" button (`ConfidenceBadge.jsx:95–115`), the manual-override badge + `ai_kiekis_original`.

**Frontend never renders:** `_assumption`, `_detalus`, `_medziagos`, `_height_zone` — **zero hits in `frontend/src`** (and three of them are dropped by the `darbu_sarasas` allow-list anyway). `_detail_m2` renders as an unlabelled 10 px subline (`WorkspacePanel.jsx:1081–1090`). The Kiekiai tab shows **no** provenance at all — `ProjectMainView.jsx:272–273` hardcodes `sourceDot = null; confDot = null` per FIX-8.

**No per-row expand exists on either live table.** Only skyrius-level collapse.

**Four ready-made components are written and unreachable:**

| Component | File | Why unreachable |
|---|---|---|
| `RoomCard`'s „Skaičiavimo paaiškinimas" `<details>` — the **only** true `X = A × B − C` rendering in the app, printing `room.calculation_trace` | `components/project/RoomCard.jsx:417–458` | imported only by `RoomsGrid.jsx:173`, mounted in the `kiekiai` tab at `InteriorProject.jsx:1286` — and **no `setTab('kiekiai')` call exists anywhere** (verified). 507 dead lines. Worse: the projection at `:1287–1293` strips `calculation_trace` even if reached. |
| `FormulasCard` — 11 canonical LT formulas with sources (NRM2 §29, Q-tables, coverage tables) | `AssumptionsPanel.jsx:674–788` | defined twice, **never rendered** (verified: no `<FormulasCard` JSX repo-wide) |
| `RowDetailPanel` — slide-over with label/section/unit/qty/price/confidence/reason | `RowDetailPanel.jsx:15` | mounted only at `ProjectDetail.jsx:342`, after the interior early-return at `:220–221` |
| `TraceOverlay` — a **complete** react-konva renderer for `trace_type` ∈ counted/area/linear with dots, filled polygons, perimeter lines, hover pulse and bbox fallbacks | `components/project/TraceOverlay.jsx:21–124` | zero importers; built for the retired react-pdf Stage, not `PageOverlayHost` |

## 1.7 The 2026-04-26 traceability spec: 60 % built, then orphaned twice

`docs/superpowers/specs/2026-04-26-bidirectional-plan-traceability-design.md` already proposed exactly what the contractor is asking for: `trace_type` ∈ `counted | area | linear | **formula**`, `trace_links[]`, hover-pulse at 250 ms, click → auto-switch sheet → zoom → 5 s marker, a multi-page `1/5 [< Ankstesnis][Kitas →]` stepper, and — critically — a **room-click popover listing every position that contributed to that room**, grouped by kategorija (spec §"Reverse direction").

Both halves were built and both were orphaned by unrelated rewrites:
- **Backend producer:** `_classify_trace_type` / `_build_trace_links` / `_explain_formula` exist in `backend/interior_v8/universal_engine.py:374 / :406 / :550` — and `extract_v8` has **zero production call sites** (the 2026-04-28 deterministic refactor replaced it; `universal_rules.py:9–10` says so explicitly).
- **Frontend consumer:** `TraceOverlay.jsx` — orphaned by the EmbedPDF viewer rebuild.

**Read `_build_trace_links` before designing anything.** It shows the *shape* to keep and the *architecture to reject*: it reverse-engineers which rooms a position applies to by **substring-matching Lithuanian words in `aprasymas`** (`:432–447` — `wet_keywords`, `skip_keywords`, a 20-entry `SYMBOL_MAP`). That is a second, divergent copy of the builder's own predicates. Any real solution must have the **builder emit** the contributions, not have a downstream function guess them from the label.

## 1.8 Where a wrong input is fixed today

| Wrong thing | Fix surface | Live? |
|---|---|---|
| Ceiling height (per room or bulk) | `AssumptionsPanel.jsx:503–563` → `lubu_auksciai` → `POST /api/recompute-quantities` (`lib/recomputeApi.js:25`) | ✅ |
| Room painted / not painted | `AssumptionsPanel.jsx:578–602` → `walls_paint_override` | ✅ |
| Wall thickness, Q level, potinkinis mixers, window/door sizes | `AssumptionsPanel.jsx:411–483`, `:607–661` | ✅ |
| Room area / perimeter / paskirtis | `handleRoomsChange` → `POST /recompute-interior` (`InteriorProject.jsx:766–820`) — but its only live producer is `markRoomVerified`; `RoomsGrid`, the intended editor, sits in the dead tab | ⚠️ mostly unreachable |
| Room outline | „Taisyti zoną" → `POST /api/click-to-fill` → `polygon_source:'corrected'`. **Deliberately does not recompute** — the toast says so (`TakeoffViewer.jsx:752–754`) | ✅ (marking only) |
| A single position's quantity | inline `kiekis` edit → `manual_override` + `ai_kiekis_original` (`lib/quantityOverride.js:17–24`) | ✅ |
| Anything else (share, coefficient, predicate, opening count) | nothing | ❌ |

`AssumptionsPanel` accepts **no** `focusField` / `openTo` prop and its per-room inputs carry no `id`/`name`/`data-*` anchor (`:536–563`, `:578–602`), so a deep-link has nothing to scroll to. `SanityWarningsBanner` already has the *pattern* — a warning with a `code`/`field` renders an „Atidaryti Prielaidas" link (`:284–294`) — but calls `onOpenAssumptions()` with **no arguments**.

## 1.9 Five structural blockers (everything in §3 is a response to these)

1. **No position identity.** A row is a Lithuanian string. Nothing can be attached to it durably. (`recompute_quantities.py:470–509`; `ARCHITECTURE.md:52` already queues stable line IDs for an unrelated price-loss bug.)
2. **No contribution record.** 64 emit sites do `Σ` and keep no trace of who contributed what. The room half of the chain (`calculation_trace`) and the position half never meet.
3. **Openings and symbols have no coordinates.** ~10 families can never be pointed at on the drawing without a new extraction lane. Any option promising "everything on the drawing" is lying.
4. **The predicate is invisible and it is the likeliest error.** `_sum_filtered(..., WET)`, `_is_tiled(r) ≥ 0.6`, `walls_paint_factor == 0` for garažas, "which rooms get a cornice" — the contractor's real question is often *"why is the garažas in this number?"*, and no tool in the survey (§2) answers it, because in their model a human made that call by drawing.
5. **A verification UI without visible derivation makes things worse.** Measured false-green rate was 50–60 % before the confidence pass (`extractor/confidence.py:1–22`). A faster ✓ sweep over a list where half the greens are wrong trains rubber-stamping. **Drill-down must ship before checklist.**

---

# 2. Competitor scan — condensed

Full per-product notes are in the research thread; the load-bearing conclusions:

**Two architectures exist, and we are neither.**
- **Condition / assembly** (On-Screen Takeoff + Quick Bid, STACK, PlanSwift, CostX, eTakeoff): a named condition holds unit + formula; measured objects are *drawn into* it; the bid line is the condition's total; drilling down lists the objects, each at a known page + coordinates.
- **Markup list** (Bluebeam): every measurement is a row; derived values are extra columns; the row *is* the markup.

**Every audit chain in the survey terminates at a human-drawn object.** Our leaves are arithmetic over inferred room attributes. There is no object to fly to.

**Nobody can audit a filtered aggregate.** Bluebeam's Formula custom column is verified **strictly row-local** — no cross-row reference, aggregation limited to an `Include In Totals` subtotal flag (`support.bluebeam.com/user-manual/menus/window/custom-columns.html`). STACK's Item Formula converts *one* takeoff variable (`help-preconstruction.stackct.com/docs/working-with-assembly-formulas`). CostX Dimension Expressions read *one* dimension group's fields (`rib-software.com/en/blogs/rib-costx-dimension-expressions`). PlanSwift's `[!sum(...)]` is the only cross-row aggregate found and it sums a parent's own children. Our `kampai` is a `GROUP BY` with a `WHERE` presented as one number.

**Every tool shows a formula; none shows an evaluation.** Provenance is achieved by *co-location* (inputs as sibling columns), not by a trail. Our `calculation_trace` string is, on this axis, ahead of the market — it is just unreachable.

**The assembly tree is inverted relative to ours.** Assemblies fan *one measured object* → *many outputs*. We fan *many inferred rooms* → *one output*. So the gesture to copy is **not** STACK's "expand the assembly"; it is Togal's Quantities-Panel chevron: **expand the line into its contributing items**.

**Patterns worth stealing, by name:**

| Pattern | Product |
|---|---|
| Chevron-expand a line to its individual contributing items; right-click to reassign | Togal **Quantities Panel** (Folder → Classification → Item) |
| Named formula per derived output, opened by a pencil, defaulting to a **Coverage Rate** | STACK **Item Formula / Formula Editor** — maps 1:1 onto our 9 m²/l, 1,0 kg/m²/mm constants |
| Visible expression over named fields | CostX **Dimension Group Expression Editor** |
| 25 % fill + solid 2 px stroke of the same hue; square vertex markers; dashed for linear | Kreo colour-per-category |
| Persistent `SCALE 1:100 🔒` chip — "this value is committed, click to change" | Kreo scale-lock badge (we already have the honest `~1:100 (automatinis)` variant at `TakeoffViewer.jsx:307`) |
| Per-item review state None/Accepted/Rejected/Completed + replies | Bluebeam **Markup Status** *(training-recall, unverified)* |
| blue = added, red = removed, grey = unchanged | eTakeoff / Togal revision diff — do not invent our own |
| "Pan the markups to spot misses and double-counts" as an explicit **checker** step | Bluebeam, *Seven Steps to a Defensible Takeoff* |

**Bluebeam's stated doctrine is the sentence to put on the wall:** a digital measurement creates the visible markup *and* its data record simultaneously; when a quantity exists only in a table, *"review becomes trust-based instead of evidence-based."*

**Countfire** positions checking as the product (check sheets by symbol type, four checking stages) but its clickable-dot-back-to-drawing mechanic is unverified recall — re-verify before citing it in a design decision.

---

# 3. Options

All three share **one prerequisite**, because §1.9 blockers 1–2 make everything else impossible. Cost it once:

> ### P0 — The contribution ledger (prerequisite, **M**)
> **Backend.** Give every position a stable `id` (hash of `skyrius` + normalised base label + tier, per `ARCHITECTURE.md:52` — it also fixes the price-carry bug on its own). Add an `emit()` helper used by all 64 sites in `_build_pozicijos_from_rooms` that carries:
> ```python
> "contributions": [{"room_nr", "room_name", "page", "value", "unit",
>                    "terms": {...},            # optional per-term breakdown
>                    "included_because": "...", # the predicate, in LT
>                    "geometry": "polygon" | "marker" | "none"}],
> "excluded": [{"room_nr", "room_name", "excluded_because": "..."}],
> "roll_up": [{"op": "sum" | "cap" | "share" | "coefficient" | "constant" | "anchor",
>              "label": "...", "value": ..., "note": "..."}]
> ```
> `roll_up` is what makes a capped or scaled line honest: grindjuostės becomes `sum → 111,87 · cap 0,65 m/m² → 107,67`; Rotband becomes `sum → 441,47 · share 30 % → 132,44`; šiukšlės becomes `constant 0,075 m³/m² × 165,61`. The `anchor` op exists because the in-flight batch's T3 makes the ceiling quantity `eksplikacijos „Iš viso" − įtempiamų lubų patalpos` — a line that is deliberately **not** Σ-decomposable (§6).
> Families with no per-room driver emit `contributions: []` and a populated `roll_up` — they are honestly *un-decomposable*, not silently empty.
> **Do not** reconstruct contributions downstream from the label (that is what `interior_v8/universal_engine.py:432–447` does and why it drifted).
> **Also:** widen the `_emit_v8_compat_fields` allow-list (`vision_call.py:888–909`) to carry `id`, `contributions`, `roll_up`, `_assumption`, `_detalus`, `_medziagos` onto `darbu_sarasas`, since that is what the UI reads.
> **Persist the evidence we already throw away** (each ≈ 1–2 lines, all **S**): the adjacency payload (`vision_call.py:3636`), the sanitary `prietaisai[]` list (`:4755`), the height marker's `x_pct/y_pct` (`height_markers.py:397–450`), and the retired kampai sub-terms (`universal_rules.py:1829`).
> **Guard:** a backend test asserting that replaying `roll_up` over `contributions` reproduces `kiekis` to ≤ 0,01 for every line that claims decomposability — assert against `roll_up`, **not** against a raw Σ, or T3's anchored ceiling line fails by construction. Per §1.4, the panel must render the *server's* ledger and never re-derive Σ on the client.
> **Effort:** backend M (1 focused week: id scheme + emit helper across 64 sites + roll_up + tests). Frontend 0.
> **Timing:** start only after the Contractor Feature Batch's last task commits — T2/T3/T4 are editing `_build_pozicijos_from_rooms` and a 64-site refactor would collide (§6).

---

## Option A — „Audito režimas": select a row, the drawing answers

**Pitch.** A dedicated mode in the Brėžinys tab. Selecting a position row turns the whole viewer into an answer to *that one row*: every contributing room lights up **with its own contribution number printed on the drawing**, non-contributing rooms dim, excluded rooms show a grey „neįtraukta" chip with the reason, and the side panel proves `total = Σ parts` line by line. This is the contractor's literal request — numbers on the drawing — and it is the elegant answer to the fan-out, because the fan-out becomes the *display*, not a problem.

**UX flow.**
1. Contractor opens Brėžinys, clicks **„Kaip suskaičiuota"** on „Dažymo kampų montavimas — 501,30 m" in the right panel.
2. The drawing enters audit mode: header strip reads `Dažymo kampų montavimas · 501,30 m · 11 iš 11 patalpų`.
3. **Every contributing room** gets a red ring at its printed number plus a chip whose second line is now that room's contribution: `103 Koridorius` / `81,40 m`. Rooms with a traced polygon get the polygon tinted; rooms with only a marker get the ring — the existing honest tiering carries over unchanged.
4. Excluded rooms show a grey chip: `105 Garažas · neįtraukta — nedažoma pagal paskirtį`. **This is the highest-value pixel on the screen** (§1.9 blocker 4).
5. The panel below shows the ledger: 11 rows summing to 501,30, then a `roll_up` strip; each row expands to its terms (`4 sienos × 2,80 = 11,20` + `angos 3×(0,9+2×2,1) = 15,30` + `pusiniai 3 × 2,80 = 8,40` + `perimetras 15,00`).
6. Any row → click the number → jump to the room's page and focus it; click the **term** → the fix surface for that term (H → Prielaidos focused on room 103; openings → the room's `elementai` list; „nedažoma" → the walls-paint toggle for 105).
7. Rooms on other pages are grouped under `Kiti puslapiai (2)` with a page jump.

**Backend changes.** P0 only. Plus: emit the per-room iki/virš-3m paint split (turn `_room_virs_3m_paint` into a persisted field) — **S**.

**Frontend changes.**
- `RoomZoneLayer` already does almost all of this. It renders SVG label chips with a two-line body (`:181–189`, `:304–317`), has `focusedRoomNr` + `hoveredRoomNrExternal` + `hiddenRoomNrs` + `onRoomClick` props (`:67–81`), a pulsing focus ring (`:152–176`), overlap fanning (`spreadOverlappingMarkers`), a dashed/„apytikslė" tier for synthesized geometry, and an honest „N patalpų be vietos plane" chip (`:329–339`). **Required change: accept a `Map<room_nr, {value, label, tone}>` instead of the single `focusedRoomNr`, and let the chip's second line come from that map instead of `z.areaLabel`.** That is the difference between a demo and a product, and it is **S–M**, not a rewrite.
- `buildRoomZone` (`lib/roomZones.js:120–188`) gains an optional `contribution` field — **S**.
- New `AuditModePanel` (the ledger) — **M**.
- Wire the existing bidirectional hover (`WorkspacePanel.jsx:442–443` → `InteriorWorkspace.jsx:596` → `hoveredRoomNrExternal`) to also drive audit selection — **S**.
- **The one genuinely new viewer capability: zoom-to-region.** There is no `fitBounds`/`zoomTo` in the EmbedPDF wiring — only `scrollToPage` and whole-page `requestZoom(FitWidth|FitPage)` (`TakeoffViewer.jsx:190–191`, `:440`). Framing a room needs a scroll-to-rect built on the viewport plugin — **M**, and it is the highest-risk piece.

**Effort:** P0 (M) + backend S + frontend M–L. Realistically **3–4 weeks** to a good version.

**Risks.**
- **Coordinate drift is a repeat offender here.** `EksplikacijaSourcePopover.jsx:9–13` documents the last attempt: a halo drawn from `row_bbox` „flashed in arbitrary spots… exactly the dishonest UX we set out to remove", and was replaced by a text popover. **Mitigation:** that failure was on the retired react-pdf canvas; the EmbedPDF stack now has one rotation wrapper (`PageOverlayHost.jsx:132–156`) and a single coordinate boundary (`embedPdfAdapter.js:36–43`), and room percents are already display-space. The eksplikacija halo could in fact be revived correctly now — but treat that as a separate, later bet.
- **6 of 11 rooms have no polygon.** The marker tier saves it, but a screenshot with 5 tinted polygons and 6 rings will look inconsistent. Lean into it: the ring *is* the checked-drawing convention.
- **Chip pile-up.** 11 chips on one A1 sheet is dense. Mitigations already in the codebase: overlap fanning, the eye-toggles, and a "top 5 contributors" default with a „rodyti visas" toggle.
- **~10 families will show an empty drawing.** Elektra, santechnika, plytelių operations. The mode must say so explicitly (`Šiam kiekiui brėžinio nuorodų nėra — skaičiuota iš simbolių/prielaidų`) rather than showing a blank plan.

**Does NOT solve:** anything without coordinates (§1.5 gaps 1–3); term-level *placement* (you see the room contributed 81,40 m, not which corner); wrong *primitives* (a wrong perimeter is displayed confidently).

---

## Option B — „Skaičiavimo medis": a derivation panel, drawing as a supporting actor

**Pitch.** Make the *arithmetic* the product, not the picture. Every row expands into a formula tree that renders the actual evaluation — operator by operator, from the position total down through the roll-up, the per-room contributions, the per-term addends, and finally the primitives with their source and confidence — where every leaf is a link to either the drawing or the exact control that changes it. The drawing gets a jump-and-focus, not printed numbers.

**UX flow.** Click a row → `RowDetailPanel` (already written, `RowDetailPanel.jsx:15`, just mounted on the interior path) opens with a tree:

```
Dažymo kampų montavimas ......................... 501,30 m   🟡 tikrinti
│ „Kampų ilgis apskaičiuotas iš patalpų geometrijos…"   ← existing _confidence_reason
├─ Σ 11 patalpų .................................. 501,30 m
│  ├─ 101 Tambūras ............................... 48,10 m   [psl. 2 ▸]
│  │   4 sienos × 2,80 m ......................... 11,20 m   ⚙ aukštis
│  │   3 angos × (0,90 + 2×2,10) ................. 15,30 m   ⚙ durys/langai
│  │   2 pusinės sienos × 2,80 m .................. 5,60 m   🟡 iš AI gretimybių
│  │   perimetras ................................ 13,50 m   🟢 iš eksplikacijos [psl. 2 ▸]
│  └─ … 10 daugiau
└─ Neįtraukta: — (visos patalpos dažomos)
```

`⚙` opens the exact assumption control. `[psl. 2 ▸]` focuses the room in the viewer. `🟢/🟡` are the existing tiers. `FormulasCard`'s 11 canonical formulas (`AssumptionsPanel.jsx:674–788`) become the "kodėl taip skaičiuojama" footnote per family, with the standard cited (NRM2 §29, Merkblatt Nr. 2) — they are written, sourced and never rendered.

**Backend changes.** P0, plus richer `terms` on the contributions for the ~6 families where terms were destroyed (kampai first — restore what `universal_rules.py:1829` deleted) — **S–M**.

**Frontend changes.** Mount `RowDetailPanel` on the interior path (`ProjectDetail.jsx:220–221` returns before `:342`) — **S**. Build the recursive tree component — **M**. Add `focusField`/`focusRoom` props + DOM anchors to `AssumptionsPanel` (it currently has neither, `:211`, `:536–602`) and generalise `SanityWarningsBanner`'s existing jump (`:284–294`) — **S–M**. Surface `_assumption` / `_detalus` / `_medziagos` (already on the wire, zero readers) — **S**.

**Effort:** P0 (M) + **1.5–2 weeks** frontend. Clearly the cheapest of the three.

**Risks.**
- Density. A tree with 11 rooms × 4 terms is 44 lines. Needs collapse-by-default and a „top contributors" summary.
- It is a spreadsheet, not a drawing. It answers *how* and *what to fix* very well and *where* only by a page jump — i.e. two of the contractor's three demands.
- Numbers-only screens are exactly what Bluebeam warns against ("review becomes trust-based instead of evidence-based") — **unless** each leaf really does link back to a drawing location, which for ~10 families it cannot.

**Does NOT solve:** the literal "ant brėžinio" ask; term-level geometry; the families with no per-room decomposition (they show `roll_up` only, honestly).

---

## Option C — „Patalpų audito lapas": invert the unit of audit

**Pitch.** Stop auditing positions. A sąmatininkas checks a job **room by room** — he stands in the flat, or walks the plan, and asks *"does this room's work list make sense?"*. Make the room the audit unit: one room, one card, every work item that room contributes to, with its own numbers — and a reconciliation strip proving the room cards sum to the sąmata. The fan-out disappears because we stopped fighting it: we transpose the matrix.

**UX flow.**
1. Brėžinys tab, click any room (ring or panel row) → the **Patalpos audito lapas** slides in.
2. Header: `110 Miegamasis · 23,97 m² · perimetras 20,00 m · H 2,80 m` — each primitive with its `ProvenanceChip` and inline edit.
3. `calculation_trace` verbatim as the paint derivation (it already exists and already refreshes on recompute).
4. Body: everything this room contributes, grouped by skyrius:
   `Sienų, lubų glaistymas/dažymas … 53,75 + 23,97 = 77,72 m² · iki 3 m`
   `Dažymo kampų montavimas … 58,00 m`
   `Grindjuosčių sumontavimas … 16,60 m (po 0,65 m/m² apribojimo)`
   `Parketo klojimas … 23,97 m²`
   `Neįtraukta: plytelės — patalpa neplytelėta`
5. Footer: `Šios patalpos dalis sąmatoje: 1 847 € iš 24 310 € (7,6 %)` — the € framing a contractor actually reasons in.
6. A **„Peržiūrėta"** stamp per room. Progress reads `7 iš 11 patalpų peržiūrėta`. The verified flag already exists (`user_verified_at`, `markRoomVerified` in `projectStore.js:718–738`) and is the one signal that also feeds `scripts/build_ground_truth.py` — so the audit workflow *is* the ground-truth harvest, which is the open problem in `CLAUDE.md`.
7. Reconciliation tab: rooms down, positions across, totals both ways — a visible proof, and it exposes exactly the ~10 families that belong to **no** room.

**Backend changes.** P0 is enough — this is P0's ledger read transposed. Add a per-room € rollup (needs `kaina` joined by position id — free once positions have ids) — **S**.

**Frontend changes.** New `RoomAuditSheet` — **M**. Transpose the ledger client-side — **S**. Reuse `ConfidenceBadge` (`:95–115`), `ProvenanceChip`, `EksplikacijaSourcePopover`, and `RoomCard`'s `<details>` trace block (`RoomCard.jsx:417–458`) — mostly resurrection, **S**. Room-level verified state and progress — **S**, the store function exists.

**Effort:** P0 (M) + **2–2.5 weeks**.

**Risks.**
- **It does not answer the question as asked.** The contractor points at a *row*; this hands him a *room*. Needs a bridge (row → "which rooms?" → the room sheets), which is essentially Option A's ledger.
- The ~10 room-less families become a visible orphan bucket. That is honest, and it will look like a hole. It *is* a hole.
- It changes the mental model of the product — bigger UX bet than A or B.

**Does NOT solve:** the on-drawing numbers; a per-row question asked from the row.

---

# 4. Recommendation

**Ship P0 → B → A, and fold C's room-verified stamp into A. Do not ship the founder's rejected v1, and do not ship a checklist before a drill-down.**

Reasoning:

1. **P0 is unconditional.** All three options are the same data structure with three different renderers, and P0 independently fixes the price-carry bug that `ARCHITECTURE.md:52` already queues. It is the only work that cannot be wrong.
2. **B first, because it is the only option that can be *complete*.** Every family gets an honest answer — decomposable ones get a tree, the other ~10 get their `roll_up` and a plain statement that no drawing reference exists. A drawing-first option cannot be complete for those families no matter how much is spent (§1.5). Shipping B first also means the risky viewer work (zoom-to-region) is not on the critical path to the contractor seeing *any* improvement.
3. **A second, because it is what he actually asked for**, and because after P0+B it is mostly a `RoomZoneLayer` prop change plus a scroll-to-rect. Its expensive half is already written.
4. **C's insight survives as a feature, not an architecture.** The room-verified stamp is worth more than the room-first navigation, because it is also the ground-truth harvest, and it costs almost nothing on top of A.
5. **Sequencing is a safety property, not taste.** Per `extractor/confidence.py:1–22` the measured false-green rate was 50–60 %. A "peržiūrėta" sweep shipped before derivation is visible would train the contractor to confidently approve wrong numbers. Derivation first, checklist after.

### First shippable slice — precisely

**Backend (one PR):**
1. Stable `id` on every pozicija; `_price_index` / `_merge_user_edits` prefer `id` and keep label matching as fallback (`recompute_quantities.py:470–530`).
2. An `emit()` helper in `_build_pozicijos_from_rooms` carrying `contributions[] / excluded[] / roll_up[]`. Wire **three families only**: paint (`walls_paintable_m2` + `ceiling_paintable_m2`, with the iki/virš split persisted), **kampai** (restore the four sub-terms deleted at `universal_rules.py:1829` — this is the founder's own example), and grindjuostės (proving `roll_up` on a capped line).
3. Extend the `_emit_v8_compat_fields` allow-list (`vision_call.py:888–909`) with `id`, `contributions`, `roll_up`, `_assumption`.
4. Free persistence wins in the same PR: the adjacency payload, `prietaisai[]`, height-marker `x_pct/y_pct`.
5. Test: `abs(kiekis − Σ contributions)` after roll-up ≤ 0,01 for the wired families, on all corpus fixtures.

**Frontend (one PR):**
6. Mount `RowDetailPanel` on the interior path.
7. Render the tree for the three wired families; every other row shows the existing `_confidence_reason` plus `roll_up` and an explicit „detalizacija dar neprieinama šiai eilutei".
8. `[psl. N ▸]` on each contribution → existing `focusedRoom`/`FocusScroller` path (`TakeoffViewer.jsx:501–515`). No new viewer capability required for this slice.
9. `⚙` on the H term → open Prielaidos (untargeted at first; add `focusField` in the follow-up).

**Definition of done:** the contractor clicks „Dažymo kampų montavimas — 87 m", sees which rooms produced it, sees the four terms inside one room, sees which rooms were excluded and why, and reaches the control that changes the wrong one — without leaving the project.

---

# 5. Appendix — evidence we compute and then discard (all cheap)

| Evidence | Produced at | Discarded at | Would explain |
|---|---|---|---|
| Per-room neighbour list + `wall_types` + `evidence` prose | `vision/adjacency_extractor.py:37–56` | `vision_call.py:3636` (only 3 scalars kept) | the pusiniai-kampai term |
| `prietaisai[] {tipas, vieta}` enumeration | `sanitary_fixture_reader.py:77`, `:236` | `vision_call.py:4755` (counts only) | every santechnika row |
| Height marker `x_pct`/`y_pct` | `height_markers.py:433–446` | `_height_marker_evidence` keeps `page` + raw strings only (`:618–623`) | ceiling height, on the drawing |
| kampai sub-terms | `universal_rules.py:1696–1712` | deleted 2026-06-02 (`:1829`) | the founder's own example |
| `n_doors` / `n_windows` | `vision_call.py:937` | never persisted | opening deductions |
| Per-room iki/virš-3m paint split | `vision_call._room_virs_3m_paint` (`:1654` closure, `:1761` module-level) | never persisted | both live paint rows |
| Wall-level graph (vertices, walls, **openings attached to walls**) | `vision/room_graph_extractor.py:274`; real cached outputs in `.vision_cache/room_graph/` | `plan_assembler.py:10–26` — experimental, zero production call sites | opening positions — the §1.5 gap 1 |
| `_assumption` / `_detalus` / `_medziagos` / `_height_zone` | `vision_call.py` (19 rows carry `_assumption`) | dropped by the `darbu_sarasas` allow-list and/or unread by the frontend | assumptions, consolidated line members, materials |

---

# 6. Interaction with the in-flight Contractor Feature Batch

`docs/superpowers/plans/2026-09-02-contractor-feature-batch.md` is being executed **right now** on this same branch and explicitly hands the sixth contractor ask ("parodyti kaip skaičiuota") to this document. Four of its five tasks touch what §3 proposes. None of them conflict; two of them move the ground.

| Batch task | Effect on this arc |
|---|---|
| **T2 — Įtempiamos lubos, per-room toggle in Prielaidos** (removes that room's ceiling skim/prime/paint/sand) | **Synergy.** It clones the `walls_paint_override` wiring, so after it lands there are two per-room finish overrides. Both become `⚙` fix-targets in the Option B tree with zero extra work — and the removal is exactly the kind of thing that needs an `excluded[]` entry saying *why* a room contributes 0 m² of ceiling. |
| **T3 — sienų/lubų split + eksplikacija „Iš viso" ceiling anchor** (locked decision #2: ceiling quantity = eksplikacija total − stretch-ceiling rooms, shown as `165,61 − 24,30 = 141,31 m²`) | **Direct impact, and it validates P0.** The ceiling total stops being `Σ ceiling_paintable_m2` and becomes an **anchor minus deductions** — i.e. a line that is *not* Σ-decomposable and would fail a naive `total = Σ parts` check. P0's `roll_up` must therefore carry an `anchor` op alongside `sum`/`cap`/`share`/`coefficient`/`constant`, and the Σ-guard test must be written against `roll_up`, not against raw Σ. Note also that the founder has independently specified the *display* form `165,61 − 24,30 (įtempiamos lubos) = 141,31 m²` — that is a one-line `roll_up` rendering. **The transparency contract is already being demanded feature by feature; P0 is the generalisation of it.** |
| **T4 — global "Medžiagos" section, each material row showing which work it belongs to** | **Direct dependency.** "Which work it belongs to" is a durable back-reference from one row to another — the same identity problem as §1.9 blocker 1. If T4 ships that link keyed on the label string, it inherits every fragility `_price_index`/`_LEGACY_LABEL_MAP` exists to paper over. **Recommend: pull P0's stable `id` forward into T4** rather than building a second label-keyed link. |
| **T1 — add row into any section** | **Constraint on P0.** User-added rows have no `contributions` and no `roll_up`. The ledger must render them as "rankinė eilutė" rather than as a decomposition failure. |
| **T5 — kainynas xlsx + auto price fill** | Independent. But it makes `kaina` populated on far more rows, which is what makes Option C's `€ dalis sąmatoje` framing and the review queue's €-impact ranking (`lib/takeoffWorkflow.js:52–57`) actually useful. |

**Practical sequencing advice:** do not start P0 mid-batch — `_build_pozicijos_from_rooms` is being edited by T2/T3/T4 and a 64-site refactor would collide. Start P0 the moment the batch's last task commits, and land T4's material→work link on P0's ids rather than on labels.

---

# 7. v2 direction — „Patikra" (founder feedback, 2026-09-02 evening)

Founder on the §3 options mockup: *"nu man dar kazkaip ne taip atrodo, pabandyk dar stipriau
kazka sugalvoti. Ir prie to pacio butu gerai padaryti kad kai zmogus kazka pataiso kad AI
mokytusi is jo pataisymo."* Two signals: the options read as inspection surfaces, not a
workflow; and learning-from-corrections is now a first-class requirement.

**The reframe:** don't ship A/B/C as separate surfaces — fold them into one guided loop,
**Patikra**: after extraction the app walks the contractor through claims ranked by
`rankReviewRows` (€ impact × confidence, `lib/takeoffWorkflow.js`), one claim card at a time.
Card = the number + the evaluated formula (Option B, collapsed behind „kodėl?") + the single
most sensitive input surfaced explicitly. The drawing spotlights the claim's evidence
(Option A, auto-entered, not a mode). Verbs: „Teisinga ✓" (→ `user_verified`, ground-truth
harvest) / „Pataisyti" (→ fix the INPUT, live recompute ripple with € delta, correction
logged). Progress = a project trust meter that only human verification raises (Option C's
stamp, generalised). Mockup v2 at the same artifact URL.

**Learning loop — inventory (verified in code):** correction logging → `corrections` table
(`db.py:134`, every override); instant recompute (exists); ground-truth harvest →
`scripts/build_ground_truth.py` (exists); per-project calibration factors →
`api/calibrate.py` + `data/calibrations/` (exists, survives deploys); cross-project
promotion analyzers with human-review guardrails → `extractor/calibration_learner.py`
(≥3 projects, direction-consistent, IQR<0.05) + `extractor/learn_from_corrections.py`
(prompt-annotation reporter, ≥20% override rate). **Missing:** any user-visible trace of
this loop, and automatic per-USER priors („jūsų standartai": a correction repeated ≥3×
becomes that user's default for future extractions, opt-out-able). P0's ledger is also the
learning substrate — a correction is only learnable when we know which term/room/input it
targeted.

**Honesty constraints carried into UI copy:** „jūsų standartai" apply per-user only and
only from repetition; global accuracy promotion stays human-reviewed (no silent formula
rewrites); geometry-less families show their source instead of a plan; false-green history
(50–60%) still mandates derivation-before-checkmark inside each card.

Status: awaiting founder verdict on the v2 direction. P0 timing unchanged (after the
contractor feature batch lands).

---

## Sources

**Code (this repo, `viewer-rebuild` @ `3d82131`):** cited inline as `path:line`. Position/decomposition figures were produced by re-running `_build_pozicijos_from_rooms` in-process over `backend/data/demo-berzu-24-snapshot-20260714.json` (11 rooms) with reader context from `ground_truth/berzas/ai_extract.json` — no Vision calls, no paid extraction.

**Prior internal work:** `docs/superpowers/specs/2026-04-26-bidirectional-plan-traceability-design.md` (the original spec — read §"Reverse direction" and the `trace_type` taxonomy), `docs/superpowers/specs/2026-05-02-pdf-viewer-trust-design.md`, `docs/superpowers/research/2026-05-02-competitor-viewer-ui-deep-dive.md`, `.../industry-takeoff-tools.md`, `.../2026-04-28-takeoff-standards-and-pdf-ux.md`, `.../2026-06-14-pdf-viewer-togal-roadmap.md` (the false-green measurement), `docs/ARCHITECTURE.md` §"The viewer stack" + §"Known fragilities".

**External, fetched and read:** [Bluebeam custom columns](https://support.bluebeam.com/user-manual/menus/window/custom-columns.html) · [Bluebeam takeoffs guide 2026](https://www.bluebeam.com/resources/construction-takeoffs-guide-2026/) · [Seven Steps to a Defensible Takeoff](https://blog.bluebeam.com/digital-takeoff-steps/) · [CostX Dimension Expressions](https://www.rib-software.com/en/blogs/rib-costx-dimension-expressions) · [CostX Functions in Measurement](https://www.rib-software.com/en/blogs/rib-costx-functions-in-measurement) · [eTakeoff Dimension features](https://etakeoff.com/etakeoff-dimension/dimension-features/)

**External, search snippets only (pages not opened):** [Togal custom formulas](https://help.togal.ai/custom-formulas) · [Togal quantities list](https://help.togal.ai/how-to-use-quantity-list) · [STACK assembly formulas](https://help-preconstruction.stackct.com/docs/working-with-assembly-formulas) · [PlanSwift parts & assemblies](https://www.planswift.com/blog/use-parts-assemblies/) · [Quick Bid interactive bids](https://help.constructconnect.com/06-creating-and-managing-bids-alternates-and-change-orders-127/quick-bid-06-03-creating-interactive-bids-bids-connect-to-on-screen-takeoff-470) · [Countfire estimating errors](https://www.countfire.com/blog/reduce-estimating-errors-in-construction)

**Verified later the same day by three follow-up research passes against live vendor docs (Togal+Kreo, STACK/OST/PlanSwift, Bluebeam+Countfire):** Bluebeam Markup Status persists user+timestamp per status change and Studio Sessions keep an attendee-attributed Record log — confirmed; Bluebeam Quantity Link is PDF→Excel only (the "bidirectional" wording is marketing; no documented Excel→markup navigation); Countfire has NO clickable-dot-back-to-drawing — its audit is visual (colour-consistent record drawings, an inverted "symbols removed" drawing, check sheets whose hover tooltip gives drawing name + position). Kreo's Trace Link (measurement → spreadsheet cells) + Cell Range Filter (cells → measurements) + Scheduled/Unscheduled orphan filter is the strongest closed loop found; STACK's "Measurement by Takeoff" report is the one crisp bid-line → zoom-and-highlight instance, and STACK's own Audit Trail admits "clicking an event does not yet navigate to that location in the plan". Nothing found changes §4.
