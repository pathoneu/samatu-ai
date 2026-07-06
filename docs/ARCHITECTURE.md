# Pathon — Architecture & Traps

The real data flow, a **"which file is canonical"** map so you don't edit a stale copy, and the known fragilities. Written 2026-07-06 (Fable 5 handoff). Pairs with [`DEVELOPING.md`](DEVELOPING.md).

## Data flow (the happy path)

1. Contractor uploads a construction PDF → `POST /extract-interior` (`backend/main.py`).
2. **`extract_interior`** (`backend/extractor/vision_call.py`) — Claude Vision reads the pages → rooms (`patalpos`) + per-room elements. Multi-pass: native-PDF pass-1 with **voting**, a **zoom** pass, and **readers** (`apdailos_reader`, `doors_reader`, `sanitary_fixture_reader`, `eksplikacija_reader`, `page_classifier`).
3. **`calc_room_quantities`** (`backend/extractor/universal_rules.py`) — the **canonical deterministic LT formula engine**. Per-room → paintable area, tiles, GKP, reveals, corners, etc. Formulas are specified in `CLAUDE.md §1`.
4. **`_build_pozicijos_from_rooms`** (`vision_call.py`) — aggregates rooms → `pozicijos` (line items) and applies **consolidation** (paint into iki/virš-3m tiers; LED-niche glaistymas+dažymas into one line), gated by feature flags.
5. **`_emit_v8_compat_fields`** → `darbu_sarasas` — the flat list the UI table **and** the exporters read.
6. Frontend renders; the user types **prices (`kaina`)** onto `darbu_sarasas` lines.

## Recompute flow (Prielaidos / assumption edits)

There are **two live recompute endpoints** for different edit surfaces — don't assume either is dead:
- **`POST /api/recompute-quantities`** (`backend/api/recompute_quantities.py`) — the **AssumptionsPanel** path. `AssumptionsPanel` edit → `frontend/src/lib/recomputeApi.js` → `_apply_assumption_edits` mutates rooms (ceiling height, `walls_paint_override`) → `_build_pozicijos_from_rooms` rebuild → `darbu_sarasas`.
- **`POST /recompute-interior`** (`backend/main.py`) — the **room/polygon-edit** path, via `handleRoomsChange` in `InteriorProject.jsx` (fires when the user edits a room primitive — plotas, perimetras, lubų aukštis, paskirtis — or on the `samatu:project-recompute` event). Rebuilds `darbu_sarasas` + santrauka deterministically from the edited rooms; no Vision call. (The old `RulesOverridePanel` also called this endpoint but was removed from the UI 2026-05-06 — the endpoint itself is live and reachable.)

Both run `calc_room_quantities` → `_build_pozicijos_from_rooms`. Frontend `onRecomputed` → **`mergeDarbuSarasasEdits`** re-attaches the user's prices to the rebuilt lines by label.

## Export flow

`ExportModal` builds `{projektas, eilutes, prielaidos, patalpos}` (maps `darbu_sarasas → eilutes`) → `POST /export/excel` | `/export/pdf` → `generate_excel` / `generate_pdf` (`main.py`). Excel uses **live formulas** (`=SUBTOTAL`, `=ROUND(...*0.21)`) so the contractor can edit quantities/prices in Excel and totals recompute.

## ⚠️ CANONICAL vs STALE — edit the RIGHT file

| Concern | CANONICAL (edit this) | STALE / DEAD (do NOT build on) |
|---|---|---|
| Accuracy formulas | `backend/extractor/universal_rules.py::calc_room_quantities` + `line_items.py` (spec: `CLAUDE.md §1`) | `frontend/src/lib/interiorCalc.js` (old FE copy of the math — backend is source of truth); legacy math paths in `main.py` |
| Live recompute | BOTH `backend/api/recompute_quantities.py` (AssumptionsPanel) and `/recompute-interior` in `main.py` (RulesOverridePanel) — different edit surfaces, both live | — |
| Line items shown/exported | `darbu_sarasas` (from `_emit_v8_compat_fields`) | — |
| Prices | user-entered on `darbu_sarasas`, carried by `mergeDarbuSarasasEdits` (`frontend/src/pages/InteriorProject.jsx`) | — |

Also: **gap-analysis docs go stale fast.** The `gap-analysis.md` under a fixture may predate an engine change — always confirm against the *current* code before trusting a "TODO" in it. (This exact trap wasted time: the 2026-05-27 gap doc listed an aggregation refactor as pending that had already shipped 2026-06-06.)

## Known fragilities / gotchas

- **Price-label matching.** Prices carry across a recompute by lowercased `aprasymas`. If a line's label changes on rebuild (paint flips iki↔virš-3m when a ceiling height crosses 3.0 m), the price can silently drop. Patched with a **normalized-key pass-2** on both FE (`mergeDarbuSarasasEdits`) and BE (`_merge_user_edits`). The *correct permanent fix* is **stable line IDs** (hash of room + line-type + base description) — a queued task.
- **Stale-static demo.** The sample project's numbers are **hand-authored** (they don't derive from its rooms), so any recompute shifts them. That's why the sample is now **locked read-only** (`AssumptionsPanel` gates on `rawData.is_demo`). Real projects don't have this.
- **Project persistence.** Projects sync backend ↔ localStorage; a project that exists **only** in localStorage is dropped on a backend pull. Moving to a durable per-user store is a queued task (also the audit's #1 architectural pilot risk).
- **Vite module cache.** In a long dev session, `seedDemoProject`'s dynamic `import('@/demoData')` can return a stale module — a fresh browser is fine.
- **No backend `--reload`** — see `DEVELOPING.md`.

## Accuracy reality (don't chase the detector)

The deterministic formulas are essentially **solved** — they match the contractor within ~1% on correct inputs. The accuracy ceiling is the **VLM detection layer** (counting difūzoriai / electrical / windows), an industry-wide ~0.40–0.55 exact-match limit that better models won't remove. So the leverage is in **fast correction UX + the ground-truth/corrections flywheel**, not in refactoring math. Never change billed formulas without measuring against the fixtures (see `DEVELOPING.md`).

## Security invariants (keep these true)

- Every project-scoped endpoint **requires auth** and **scopes the DB query by `user_id`** (read + write). `db.upsert_project` has an ownership barrier that blocks overwriting another user's — or a NULL-owner orphan — project.
- Vision runs **only after** auth (no unauthenticated budget-drain). Uploads capped at 200 MB.
- Excel/PDF export: sanitize **any user text written to a cell** with `_safe_cell()` (spreadsheet formula-injection). New cells that render `projektas` / room names / notes must use it.
- No `dangerouslySetInnerHTML` on user data (the only sink is an app-controlled chart-CSS helper). React auto-escapes everything else.
