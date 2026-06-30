# Sąmatų AI — Užduočių sąrašas + projekto state

> Atnaujinta: 2026-04-29 (po Sprint H PDF UX polish + critical fix'ų)
> Naudojama kaip „truth file" tarp sesijų — kas padaryta, kas liko, kur.

---

## 🟢 ŠIANDIENOS BATCH (2026-04-29) — 14 užduočių baigta + Rangovas additions

| # | Task | Files |
|---|------|-------|
| 1 | **CRITICAL** /recompute-interior fix (10→71 positions, 7.1× recovery) | main.py |
| 2 | English → LT tooltips (NRM2/VOB/Klasė) | RulesOverridePanel.jsx |
| 3 | Glaistymo lygis Q1-Q4 UI selektorius | RulesOverridePanel.jsx |
| 4 | **H1** Left vertical tool rail (Togal-style icon bar) | PdfViewer.jsx (LeftToolRail) |
| 5 | **H2** Top toolbar declutter (Pažangu/Eksplikacija icon-only on small screens) | PdfViewer.jsx |
| 6 | **H3** Bottom status bar (Įrankis · Mastelis · Keyboard hints) | PdfViewer.jsx |
| 7 | **H4** Tooltip + keyboard shortcut hints visi mygtukai | PdfViewer.jsx |
| 8 | **H5** Zoom dropdown su preset'ais (50/75/100/125/150/200 + Fit) | PdfViewer.jsx |
| 9 | **H6** Thumbnail rail collapsible su localStorage state | PdfViewer.jsx |
| 10 | **H7** PDF area 65→70% by default | InteriorWorkspace.jsx |
| 11 | **H8** First-time onboarding 3-step tooltips | OnboardingTooltips.jsx (new) |
| 12 | Mobile responsive restore (hamburger + stacked layout <768px) | AppLayout.jsx, Sidebar.jsx, InteriorWorkspace.jsx |
| 13 | Backup/restore localStorage projects (Settings export/import JSON) | projectStore.js, Settings.jsx |
| 14 | G2 Phase 2 — inline ✓/✏️/✕ accept/reject + `_review_status` field | ReviewQueueSidebar.jsx, WorkspacePanel.jsx |

### Papildomi task'ai
| # | Task | Files |
|---|------|-------|
| 15 | AI Chat quick reply suggestions atnaujintos (paint_class, NRM2, plytelių specs) | AiChat.jsx |
| 16 | Multi-floor helper `room_aukstas_from_nr()` + `group_rooms_by_floor()` (8 testai) | universal_rules.py, test_multi_floor.py (new) |
| 17 | Dead code sweep — `ProjectCanvas.jsx` ir `SymbolCounter.jsx` ištrinti | InteriorProject.jsx, PdfViewer.jsx |
| 18 | **BUG FIX** Dashboard projekto kortelė: backend `status='ok'` → „PARUOŠTA" (buvo „KLAIDA") | ProjectCard.jsx |
| 19 | **G8** Multi-layer visibility toggle (LayersDropdown — Žymėjimai/Eksplikacija/Rooms/Source dots) | PdfViewer.jsx (LayersDropdown component) |
| 20 | Setup Wizard pilnumas — paint_deduction_standard, paint_class, sienos_storis, paint_coats | SetupWizard.jsx |
| 21 | Frontend rendering of `_wall_elevations` — WallElevationsPanel su tile_zones mm precision | WallElevationsPanel.jsx (new), WorkspacePanel.jsx |
| 22 | **F2/F3 export forma** — backend `/export/f2` + `/export/f3` Excel su parašų laukais | main.py (~200 lines), ExportDropdown.jsx |
| 23 | **G5 Phase 1** Scale auto-detect endpoint `/detect-scale-hint` (regex „1:50" iš text layer) | main.py |
| 24 | Error tracking lite — `errorTracker.js` (localStorage 100 entries) + Settings eksportas | lib/errorTracker.js (new), main.jsx, Settings.jsx |

### Rangovas coverage audit additions (3 priority items, 78%→85%+ coverage target)
- **Sienų lyginimas Knauf Rotband** (description fix — exact LT pro wording, 5/5 projects)
- **Dažymo kampų montavimas** (NEW labor line, 5/5 projects, 665.98 m on test project)
- **Plytelių vidinių kampų silikonavimas** (split from sanitaryware sealing, 4/5 projects, 15.24 m)

Reference: [`docs/superpowers/research/2026-04-29-rangovas-coverage-audit.md`](superpowers/research/2026-04-29-rangovas-coverage-audit.md)

**Verify**: 146/146 backend pytest + Vite build clean (309KB main bundle, target <350KB ✅) + Playwright desktop+mobile screenshots + Layers dropdown visual confirmed + live `/export/f2` + `/export/f3` produce valid 5.8KB Excel files + `/detect-scale-hint` endpoint operational.

### Pripažintos atidėtos (out-of-scope autonomas sesijai)
- **G1 Editable polygons** — vartotojas explicitly paliepė praleisti (reikia daug interaktyvaus testavimo)
- **G3 Symbol search** (3-4 d.) — OpenCV pipeline + Vision symbol catalog
- **G4 Drawing diff** (4-6 d.) — phase correlation algorithmas, didelis scope
- **G9 Konva → SVG refactor** — perf benefit'as ateis tik po G1 (>500 polygons)
- **G5 Phase 2 frontend** scale auto-detect call'as iš NewProject upload flow (endpoint live'as, UI hook deferred)
- **§2A.2 Polygon tile zones** — reikalauja real wall_elevation data (Vision API spend + user PDFs)
- **§1 Production hardening** — paskutinis žingsnis prieš shipping (auth, monitoring) — per user preferences

---

## 🟢 PHASE A: 2026-04-29 antra pertrauka — 7 nauji task'ai

| # | Task | Files |
|---|------|-------|
| 25 | Rangovas audit #4-#7 — niche framing GKP + epoxy 45° pjovimas (Klasė 1 only) | vision_call.py |
| 26 | Project archetype templates — paint_class + paint_deduction_standard į PRESETS | ltLibrary.js |
| 27 | Sanity warnings UI — grouped by severity, dismissable per-warning, localStorage state | SanityWarningsBanner.jsx (rewritten) |
| 28 | Project soft delete + Šiukšliadėžė (30d. retention) | projectStore.js, Settings.jsx, Dashboard.jsx |
| 29 | Stats dashboard +2 metrics (Visas plotas, Vid. pozicijų sk., Per 30 d.) | StatsBar.jsx |
| 30 | Bulk price list CSV import (parser + UI) | PriceLists.jsx |
| 31 | Playwright comprehensive UX audit — 7 test groups, all PASS | test-audit-comprehensive.mjs |
| 32 | Localization audit — neradau English leaks user-facing tekstuose | (audit only) |

**Fresh PDF processed**: `Visi techniniai 01.28.pdf` (5.5MB, 17 pages) → 11 patalpos + 73 pozicijos. Saved as project `99e0ae97-f8c2-4fe0-a199-f9e3bb27f964`.

**bbox_pct quality finding**: fresh PDF Vision spatial reasoning = good (centroidų spread mean=0.322, sane layout). User'io existing project = blogai (random highlight'ai). Confirms PDF interactivity rewrite needs to handle variable Vision quality.

---

## 🟢 PHASE A+ deepening (2026-04-29 trečia bangą) — 7 nauji task'ai

| # | Task | Files |
|---|------|-------|
| 33 | **G5 frontend wiring** — NewProject upload → /detect-scale-hint → store project._scale_hint | NewProject.jsx |
| 34 | **Multi-floor Vision schema** — `aukstas` field per kambariui + cross-page floor-mismatch warning rule (`_rule_floor_consistency`) | prompt.py, cross_page_validator.py |
| 35 | **Wall elevation → pozicijos override** — kai `_wall_elevations` data yra, override `plyteles_sienos_m2` su mm precision (formula: tile_height_mm × wall_width_mm / 1e6) | vision_call.py + 7 testai |
| 36 | **Share token expiry + view tracking** — POST/GET /api/projects/{id}/share su expires_in_days + view_count + last_viewed_at + revoke | main.py, db.py |
| 37 | **F2/F3 PDF variants** — printable reportlab versions su signatūrų laukais. `/export/f2-pdf` + `/export/f3-pdf` endpoints + frontend dropdown | main.py, ExportDropdown.jsx |
| 38 | **Pytest edge cases** — empty rooms, single garažas, single-room, NRM2+Q4+Class3 combo, all-wet, cellar floor, high ceiling, paskirtis Unicode (9 testai) | test_edge_cases.py |
| 39 | **Rangovas coverage analysis** — static comparison (no $$ extraction) — agent dispatched | research/2026-04-29-rangovas-coverage-followup.md |

### Bug fixes per user feedback
| # | Issue | Sprendimas |
|---|------|-----------|
| | Excel Conf VISAS column dingsti | Pašalintas iš HDR list + A1:F1 merge (was A1:G1) — max_column dabar 6 |
| | Excel 3 GKP sheets → 1 | Normalize skyrius via `SKYRIUS_LEGACY_MIGRATION` BEFORE grouping into sheets |
| | „komutavimas" → „pajungimas" | Backend × 2 (vision_call.py:1251, 1274) + frontend × 2 (InteriorWorkspace.jsx) |
| | Delete project mygtuko nematyti | Pridėtas Trash2 button į InteriorProject ProjectTopBar (greta Eksportuoti) |
| | Frontend 3 GKP grupės | `SKYRIUS_LEGACY_MIGRATION` mapping išplėstas (GKP, Gipso kartono montavimas, GKP konstrukcija → „GKP montavimas"; Plyteles, Plytelių darbai → „Plytelių klijavimas"; etc.) |
| | grindjuostes ant garazas/parter | calc_room_quantities: skip grindjuostes if `walls_paint=0` arba `floor=concrete` |

### Research findings (Phase A+)
- **Sienų išklotinių varieties** (`docs/superpowers/research/2026-04-29-isklotines-quality.md`) — 40% LT projektų turi mm-precision išklotines, 60% schematiniai. Verdict: keep wall_elevation as opt-in fallback.
- **Rangovas coverage v2** — agent runs background'e

**Final verify (2026-04-29 vakaras)**: 162/162 backend pytest ✅ · Vite 310KB main bundle ✅ · Playwright comprehensive audit ALL PASS ✅

---

## 🟢 PHASE A++ (2026-04-29 vėlyvas vakaras) — 3 nauji task'ai po Rangovas v2 audit

| # | Task | Files | Tests |
|---|------|-------|-------|
| 40 | **HVAC Ductwork** — D100/125/160 mm ortakiai per-diameter + izoliacija + tvirtinimas. Vision schema atnaujinta (ortakiai_d100/125/160_m fields). Heuristic fallback iš difuzoriai count (~5 m per diffuser) | vision_call.py, prompt.py | **+6 testai** |
| 41 | **Tile format split** — didžiaformatės plytelės (>600×600) gauna papildomas labor lines (back-buttering klijai 5kg/m² + lygio kontrolė). Trigger when `_plyteliu_specs` turi `format_label="Didžiaformatė"` | vision_call.py | (validation per existing tests) |
| 42 | **Frontend `_scale_hint` display** — kai NewProject upload aptiko mastelį per text layer, rodom info banner'į „Brėžinio mastelis aptiktas automatiškai: 1:50" | InteriorProject.jsx | manual UI confirm |

**Rangovas v2 coverage finding**: All 5 audit items now COVERED in code. By labor-category: 85% solid for residential typical. By line-item exact match: 31% (granularity, not coverage). Top gap addressed: **HVAC ortakiai** (was 0%, now backend-ready).

**Final state**: 168/168 backend pytest ✅ · Vite 310KB main bundle ✅ · 6 background research agents successfully completed.

---

## 🟢 PHASE A+++ (2026-04-29 vakaras 2 — užbaigta po user feedback) — 4 bug fixes

| # | User issue | Sprendimas |
|---|------|-----------|
| 1 | Trash → page refresh → projektas vėl Dashboard'e, dingsta iš Šiukšliadėžės | `pullProjectsFromBackend` dabar **PRESERVE'INA** lokalų `_archived` flag mergeing'u su backend. Verified: refresh → archive flag išlieka, Šiukšliadėžė rodo, Dashboard nerodo. |
| 2 | F2/F3 export'ai nereikalingi (LT chars + nereikia kol kas) | **Pašalinta** iš backend (5 endpoints + 3 builders) ir frontend (4 dropdown items). **Backup'ą saugojau** `docs/superpowers/backup-2026-04-29-f2-f3-forms.py` (465 lines) — galim grąžinti po contractor feedback'o. |
| 3 | GKP montavimas vis dar 2-3 grupės sąraše + Excel'yje | **Stable-sort skyrius** pridėtas į `_build_pozicijos_from_rooms` finale (SKYRIUS_ORDER dict). Verified: GKP transitions = **1** (was 2-3). |
| 4 | Visi tie taškiukai ant rows confusing — abiejuose pusėse, skirtingos spalvos | **Confidence dot pašalintas** (info'rmuoja PERŽIŪRA queue'oje viršuje). **Source dot** lieka tik kai showProvenance toggle ON (default OFF). Default UI dabar clean, be vizualinio noise'o. |

**Final state**: 168/168 backend pytest ✅ · 310KB main bundle ✅ · Playwright comprehensive audit (7 groups) + Trash persist test PASS ✅

---

## 🎯 REKOMENDUOJAMA TVARKA (atnaujinta po 2026-04-28 research'o)

Research'as parodė, kad **competitive moat** = **eksplikacija-grounded confidence + editable polygons + LT-only F2/F3+STR reasoning**. Siūloma sekvencija:

| Pos. | Sprint / sekcija | Trukmė | Argumentas |
|------|------------------|--------|------------|
| 1️⃣ | **Sprint G — PDF Interactive Leap-Up** (G1+G2+G6+G7) | ~5–7 d | Editable polygons + Confidence Review Queue su 🟢 eksplikacija lock badge — vienintelis tikrai unikalus differentiator. UX leap-frog. |
| 2️⃣ | **§2 Accuracy fix'ai** (NRM2 + polygon tiles + sloped/stairwell + Q4 + paint class) | ~5–6 d | Tikrosios formulės gerinimas — tylūs 15–40% underestimates šiandien. |
| 3️⃣ | **§5 Wall elevation merge į pozicijas** (jau buvęs §2 task'as, dabar prieinamas po polygon tile fix'o) | ~1 d | Wall elevation → tile zones formulė unifikuojama su G1 polygon editing. |
| 4️⃣ | **Sprint G — likę** (G3 symbol search, G4 drawing diff, G5 snap) | ~9–13 d | Parity su Togal/Kreo. |
| 5️⃣ | **§3 UX polish** (F2/F3, mobile, Setup Wizard) | ~3–4 d | LT-only F2/F3 = nišinis differentiator. |
| 6️⃣ | **§1 Production hardening** (auth, monitoring) | ~2 d | Paskutinis žingsnis prieš shipping (per user preferences). |

---

## 🟢 PADARYTA (2026-04-28 sesijos)

### Architektūra
- ✅ Deterministic refactor — Vision tik primityvai, Python skaičiuoja
- ✅ pdfplumber eksplikacijos extractor (P3 atveju 100% deterministic, $0)
- ✅ Cross-page consistency validator (9 + 1 Rangovas-empirical taisyklės)
- ✅ Pdfplumber bbox extraction → frontend row highlight on eksplikacijos puslapyje
- ✅ Symbol counts (`detected_symbols_summary`) į main Vision prompt'ą — 14 tipų

### Pozicijų generator (vidaus apdaila)
~70+ line items per typical residential project:
- ✅ Sienų lyginimas Rotband + glaistymas Q1/Q2/Q3 (per coat) + dažymas + šlifavimas + gruntavimas
- ✅ Lubų glaistymas + dažymas (atskira nuo sienų)
- ✅ Glaistymo kampai (vidiniai 70% / išoriniai 30% split)
- ✅ Angokraščiai pair (Glaistymo skyrius + GKP skyrius — `Angokraščių apdirbimas GKP`)
- ✅ Paslėptų durų stakta (`Durų angų paruošimas beapvadinėms durims`)
- ✅ Grindjuostės su ratio-cap fix (max 0.65 m/m² floor)
- ✅ Lubų karnizas + LED nišos
- ✅ GKP lubų montavimas (standart vs >3m), GKP lapai, profiliai, savisriegiai, siūlių glaistymas
- ✅ Reviziniai dureliai + Dėžučių iš GKP WC mechanizmams
- ✅ Plytelės (vonia/virtuvė/kita) per location: klijavimas + plytelės + fugavimas
- ✅ Plytelių 45° pjovimas (outer corners formula)
- ✅ Silikonavimas (×1.2 multiplier)
- ✅ Skylių gręžimas plytelėse (symbol-driven: kloz×4 + praust×6 + vonia×8 + rėmas×3)
- ✅ Nuolydis dušo zonoje, lentynėliai dušo kabinoje
- ✅ Hidroizoliacija (collapsed 4→1 line per LT contractor convention, su `_detail_m2`)
- ✅ Grindys: išlyginamasis, parketas/laminato klojimas, slenksniai
- ✅ Santechnika (paskirtis-based): WC rėmas, klozetas, praustuvė, dušo maišytuvas, gyvatukas, latakas, plautuvė, virtuvės maišytuvas, skalbimo mašinos sifonas
- ✅ Elektra (symbol-driven): rozetės/jungiklio komutavimas, šviestuvai (montavimas + apdirbimas + skylės), pakabinami, LED juostos, difūzoriai (montavimas + apdirbimas)
- ✅ Pridėtiniai: Pastolių nuoma >3m, Šiukšlių išvežimas (m³), statybvietės sutvarkymas, apsauginės dangos

### Backend extractors
- ✅ `extractor/eksplikacija_reader.py` — pdfplumber + Vision fallback
- ✅ `extractor/pdfplumber_eksplikacija.py` — deterministic table parser su row bbox
- ✅ `extractor/material_specs.py` — on-demand designer specs ($0.20/click)
- ✅ `extractor/page_filter.py` — vendor catalog detection
- ✅ `extractor/cross_page_validator.py` — 9 sanity rules + Rangovas-empirical bounds
- ✅ `extractor/plyteliu_specifikacija.py` — pdfplumber tile size reader, $0
- ✅ `extractor/wall_elevation.py` — Vision per-page extractor (opt-in via `WALL_ELEVATION_EXTRACT=1` env)

### Frontend (claude.ai/design prototype mirror)
- ✅ Tokens swap (orange brick → construction blue #2a6fb5, warm paper #f6f5f2)
- ✅ Sidebar 56px icon-only LIGHT bg-1
- ✅ AppLayout simplified (no collapse toggle)
- ✅ StatsBar 3-card (drop fabricated metrics): Aktyvūs · Su PVM · Vid. apdorojimo laikas
- ✅ ProjectCard prototype style — 3-col grid, hover translate-y, status pill, 26px gross sum
- ✅ ProjectTopBar 52px header — back arrow + name + Be PVM/Su PVM + Prielaidos + Eksportuoti
- ✅ Tabs sutraukti į 3: Brėžinys · Kiekiai · AI Chat
- ✅ WorkspacePanel rewrite — filter + Patalpos (drėgna pill) + Kiekiai (collapsible per skyrius) + inline price edit
- ✅ Source dots default OFF (toggle eye on demand)
- ✅ PdfViewer drag-pan + Ctrl+wheel zoom; SymbolCounter popup pašalintas
- ✅ Plytelių specifikacija section UI'uje (kai `_plyteliu_specs` yra)
- ✅ Cookie banner subtler (single bottom strip, ne modal)
- ✅ Direct-URL `/project/<id>` fallback fix (pullProjectsFromBackend)

### Sprint F (PDF viewer polish)
- ✅ F1 Thumbnail virtualization (1 Document instance + IntersectionObserver)
- ✅ F2 Default page = first floor_plan (auto-navigate)
- ✅ F3 Room → PDF jump bidirectional
- ✅ F4 Eksplikacija row highlight (pdfplumber bbox + Konva-free div overlay)
- ✅ F5 Loading skeleton + toolbar polish

### Performance
- ✅ Lazy routes (React.lazy + Suspense) — main bundle 1.5MB → 304KB
- ✅ Code split: `pdf-viewer` 382KB, `canvas` 300KB, `ProjectDetail` 244KB chunks
- ✅ WorkspacePanel React.memo + useCallback (no cascade re-renders)

### Tests & quality
- 74/74 backend pytest pass
- Vite build green
- Determinism: 3× same input → byte-identical output
- Edge cases tested: empty patalpos, 50-room project, garazas, high ceiling

---

## 🟡 LIKUSIOS UŽDUOTYS (priority order)

### 1. PRODUCTION HARDENING (paliekam paskutinį — po Sprint G + §2 Accuracy)
- 🔒 Auth re-enable + email verification + password reset (1-2 d.)
- 🔒 Monitoring (Sentry/posthog) (0.5 d.)
- 🔒 Rate limiting on `/extract-interior` (2 val.)

### 2. ACCURACY EXPANSION

#### 2A. Research-driven fix'ai (2026-04-28 research, ranked by impact)
- 🟢 **NRM2 tiered opening rule (3 m² slenkstis)** — ✅ DONE 2026-04-28: helpers `_opening_should_deduct`, `_opening_adds_reveal`, `_resolve_deduction_standard`; `paint_deduction_standard` user pref propagated via `_paint_deduction_standard` meta key; reveal logic in `vision_call.py::_build_pozicijos_from_rooms` gates by standard; LT default = backward compatible. **18 nauji testai** `test_nrm2_opening_deduction.py`. **TODO:** frontend Setup Wizard / Prielaidos panel toggle (LT/NRM2/VOB radio) (~0.25 d.).
- 🔴 **Polygon-based tile zones** — replace `tiled_wall_length × tile_height` (CLAUDE.md §1.7) → polygon area iš išklotinės elevation. Add niche internals (1.5–3 m²/niša šiandien PRARASTI) + Schlüter trim line items. Unifikuoti su §2B wall_elevation merge task'u. Files: `extractor/wall_elevation.py`, `extractor/universal_rules.py`. Reference: [research §A2](superpowers/research/2026-04-28-takeoff-standards-and-pdf-ux.md#a2). (1.5–2 d.)
- 🟢 **Sloped ceiling + stairwell modules** — ✅ DONE 2026-04-28: helpers `slope_factor(angle_deg)`, `stairwell_wall_area_m2(perim, max_h, n_steps, run, rise)`. `ceiling_geometry` parameter (flat/sloped/vaulted/coffered) + `coffered_factor` override. Stairwell: `paskirtis="laiptine"` arba `room_type="stairwell"` triggers stair triangle subtraction. Pridėtas `laiptine` į ROOM_TYPE_RULES + `normalize_paskirtis` recognition. **21 naujas testas** `test_sloped_stairwell.py`. **TODO:** Vision prompt update kad pildytų `ceiling_geometry` + `slope_angle_deg` automatiškai; frontend RulesOverridePanel UI šiems parametrams (~0.5 d.).
- 🟢 **Q4 thickness fix (3–5 mm) + šlifavimo labor** — ✅ FULL DONE 2026-04-28: Phase 1 (constants + CLAUDE.md §1.11). **Phase 2:** Q4-conditional šlifavimas line item su `darbo_norma_h_m2: 0.30` + `_q_lygis: "Q4"` tag + description suffix „Q4 (80–120 grit, 100% paviršius)". **5 nauji testai** `test_q4_sanding.py`.
- 🟢 **Paint class (1/2/3) parameter** — ✅ DONE 2026-04-28: `_PAINT_CLASS_PROFILES` table (Class 1/2/3) drives coats × coverage × absorption_factor. Helper `_resolve_paint_class()`, propagated via `_paint_class` meta key. `_calc_dazai_liters` accepts `paint_class` param (priority over legacy coats). Class 2 = backward-compatible default. **20 nauji testai** `test_paint_class.py`. **TODO:** frontend RulesOverridePanel paint class radio (~0.25 d.).
- 🟢 **CLAUDE.md §8 — 4 nauji common mistakes** — Phase 1 ✅ DONE 2026-04-28: items #11–14 pridėti į CLAUDE.md §8 + research source nuoroda. Phase 2 LIKO: surface as UI warnings (frontend banner / tooltip kai aptikti susiję pozicijos). (0.25 d.)

#### 2B. Esami planai (priority adjusted)
- 🟡 **Wall elevation extractor real-world test** — modulis padarytas (`extractor/wall_elevation.py`), bet niekad neleistas su realiu projektu. Reikia: paleisti su `WALL_ELEVATION_EXTRACT=1` ant P1 ir P3, palyginti tile_zones precision vs paskirtis-based default. Cost ~$1-3/projektui. **Atlikti DRAUGE su 2A polygon tile task'u — abu naudoja tą patį `_wall_elevations` data flow.** (0.5 d. + ~$5)
- 🟡 **Wall elevation → pozicijos override** — kai `_wall_elevations` turi tile_zones su mm precision, override `plyteles_sienos_m2` paskirtis-based aproksimacijos. Reikia merge logic + tests. **Sutampa su 2A polygon tile task'u — vykdyti kaip vieną.** (1 d.)
- 🟡 **Real Rangovas benchmark per visus 5 projektus** — paleisti `/extract-interior` ant P1+P3 (kuriuose veikia text layer), lyginti row-by-row su parsed_pasiulymai.json. Tracking matrix per skyrius (coverage %, EUR drift). **Po 2A fix'ų — tada matuojam improvement.** (0.5 d. + ~$10)
- 🟡 **Multi-floor support** — `aukstu_skaicius` veikia kaip multiplier, bet Vision sumaišo 1 vs 2 vs 3 aukštus. Pridėti per-room `aukstas` field, expose į Setup Wizard, validate cross-page (room nrs starting with 2F vs 1F should split). (0.5 d.)

### 2.5. SPRINT G — PDF INTERACTIVE LEAP-UP (NAUJA, 2026-04-28 research)

> Tikslas: parity su Togal.AI/Bluebeam/Kreo + leap-frog per 🟢 eksplikacija lock badge.
> Architektūros pamatas: react-pdf + PDF.js layered model (canvas → text-layer → annotation-layer); Konva tik editing'ui (static overlays → SVG annotation-layer); rbush hit-testing'ui; pdfplumber line segments snap-to-edge'ui.
> Reference: [research §B1–B6](superpowers/research/2026-04-28-takeoff-standards-and-pdf-ux.md)

#### Aukštas prioritetas (KILLER + DIFFERENTIATOR)
- 🔴 **G1. Editable AI polygons** — cut/merge/split + drag-vertex handles + mid-edge phantom handles + C/M/S/Esc hotkeys. Real-time area recalc per `interiorCalc.js` (Shoelace formula). Files: `frontend/src/components/project/PdfViewer.jsx`, naujas `PolygonEditor.jsx`. Šiandien turime Konva canvas, bet ne editing logiką. **Be šito kiekvienas blogas AI poligonas verčia re-extract.** (3–5 d.)
- 🟢 **G2. Confidence Review Queue + 🟢 eksplikacija lock badge** — Phase 1 ✅ DONE 2026-04-28: naujas `ReviewQueueSidebar.jsx` mount'intas WorkspacePanel'yje. PERŽIŪRA collapsible section + „🛡️ N patvirt." chip header'yje (DIFFERENTIATOR), empty state „Visi duomenys patvirtinti", confidence-sorted list (low first), click → onJumpToPage. Live verified Playwright + screenshot @ test project (16 patvirt. badge rodo). Phase 2 LIKO: zoom-pan-flash polish 600ms ease + 1.5s flash (sutampa su G6); inline ✓/✏️/✕ accept/edit/reject su `_review_status` data field (~0.5–1 d.).

#### Vidutinis prioritetas (PARITY)
- 🟡 **G3. Symbol/pattern search** — „find all door symbols" / outlets / langai. Vision once per project to catalog symbols → OpenCV template-match (`cv2.matchTemplate`) cheap re-runs. Highlight matches across all pages + count badge. Backend: naujas `extractor/symbol_search.py`. Frontend: search panel + visual highlight. Togal/Bluebeam/Kreo visi turi. (3–4 d.)
- 🟡 **G4. Drawing comparison (revision diff)** — auto-align dviejų PDFs phase correlation on rasterized thumbnails → canvas color-diff: blue=added, red=removed, grey=unchanged. Kritiška LT renovacijai (DGM/SP keičiasi nuolat). Backend: naujas `extractor/drawing_diff.py`. Frontend: Compare tab + overlay. (4–6 d.)
- 🟡 **G5. Snap-to-edge + scale auto-detect** — (a) regex scan text-layer for `1:50 / 1:100 / M 1:50` → pre-fill `ScaleCalibrationModal`, (b) precompute pdfplumber line segments per page → rbush + kdbush → snap cursor while drawing/measuring. Files: `extractor/pdfplumber_eksplikacija.py` (extend with line segments), `PdfViewer.jsx` (snap logic). (2–3 d.)

#### Žemas prioritetas (POLISH, low effort × meaningful felt-quality)
- 🟢 **G6. Three-way sync polish** — ✅ Phase 1 DONE 2026-04-28: naujas `FocusFlashOverlay.jsx` komponentas (3-pulse outer glow ant room.bbox_pct, 1.8s ease-out animation + auto-cleanup). Mount'inta `PdfViewer.jsx` šalia EksplikacijaRowOverlay. Plus `.row-hover-halo` CSS klasė pritaikyta WorkspacePanel + ReviewQueueSidebar room rows (4px primary outline + faint background on hover). Vite build clean, Playwright smoke pass. **TODO Phase 2:** programmatic zoom-pan auto-scroll į bbox center (sudėtinga su react-pdf scaling, ~0.5 d.).
- 🟢 **G7. Industry keyboard shortcuts** — ✅ DONE 2026-04-28: `+/=` zoom in, `-/_` zoom out, `0` reset 100%, `F/f` fit to 120%, `[` prev page, `]` next page, `Esc` reset to select tool. Skip when typing in inputs. Live verified via Playwright (120% → 140% → 120% → 100% → 120% → page nav). Files: `PdfViewer.jsx:1079-1124` (new useEffect with input-typing guard).
- 🟢 **G8. Layer toggle** — vietoj „source dots eye" generic toggle'o, atskiri layers: Rooms / Dimensions / Symbols / Source dots. Files: `PdfViewer.jsx` toolbar. (0.5 d.)

#### Architektūros refactor (perform DRAUGE su G1)
- 🟢 **G9. Move static overlays Konva → SVG annotation-layer** — room outlines, source dots, eksplikacija highlights → plain SVG div (PDF.js annotation-layer). Konva pasilieka tik editing'ui (G1). Performance gain ant ≥500 polygon multi-floor projektų. Add rbush spatial index hit-testing'ui. Files: `PdfViewer.jsx`, naujas `lib/pdfOverlay.js`. (1–1.5 d.)

---

### 3. UX POLISH
- 🟡 **F2/F3 export forma** — LT statybos standartas (Atliktų darbų aktas + Pažyma apie atliktų darbų vertę). Reikia template + dates + parties + signature section. Excel + PDF. (1-2 d.)
- 🟡 **Mobile responsive restore** — AppLayout simplified lost mobile drawer. 56px sidebar collapses to hamburger on <768px. PdfViewer + WorkspacePanel stack vertically. (0.5 d.)
- 🟡 **Setup Wizard pilnumas** — `SetupWizard.jsx` egzistuoja bet ~50% pilnas. Pridėti glaistymo lygį (Q1-Q4), sienų storį, plytelių aukštį per paskirtis defaultus, dažymo sluoksnių skaičių. (0.5 d.)
- 🟡 **AI Chat — quick reply suggestions** — egzistuoja bet sample klausimai senstantys. Atnaujinti ant naujo schema (room counts, plytelių specs etc.). (1 val.)
- 🟡 **Frontend rendering of `_wall_elevations`** — ne tik backend captures, bet UI rodo (per-room expand su tile_zones). (0.5 d.)

### 4. ENGINEERING QUALITY
- 🟢 **Dead code sweep** (DAR LIKO):
  - `frontend/src/components/project/ProjectCanvas.jsx` (`?canvas=1` flag — eksperimentinis, niekada nešipo)
  - `frontend/src/components/project/SymbolCounter.jsx` (visas failas — popup'as pašalintas, modulis ne)
  - V8 legacy paths (`v8_pages`, `v8_rooms` aliases — sumažinti tarpinę layer)
  - Old `ProjectMainView.jsx` blocks (kiekiai legacy table view — ar reikia?)
  (2 val.)
- 🟢 **Backup/restore localStorage** projektų — user'iai praras viską jei brauserio istoriją valys. Add export/import JSON button to Settings page. (0.5 d.)
- 🟢 **Error tracking on Vision failures** — šiandien spausdina `console.error`, neraportuoja. Wire to Sentry / similar. Pre-req: Sentry account (laikoma su auth re-enable). (1 val.)

### 5. RESEARCH (paliekamas niekam neperkeliant Rangovo/Sistelos referencų)
- ✅ ~~**LT samata best practices iš STR + NRM2**~~ — DONE 2026-04-28: [`docs/superpowers/research/2026-04-28-takeoff-standards-and-pdf-ux.md`](superpowers/research/2026-04-28-takeoff-standards-and-pdf-ux.md) part A (NRM2 3m² rule, DIN 18363, Q4 Merkblatt 2, Tikkurila/Caparol coverage rates, polygon tile measurement, sloped/stairwell formulas). 5 actionable additions feed'inami į §2A.
- ✅ ~~**Competitor pattern analysis**~~ — DONE 2026-04-28: same file part B (Togal.AI 2025 features, Bluebeam Dynamic Fill, Kreo Auto Measure 2.0, STACK Assist, OST, eTakeoff, full feature matrix). 9 actionable additions feed'inami į Sprint G.
- 🟡 **Sienų išklotinių kokybės varieties** — kiek LT projektų realiai turi išklotines su mm precision vs schematinius brėžinius? Šitai pagrindas wall_elevation extractor decision'ams. **Vykdyti DRAUGE su §2A polygon tile zones implementation** — bus matavimo duomenys. (0.25 d.)
- 📊 **Sąmata123 / ASA.LT / Sistela licensing inquiry** — gauti LT labor norms (jei legaliai prieinama). Research'as parodė kad nėra public LT NRM2 atitikmens, bet komercinės DB egzistuoja. (0.5 d. + komunikacija)

### 6. CONSTRUCTION TYPES (atidėti — ne dabar)
- ⏸ Fasadų darbai (ETICS, ventiliuojami)
- ⏸ Stogai (slope_factor, latai, danga)
- ⏸ Žemės darbai (kasiniai, swell faktoriai)
- ⏸ Betonavimas (armatūra, klojiniai)
- ⏸ Daugiabučių modernizavimas (reverse PVM, APVA forma)

---

## 🗂 PROJEKTO STRUKTŪRA (key files)

### Backend (`/Users/ignasgaldikas/samatu-ai/backend/`)
```
extractor/
├── prompt.py                    — Vision schema + system prompt
├── vision_call.py               — extract_interior + pozicijų generator
├── eksplikacija_reader.py       — pdfplumber + Vision fallback
├── pdfplumber_eksplikacija.py   — deterministic eksplikacija + bbox
├── plyteliu_specifikacija.py    — tile sizes, $0
├── wall_elevation.py            — per-page Vision (opt-in)
├── cross_page_validator.py      — sanity rules
├── material_specs.py            — on-demand designer specs
├── page_filter.py               — vendor catalog skip
├── universal_rules.py           — calc_room_quantities (deterministic math)
└── lt_rules.py                  — LT STR sanity warnings

main.py                          — FastAPI endpoints
auth.py                          — auth (currently disabled via env)
db.py                            — sqlite + project CRUD
tests/
├── test_deterministic.py        — 35 tests
├── test_extractor_unit.py       — 12 tests
├── test_cross_page_validator.py — 12 tests
├── test_plyteliu_specifikacija.py — 10 tests
└── test_wall_elevation.py       — 6 tests
```

### Frontend (`/Users/ignasgaldikas/samatu-ai/frontend/src/`)
```
pages/
├── Dashboard.jsx                — projektų sąrašas
├── ProjectDetail.jsx            — wrapper su delete + lazy InteriorProject
├── InteriorProject.jsx          — main interior page (ProjectTopBar + tabs)
├── NewProject.jsx               — upload flow
├── Settings.jsx                 — settings
├── PriceLists.jsx               — kainynai
├── AdminDashboard.jsx           — admin
├── Login.jsx, Register.jsx, Privacy.jsx, Terms.jsx
└── SharedProject.jsx            — read-only share view

components/
├── layout/
│   ├── Sidebar.jsx              — 56px icon-only LIGHT
│   └── AppLayout.jsx            — simple wrapper
├── dashboard/
│   ├── StatsBar.jsx             — 3-card grid
│   ├── ProjectCard.jsx          — vertical card su 26px gross
│   └── EmptyState.jsx
└── project/
    ├── PdfViewer.jsx            — react-pdf + Konva + drag-pan + zoom
    ├── WorkspacePanel.jsx       — filter + Patalpos + Kiekiai sections
    ├── ProjectMainView.jsx      — Kiekiai tab table view
    ├── InteriorWorkspace.jsx    — PDF + WorkspacePanel split
    ├── AiChat.jsx               — chat tab
    ├── RulesOverridePanel.jsx   — Prielaidos
    └── (others)

lib/
├── projectStore.js              — localStorage + backend sync + skyrius migration
├── authContext.jsx
├── pdfStore.js                  — IndexedDB PDFs
├── interiorCalc.js              — frontend recalc engine
└── (others)

index.css                        — design tokens + utility classes
```

### Test data
```
training-data/
├── parsed_pasiulymai.json       — 5 Rangovas pasiulymai parsed (242 line items)
├── gap_analysis.md              — early gap analysis (V8 column outdated)
└── projektas_{1-5}/             — original PDFs
```

---

## 🔧 DAŽNAI NAUDOJAMOS KOMANDOS

```bash
# Backend (pip + uvicorn)
cd /Users/ignasgaldikas/samatu-ai/backend
SAMATU_AUTH_DISABLED=1 /Users/ignasgaldikas/samatu-ai/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Backend tests (74 testai)
/Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/ -v

# Frontend dev (vite HMR)
cd /Users/ignasgaldikas/samatu-ai/frontend
npm run dev   # arba: npx vite

# Frontend build
npx --no-install vite build

# Wall elevation extractor (opt-in)
WALL_ELEVATION_EXTRACT=1 SAMATU_AUTH_DISABLED=1 \
  /Users/ignasgaldikas/samatu-ai/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Find existing chrome process
pgrep -f "Google Chrome"

# Project URL (existing test project)
http://localhost:5173/project/04bc3f42-4e9e-49e5-ba6a-fc127b41cc0b
```

---

## 📝 VARTOTOJO PREFERENCIJOS (svarbu)

- ❌ **NEnaudoti Rangovo (kontraktoriaus) kaip pasirinktiną kainynų preset** — jis tiesiog vienas rangovas, ne ground truth
- ❌ **NEintegruoti Sistela** — galima būti intellectual property concerns
- ❌ **NErašyti tech kalbos UI'uje** ("python deterministic", "Vision", "_zoom_changes" — visada slėpti arba versti į LT)
- ✅ **UI tekstas LT'iškas su tinkamais simboliais** (ąčęėįšųūž)
- ✅ **Tikslumas + stabilumas + UI no-lag** = primary
- ✅ **Construction types** (fasadai, stogai) — atidedami, dabar nėra duomenų
- ✅ **Auth re-enable** = paskutinis žingsnis prieš shipping

---

## 🚀 NEXT-SESSION ON-RAMP

Kai pradedi naują sesiją (claude code arba subagent):

1. **Pirma perskaityk šitą failą + `docs/superpowers/research/2026-04-28-accuracy-priorities.md`**
2. Patikrink backend status: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/auth/me` (turi būti 200)
3. Patikrink frontend status: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/`
4. Paleisk testus: `cd /Users/ignasgaldikas/samatu-ai/backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/ 2>&1 | tail -3` (turi būti 74/74)
5. Pasižiūrėk git status: `cd /Users/ignasgaldikas/samatu-ai && git status --short`
6. Atrenk task'ą iš „LIKUSIOS UŽDUOTYS" sekcijos pagal priority
7. Sequential — pirma audit'ink kas jau yra, tada modifikuok, tada testuok

### Servers status (paleidimo komandos)

```bash
# Backend (be auth dev'ams)
cd /Users/ignasgaldikas/samatu-ai/backend
SAMATU_AUTH_DISABLED=1 nohup /Users/ignasgaldikas/samatu-ai/venv/bin/uvicorn main:app \
  --host 0.0.0.0 --port 8000 >/tmp/backend.log 2>&1 &

# Frontend (Vite HMR)
cd /Users/ignasgaldikas/samatu-ai/frontend
nohup npm run dev >/tmp/frontend.log 2>&1 &
```

### Esami testavimo projektai

- localStorage UUID: `04bc3f42-4e9e-49e5-ba6a-fc127b41cc0b` (Interjero projektas, 20 patalpų, 56 pozicijos)
- Test PDFs: `backend/test_pdfs/` (03_SA.pdf, vidaus_apdaila.pdf, SA-02.pdf, etc.)
- Rangovas reference: `training-data/parsed_pasiulymai.json` (5 projektai)

### Pažangos rodikliai (track these)

| Metric | Šiandien | Target |
|---|---|---|
| Backend pytest | 74/74 | maintain |
| Frontend bundle (main) | 304 KB | < 350 KB |
| Rangovas P1 coverage | ~57% (65/113 pozicijų) | > 80% |
| Rangovas P5 coverage | ~70% (35/50) | > 85% |
| Per-projekto cost | ~$3.20 (auto) | maintain |
| Determinism CV | byte-identical | maintain |

