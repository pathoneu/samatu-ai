# Contractor Feature Batch — 2026-09-02 Implementation Plan

> **For agentic workers:** execute task-by-task; every task ends with the full gate suite
> (see "Global gates"). Founder decisions below are LOCKED — do not re-litigate them.

**Goal:** Five features from the contractor's 2026-09-01 feedback call: per-room
įtempiamos lubos, a separate Medžiagos section, sienų/lubų paint split with the
eksplikacija-total ceiling anchor, add-row-into-any-section, and kainynas xlsx
upload with auto price fill. (The sixth ask — "parodyti kaip skaičiuota" — is in a
separate design-research arc, doc: `docs/superpowers/research/2026-09-02-calc-transparency-options.md`.)

**Locked founder decisions (2026-09-02):**
1. Įtempiamos lubos = **per-room toggle in Prielaidos** that REMOVES that room's
   ceiling skim/prime/paint/sand quantities. No new "įtempiamų lubų montavimas"
   position is auto-added (user can add one manually via add-row).
2. Lubų glaistymas/gruntavimas/dažymas quantity = **eksplikacijos "Iš viso" total
   − rooms whose ceilings aren't painted** (stretch-ceiling rooms), deduction shown
   transparently, e.g. `165,61 − 24,30 (įtempiamos lubos) = 141,31 m²`.
3. Materials go to **one global "Medžiagos" section** at the end of the list; work
   sections keep only labor. Each material row shows which work it belongs to.
4. Kainynas: **auto-apply from the default price list + a manual button**; a price
   fills when the row is "tokia pati arba panaši" (same or similar); never
   overwrite a user-entered price; unit mismatch never fills.

**Architecture notes (recon 2026-09-02, verified in code):**
- Positions builder: `backend/extractor/vision_call.py` — `SK_GD = "Sienų lubų
  glaistymas dažymas"` (~line 1591, 1972), ceiling rows ~2060–2080, virš/iki-3m
  split block ~1566–1690 (garažas paints ceiling only, per comment at 1648).
  `_SKYRIUS_ENUM` ~622, `SKYRIUS_LEGACY_MIGRATION` ~641, `normalize_skyrius` ~668.
- Per-room finishing override precedent: `walls_paint_override` in
  `frontend/src/components/project/AssumptionsPanel.jsx:329-341` →
  `handleRecompute('walls_paint_override', …)` → `backend/api/recompute_quantities.py`.
  Clone this wiring for ceilings.
- Eksplikacija totals: `backend/extractor/pdfplumber_eksplikacija.py` —
  `_is_total_row` (~289) DETECTS "Iš viso"/"Bendras plotas" rows and currently
  discards them. Header column map exists (HEADER_TOKENS).
- Add-row: `frontend/src/components/project/ProjectMainView.jsx:568-580`
  hard-codes `skyrius: t('project.mainView.otherWorks')`.
- Price lists: `frontend/src/pages/PriceLists.jsx` (CSV import only, Sprint §30),
  storage localStorage-only (`samatu_price_lists`, projectStore.js:754+), routed at
  `/price-lists`, in sidebar — but NOTHING applies a list to a project today.
- Merge invariants: `frontend/src/lib/mergeDarbuSarasas.js` (pass 2 matches by
  `normLabel` on aprasymas — skyrius is NOT part of the match key, so section
  renames don't orphan prices; pass 3 carries every unmatched prior row).
  Backend twin: `api/recompute_quantities._merge_user_edits`.

**Global gates (every task, before its commit is considered done):**
- `cd backend && venv/bin/python -m pytest -q` → baseline 2683 passed / 3 skipped
  (+ your new tests). 56 pre-existing failures live in a SEPARATE runner config —
  see docs/DEVELOPING.md; do not misattribute them.
- `cd frontend && npm test -- --run` → baseline 429 passing (+ new).
- Eval (only tasks marked [EVAL]): `venv/bin/python eval_harness.py --totals-only
  --recompute` — corpus mean MAE must stay ≤ 7.82%; per-project berzas ≤ 3.10
  unless the ceiling anchor moves it DOWN. NEVER quote a number without --recompute.
- Reason strings on any new/changed row must pass
  `backend/tests/test_confidence_reasons_are_for_the_user.py` (guide, don't
  confess: no client names, no benchmark counts, no pipeline jargon).
- UI text Lithuanian (lt.json + en.json both updated); currency EUR; confidence
  dot on every new quantity row.
- Commit per task on branch `viewer-rebuild`. NO git push (director pushes after
  the batch; production deploys from main).

---

## Task 1 — Add row into any section (F4) [frontend]

**Files:** `frontend/src/components/project/ProjectMainView.jsx`,
`frontend/src/i18n/lt.json`, `frontend/src/i18n/en.json`.

- Each skyrius group header gets a small ghost "+" button ("Pridėti eilutę į šį
  skyrių") → inserts a new row with `skyrius` = that section's name, appended as
  the LAST row of that section (i.e. inserted into `darbai` right after the
  section's current last row, not at array end), then eil_nr renumbered the same
  way existing code does (see renumber guard used by exports).
- The existing global "Pridėti eilutę" button stays and keeps its `Kiti darbai`
  default (it is the only way to create a brand-new section).
- New rows keep the existing new-row shape (aprasymas = t('project.mainView.newRow'),
  kiekis 0, kaina 0, mato_vnt 'm²').
- Verify (existing behavior, add a test if missing): manually added rows survive
  recompute via mergeDarbuSarasas pass 3 carry.

**Tests:** component-level or lib-level test that the insert lands inside the
right section and renumbering is stable.

## Task 2 — Įtempiamos lubos per room (F1) [full-stack] [EVAL]

**Files:** `frontend/src/components/project/AssumptionsPanel.jsx`,
`frontend/src/lib/recomputeApi.js` (only if it whitelists keys),
`backend/api/recompute_quantities.py`, `backend/extractor/vision_call.py`
(pozicijos builder + `_recompute_per_room_via_python` path),
`backend/extractor/universal_rules.py` (only if ceiling quantities originate
there), i18n files, backend tests.

- Assumptions key: `stretch_ceiling_override: { [roomNr]: 0|1 }` (1 = įtempiamos).
  Default absent → dažomos. Persisted inside the project's assumptions blob the
  same way `walls_paint_override` is.
- Panel UI: clone the "Sienų apdaila per kambarį" toggle grid (lines ~570-610)
  into a "Lubų apdaila per kambarį" block directly below it. Button states:
  "Dažomos" / "Įtempiamos". Same live-recompute call pattern.
- Backend recompute: rooms flagged stretch get NO lubų glaistymas / gruntavimas /
  dažymas / šlifavimas contribution (both the iki-3m and virš-3m tiers). Do NOT
  touch: lubų karnizas, LED nišos, GKP lubos, grindjuostės — the founder scoped
  this to "isimti lubu dazyma" only.
- Deducted rooms feed Task 3's anchor math (see there); if Task 3 isn't merged
  yet, per-room summation simply skips stretch rooms — write the code so both
  compositions work.
- Sanity check (Section 6 CLAUDE.md style): if ALL rooms are stretch, ceiling
  paint rows disappear entirely — assert no zero-quantity ghost rows remain.
- Confidence/reason on affected rows unchanged (quantity source is still the
  same); the DEDUCTION must be visible in the row's provenance string (see Task 3).

**Tests:** backend — recompute with override on 2 of N rooms drops exactly those
rooms' ceiling contributions and leaves walls untouched; frontend — toggle fires
recompute with the right payload; merge — a priced lubų row keeps its price when
quantity shrinks.

## Task 3 — Sienų/lubų split + eksplikacija ceiling anchor (F3) [backend-heavy] [EVAL]

**Files:** `backend/extractor/pdfplumber_eksplikacija.py`,
`backend/extractor/vision_call.py`, `backend/extractor/eksplikacija_guard.py`
(read-only — anchor must come from the guard-ACCEPTED table),
`frontend/src/components/project/*` (grouping/order), export code
(`backend/*export*`, ExportDropdown/ExportFilterModal), i18n, tests.

**Part A — capture the total.**
- In `pdfplumber_eksplikacija`, when `_is_total_row` fires on the accepted table,
  parse the plotas-column cell (header-mapped; merged-cell None positions
  preserved — do not regress dd57e93) into `_meta.total_area_m2` +
  `_meta.total_row_label` + page. Do NOT add total rows to rooms (unchanged).
- Multiple total rows (per-floor + building): pick the one closest to
  Σ(accepted room plotai); record all candidates in `_meta` for debugging.
- The anchor is only trusted when the guard verdict accepted that table
  (foreign-eksplikacija reject ⇒ no anchor). Vision-lane extractions without a
  pdfplumber table get NO anchor (fallback = per-room sum, current behavior).

**Part B — anchor the ceiling rows.**
- In the pozicijos builder: when `total_area_m2` exists and is sane
  (within ±30% of Σ room plotai — else ignore + LT warning), ceiling
  glaistymas/gruntavimas/dažymas base quantity = `total_area_m2 −
  Σ(stretch rooms' plotas) − Σ(rooms already excluded from ceiling finishing)`.
  Garažas stays IN (it paints ceiling only, existing rule ~1648).
- The virš/iki-3m tier split must keep working: the split DISTRIBUTES the
  anchored base; study lines 1566–1690 first and preserve the berzas
  calibration (its truth 165.61 == the Beržų table total, so expect neutral or
  better). [EVAL] gate is hard here.
- Row provenance (user-visible, Lithuanian, guide-not-confess): e.g.
  `Iš eksplikacijos lentelės „Iš viso": 165,61 − 24,30 (įtempiamos lubos) = 141,31 m²`.
  When anchor is absent: current wording stays.

**Part C — section split.**
- `SK_GD` becomes TWO sections: `"Sienų glaistymas dažymas"` and
  `"Lubų glaistymas dažymas"`. Assignment: rows whose aprasymas starts with
  "Lubų" (incl. karnizo rows and LED nišų glaistymas/dažymas) → Lubų section;
  everything else currently in SK_GD (Sienų*, Angokraščių, Dažymo kampų,
  Grindjuosčių, Durų angų, dekoravimas) → Sienų section. Sienų section
  ordered before Lubų everywhere (UI grouping, Excel/PDF exports, F2).
- Migration: REMOVE the legacy map entry `"Sienų glaistymas dažymas" → merged`
  (it now maps a valid name away). Add row-level migration where legacy
  migration runs today (`_emit_v8_compat_fields` server-side + the frontend
  load-path twin — grep for SKYRIUS_LEGACY_MIGRATION usages): a row with the
  old merged skyrius is reassigned by the same aprasymas rule. Old blobs must
  load with prices intact (normLabel matching is skyrius-agnostic — verify with
  a fixture test on a real saved blob shape).
- `_SKYRIUS_ENUM`: map BOTH new names to the existing `"paint"` enum value
  (downstream consumers keep working); keep the old merged key mapping too.

**Tests:** total-row capture (incl. multi-total pick + insane-total rejection);
anchored quantity math with/without stretch rooms; migration fixture (old blob →
split sections, prices kept); export section ordering; eval per-project deltas
reported in the task summary (berzas/objektas_b/ciurliu/lazunu before vs after).

## Task 4 — Medžiagos section (F2) [backend + UI] [EVAL: neutral expected]

**Files:** `backend/extractor/vision_call.py`, frontend grouping components
(ProjectMainView/PositionsPanel/WorkspacePanel group order), exports, i18n, tests.

- New skyrius `"Medžiagos"`, enum value `"materials"`, ordered LAST among
  auto-built sections (before nothing — after Pridėtiniai elementai).
- ENUMERATE first (in-code audit, list in task summary): every material the
  builder computes today — embedded `medziagos_aprasymas` fields (~899, 2042,
  2080, 2628), standalone material lines (Glaistas/Dažai ~1637-41), glaistas kg
  q-level calc (~1330), dažai litres (~1335), gruntas, GKP lapai, varžtai,
  hidro mišinys + juosta. Emit each as its OWN row in Medžiagos with quantity +
  unit (l / kg / vnt / m) and a `susijes_darbas` field naming the parent work
  section; UI renders it as muted subtext under the aprasymas.
- Work rows STOP embedding `medziagos_aprasymas` for newly built lists (field
  stays readable for old blobs; UI keeps rendering it wherever it does today so
  old projects don't lose information).
- Do NOT fabricate quantities: emit only materials the engine already computes.
  Anything with no computed quantity keeps out (no 0-qty placeholder rows).
- Merge behavior on old projects (INVARIANTS, test them): no priced row is
  deleted, no price silently moves; a rebuilt old project gains unpriced
  Medžiagos rows while old priced combined rows are carried (pass 3) — this
  visible duplication is ACCEPTED for old projects (founder-visible change),
  fresh extractions are clean.
- Confidence: material rows inherit the parent work's confidence tier; reason
  strings pass the guard test.
- Eval: quantities must be bit-identical (structure-only change) — verify.

**Tests:** builder emits the enumerated set; parent-link present; exports render
the section; guard test passes; merge invariants.

## Task 5 — Kainynas xlsx + auto price fill (F6) [full-stack, worktree-parallel]

**Files:** `frontend/src/pages/PriceLists.jsx`, `frontend/src/lib/projectStore.js`,
new `frontend/src/lib/kainynasMatch.js`, project page toolbar component,
`backend/main.py` or `backend/api/price_lists.py` (new), `backend/db.py`,
requirements (openpyxl — check if present), i18n, tests both sides.

**Part A — xlsx parsing (backend).**
- `POST /api/price-lists/parse-xlsx` (auth-gated, file upload ≤ 5 MB): openpyxl
  reads first sheet; header row detected within first 5 rows using the SAME
  header vocabulary as PriceLists.jsx `headerMap` (skyrius/kategorija,
  aprašymas/pavadinimas, vnt/matas/unit, kaina/kaina_eur/price; tolerate
  diacritics + case). Returns normalized `items[]` identical in shape to the CSV
  parser's output + `skipped_rows` count. LT decimal commas handled.
  Frontend: file input accepts .xlsx/.xls/.csv; xlsx goes through the endpoint,
  CSV keeps the existing client parser.

**Part B — backend persistence (write-through mirror).**
- New table `price_lists` (id TEXT pk, user_id, name, company_name, items JSON,
  is_default INTEGER, created_at, updated_at) in `backend/db.py` following the
  existing table/migration pattern; CRUD endpoints (list/upsert/delete) with the
  same owner-scoping discipline as projects (NULL-owner write barrier lesson).
- `projectStore.js` price-list functions become write-through (localStorage
  cache + backend source of truth), mirroring the projects pattern; backup
  import/export keeps working (v2 payload already carries price_lists).
- "Numatytasis" star toggle in PriceLists UI → `is_default` (one per user).

**Part C — matching + apply.**
- `kainynasMatch.js` (pure, heavily unit-tested): normalize using the EXISTING
  `normLabel`/`tierKey` from mergeDarbuSarasas (import, don't fork) + strip
  diacritics/punctuation, token-set similarity. Fill rules: exact normalized
  match → fill; similarity ≥ 0.65 AND unit matches (m²==m2 etc. — normalize
  units) → fill as "panaši" (flagged in preview); unit mismatch → NEVER fill;
  two candidates within 0.05 similarity → ambiguous, don't fill, list it.
  NEVER overwrite a non-empty/user-entered price (kaina > 0 or price-touched
  flag if one exists).
- Manual: "Užpildyti kainas iš kainyno" button in the project view (near
  export/prielaidos controls) → dialog: pick list (default preselected),
  preview (n exact / n similar / n unmatched with row names), Apply → toast
  summary; unmatched stay empty.
- Auto: when a NEW extraction's darbu_sarasas first lands (and only then — not
  on every recompute), if a default kainynas exists, run the same matcher on
  empty-priced rows, apply, and show the summary toast with an "Peržiūrėti"
  action opening the same preview dialog. Rows auto-filled get a provenance
  marker (e.g. `kaina_saltinis: 'kainynas'`) so the UI can show a subtle chip.

**Tests:** matcher table-driven cases (diacritics, Q-levels, sluoksniai, GKP
variants, unit mismatch, ambiguity, no-overwrite); xlsx endpoint parses a real
LT-style workbook fixture (build one in tests, no client data); auto-apply fires
once per extraction; write-through store round-trip.

---

## Sequencing

1. Task 1 — director, inline, first (small; commit before workers start).
2. Tasks 2+3 — ONE worker (they share the ceiling-row code paths), main tree.
3. Task 4 — next worker in main tree after 2+3 land (same builder file).
4. Task 5 — parallel worker in an isolated worktree (disjoint files; i18n
   conflicts resolved by director at merge).
5. Director: final review pass, full gates, eval numbers in summary, merge, push
   (safe_deploy_check first), browser-verify on prod per DEVELOPING.md.
