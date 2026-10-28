# Narrow Pass-1 — v4 (2026-10-27)

Author: Opus 5.5 worker on branch `v4/pass1-narrow` (off `togal-v2` @ `59f691a0`).

## §0 Resume point

Gate run on 2026-10-28; see §10 for measured numbers.

- `backend/extractor/pass1_narrow.py` — the new module (flag, probe, prompt, schema, one-round
  + voter Vision call, merge, end-to-end extract).
- `backend/extractor/vision_call.py:extract_interior` — small fenced block near the top of the
  function dispatches to `pass1_narrow.extract_interior_narrow` when `SAMATU_PASS1_NARROW=1`.
  Flag unset ⇒ identical to today (one guarded `narrow_enabled()` check, no narrow import called).
- `backend/extractor/no_vision_route.py` — the two helpers Pass-1 narrow reuses
  (`eksplikacija_from_text_schema`, `rooms_from_table`) are now exposed as public aliases of the
  underscore-prefixed originals; no behaviour change.
- `backend/tests/test_pass1_narrow_2026_10_27.py` — 12 unit tests (flag off, env parsing, page
  selection by kind, both fall-open paths, prompt shape, schema shape, merge invariants, element
  enum guard, omitted-room handling).
- `scripts/pass1_narrow_gate.sh` — the gate script. Fixed on 2026-10-28 (see §10 defects).
- Suite (builder full run, 2026-10-27, under CPU contention): **5336 passed, 2 failed, 9 skipped
  in 6985 s (1:56 h)**. The two failures were timing assertions only —
  `test_geometry_gate[objektas_a]` (`out['seconds'] < 20` failed; objektas_a ran 1930 s,
  objektas_g 421 s) and `test_parallel_voting::test_parallel_actually_overlaps` (overlap < 0.5 s).
  Manager re-ran those two files plus the narrow and golden-replay tests on an idle CPU: 26 passed,
  2 failed in 1:01 h — the same two timing assertions failed again. The same test files on the
  main checkout earlier that day passed inside the 20 s limit, so the failures reflect machine
  load or the worktree's missing gitignored caches, not the branch. The final verdict is the
  manager's full suite on the merged head in the main checkout, recorded in the merge log.

Flag:

    SAMATU_PASS1_NARROW=1              # enable
    SAMATU_PASS1_NARROW_VOTES=3        # bring back the voter (default 1)

How the gate ran (2026-10-28):

    bash scripts/pass1_narrow_gate.sh                     # one round, every project
    VOTES=3 bash scripts/pass1_narrow_gate.sh objektas_h  # one project, 3 rounds

Commits: see `git log v4/pass1-narrow`. Review-fix commits (Sonnet 5.5, 2026-10-28):
`56461475` fix(v4): LED niche wording + omitted-room handling in merge_narrow (12 narrow tests);
`fe239056` fix(v4): gate script — corpus-wide scoring after all projects are read.

## §1 Why

Measured on `objektas_h` (fresh read, 2026-10-26):

- Full Pass-1: 3 voting rounds × ~170 s = ~510 s. ~10 000 output tokens per round
  (`_meta.output_tokens` ~30 000 total).
- Zoom: 87 s for 9 attempted / 0 applied (`_meta.zoom_attempted = 9`, `zoom_applied = 0`).
- The rest of the Vision readers (doors 37,87 s, fixtures 20,87 s, door_types 11,37 s): ~70 s.
- Total: 735,4 s (`_meta.elapsed_s`).

Pass-1 is output-token-bound, not page-bound: the one call sends the images cached across voting
rounds (`cache_read_tokens` dominates). The time is set by what the prompt asks for.

The 2026-10-26 no-vision route (OFF behind `SAMATU_NO_VISION_ROUTE=1`, flagged in CLAUDE.md and
in `docs/superpowers/research/2026-10-26-no-vision-vector-route.md`) removed Pass-1 entirely for
vector PDFs and FAILED the gate:

- Totals 57,50 → 65,86 % (billed lines +8,4 pp).
- Scorecard 32/32 → 25/32 reading tiers.

Why removing Pass-1 cost 8 pp: the per-room fields only a picture carries went blank — windows
and doors on plans without wall outlines, hidden/sliding doors (`pasleptos_duris`), LED niches
(`nisa_LED`) from the ceiling plan, built-in furniture (`spinta_built_in`) that cuts walls, and
ceiling type (`lubu_tipas`).

Founder decision 2026-10-27: **narrow Pass-1, do not remove it**. Keep the picture call. Ask only
for the fields the lanes cannot read. The room list, areas and primitives come from the drawing's
text table BEFORE Vision.

## §2 Design

### N1 — Room list from the drawing's text (BEFORE Pass-1)

Same two helpers the no-vision route uses, now public aliases in `no_vision_route`:

- `pdfplumber_eksplikacija.extract_eksplikacija_pdfplumber` — deterministic $0.
- `eksplikacija_from_text_schema` — the eksplikacija page's TEXT handed to `text.schema_llm`,
  substring-guarded. Allowed, cheap: one text-schema model call. The model never sees the sheet.
- `rooms_from_table` — each row becomes a room with `nr`, `pavadinimas`, `plotas_m2`,
  `plotas_saltinis = "eksplikacija"`, `_pavadinimas_saltinis = "lentele"`, `paskirtis` inferred
  from the name (`universal_rules.classify_room_name`), `_paskirtis_source = "inferred_from_name"`.
  Empty `elementai`.

Narrow mode is possible ONLY when this yields ≥ 1 room. Otherwise fall open to today's full
Pass-1 Vision, stamp `_meta.pass1_narrow = {status: "fell_open", reason: "no_room_list_in_text"}`.

### N2 — Page selection by text page-kind

`text/page_kind.page_kinds(pdf_bytes)` → `[{nr, tipas, saltinis, tekstas}]` using the vocabulary
`page_classifier.CANONICAL_TIPAI` (plus `unknown`). Narrow page set =

- every page whose kind is `floor_plan`,
- plus every page whose kind is `ceiling_plan`,
- plus every page whose kind is `door_window_schedule`,
- plus every page whose folded title (`tekstas`) matches `\bBALD\w*\b.*\b(PLANAS|ISDESTYM|IRANGOS)\b`
  — guard against a furniture title that `page_kind._STRONG`'s floor_plan regex misses.

(There is no `furniture_plan` kind in the vocabulary. The brief forbade adding one and the
`page_kind._STRONG` floor_plan regex already catches „BALDU PLANAS" / „BALDU ISDESTYM" — the
title-regex guard here is a safety net for titles like „BALDŲ IR ĮRANGOS PLANAS" that only match
on the stem.)

`page_filter.select_pass1_pages` runs first for vendor-quote and photographic-page drops; the
narrow set is applied as the SECOND filter. Final page list = narrow kinds ∩ not(vendor/photo).

Fail open: if the narrow set has no `floor_plan` page, stamp
`_meta.pass1_narrow.reason = "no_floor_plan_kind"` and run today's full Pass-1 unchanged.

### N3 — The narrow prompt

New system text in `pass1_narrow.NARROW_SYSTEM_TEXT`, built by lifting the paragraphs the brief
calls out of `prompt.SYSTEM_TEXT`:

- the `<symbol_recognition>` paragraphs for doors / windows / LED nišos / built-in / columns and
  the `lubu_tipas` enum, verbatim;
- the `bbox_pct` paragraph that rules out elevations / mazgai / schedules;
- a TypeScript schema that only lists `nr` + `rasta` + `puslapio_nr` + `bbox_pct` + `lubu_tipas` +
  `elementai[]`. The element enum copies today's eight values (`langas`, `duris`,
  `pasleptos_duris`, `nisa_LED`, `stoglangis`, `spinta_built_in`, `kolona`, `atsikismas`); each
  element carries `tipas`, `kiekis` and the optional `plotis_mm` / `aukstis_mm` / `ilgis_m` keys
  with the names today's `prompt.OUTPUT_SCHEMA` uses (ilgis_m is kept in meters as today — the
  brief mentioned mm by mistake, the stored field name is `ilgis_m`).

Explicitly forbidden by the schema's final clause (so the model never fills them): `plotas_m2`,
`perimetras_m`, `lubu_aukstis_m`, `paskirtis`, `pastabos`, `confidence`, `warnings`, `santrauka`,
`pozicijos`, `puslapiai`, `durys_total`, `langai_total`, `detected_symbols_summary`.

`max_tokens = NARROW_MAX_OUTPUT_TOKENS = 16000` (today's 64 000 is sized for the full schema).

The user content is `prompt.build_user_content`-style: images with a cache break on the last
image, then a text block that carries the TABLE room list as JSON (every room's `nr`,
`pavadinimas`, `plotas_m2`) and the final instruction. Byte-identical across voting rounds so
voting hits the prompt cache the same way today's full prompt does.

### N4 — Voting, zoom, merge

- Voting: `narrow_votes()` returns 1 by default; a round number ≥ 1 can be set via
  `SAMATU_PASS1_NARROW_VOTES`. `votes == 1` calls `_run_narrow_once` directly, bypassing the
  voter even when `ENABLE_EXTRACTION_VOTING` is on (narrow mode controls its own cadence). The
  voter is `extraction_voter.vote_extraction`, which keys rooms by `nr:<nr>`; the table hands the
  nr to the prompt and the model echoes it back, so identity is safe.
- Zoom: skipped entirely in narrow mode (areas are table facts). `_meta.zoom_attempted = 0`,
  `_meta.zoom_applied = 0`, `_meta.zoom_elapsed_s = 0.0`,
  `_meta.zoom_skipped_via_eksplikacija = n_rooms`. The UI listens to `zoom_started` /
  `zoom_completed` events — both are emitted with `skipped: true`.
- Merge: `parsed["patalpos"]` is built from the N1 table rooms (areas never move). The model's
  answer writes per nr: `puslapio_nr`, `bbox_pct`, `lubu_tipas`, `elementai`,
  `_pass1_narrow_rasta: True`. A room the model marked `rasta: false` keeps its table row,
  carries an LT sentence in `_kilme`, and gets a user-visible WARN in `parsed["warnings"]`.
- `_meta.kambariu_tapatybe = {"saltinis": "lentele", ...}` — same shape the no-vision route
  writes; downstream `identity_from_table` / `mark_model_list` / the eksplikacija guard never
  re-run on this route (`extract_interior` only invokes them when the room list came from the
  model, which it did not).
- Stream events: `route_selected {route: "vision_narrow", sentence: "…"}`, `pass1_started
  {pass: "narrow"}` / `pass1_completed {pass: "narrow", patalpos: [...]}`, `zoom_started
  {skipped: true}` / `zoom_completed {skipped: true}`.

### Downstream (unchanged by narrow)

`extract_interior_narrow` calls today's own helpers in the same order the Vision route uses them:

1. `drawing_lanes.run_drawing_lanes` (page kinds applied, text scan + anchors, dimension pairs,
   raster outlines, heights, vector geometry, legend counts).
2. `vision_call.apply_apdailos` (text layer / OCR, one `text.schema_llm` text model call —
   substring-guarded).
3. `vision_call.apply_door_types` (text, no model).
4. `row_provenance.fill_heights_from_read`.
5. `plyteliu_specifikacija.extract_plyteliu_specifikacija`, `symbol_legend.scan_symbol_legend`,
   `door_schedule.scan_door_schedule`, `vector_symbols.scan_vector_symbols` (deterministic $0).
6. `vision_call._recompute_per_room_via_python` — this internally runs
   `universal_rules.reconcile_openings_with_walls`, which stands the model's `elementai` in the
   drawn openings. We do NOT call it separately; `_recompute_per_room_via_python` already does.
7. `scope.mark_rooms` / `_build_pozicijos_from_rooms` / `_recompute_santrauka`.
8. `apply_lt_sanity`, `cross_page_validator`, `sanity_checks`, `consistency_checker`,
   `sanity_mirror`, `_emit_v8_compat_fields`.

`_append_extra_call` tallies the narrow Pass-1 and the apdailos sub-call so pricing counts them;
`run_usage.note` writes the per-user cap side tally.

## §3 Fail-open paths

Three, each ⇒ today's full Pass-1 Vision runs unchanged and the reason is stamped on
`_meta.pass1_narrow`:

- `no_floor_plan_kind` — `text/page_kind.page_kinds` returned no entry with `tipas = "floor_plan"`.
- `no_room_list_in_text` — pdfplumber and the text-schema fallback both returned 0 rows.
- `no_narrow_pages_after_filter` — narrow kinds exist, but after `select_pass1_pages`'s vendor /
  photo drops nothing survives.

Any uncaught exception inside `extract_interior_narrow` becomes a WARN in the parsed warnings
list (not a fall-open). The gate script never silently rescues; a crashed narrow run returns an
error dict that `extract_interior` returns directly (same shape today's Vision errors use).

## §4 Tests

`backend/tests/test_pass1_narrow_2026_10_27.py`, 11 cases, all synthetic (reportlab-only PDFs):

- `test_flag_off_does_not_call_narrow_extract` — flag off ⇒ `extract_interior` never calls the
  narrow entry. Monkeypatches `extract_interior_narrow` to raise.
- `test_narrow_enabled_reads_env` / `test_narrow_votes_defaults_to_one` — env parsing.
- `test_narrow_kinds_keeps_plan_and_ceiling_drops_elevation` — a 4-page synthetic PDF
  (`AUKŠTO`, `LUBŲ`, `BALDŲ IŠDĖSTYMO`, `SIENŲ IŠKLOTINĖS` titles) ⇒ pages 1–3 kept, 4 dropped,
  `has_floor` true.
- `test_narrow_falls_open_when_no_floor_plan_page` — PDF with only sections / facades /
  visualisations ⇒ `NarrowFallOpen(reason="no_floor_plan_kind")` without rendering raster or
  calling Vision.
- `test_narrow_falls_open_when_no_room_list` — monkeypatches `_read_table_rooms` to return `[]`
  and `_page_kinds` to return a floor_plan; the full-Vision path's `_run_pass1_voted` /
  `_run_pass1_once` are stubbed to sentinels; stamped `pass1_narrow.reason = "no_room_list_in_text"`.
- `test_narrow_user_content_lists_every_table_room` — the final user text block carries each
  table room's nr + pavadinimas + plotas_m2 and the cache break stays on the last image.
- `test_narrow_schema_omits_plotas_perimetras_lubu_aukstis_and_keeps_elementai_enum` — the
  system text names the kept fields and forbids every removed field; the element enum is today's.
- `test_merge_narrow_writes_model_fields_without_moving_table_areas` — the table area survives
  the merge; `puslapio_nr` / `bbox_pct` / `lubu_tipas` / `elementai` are written per nr.
- `test_merge_narrow_room_marked_rasta_false_keeps_table_row_and_warns` — a `rasta: false` row
  keeps its table primitives, gets `_kilme`, and the WARN message tells the user what to check
  (no pipeline jargon, no client name, no benchmark count).
- `test_merge_narrow_drops_elements_with_unknown_tipas` — an element whose `tipas` is not in the
  enum is dropped before `calc_room_quantities` sees it.

Golden replay (`test_golden_replay_extract_interior.py`) PASSES with the flag unset — no pin
needed, `SAMATU_PASS1_NARROW` is simply absent in that test's environment.

## §5 The gate script and the runtime arithmetic — MEASURED (2026-10-28)

See §10 for the full measured numbers. Summary:

- `objektas_d`: 212,4 s → 80,7 s (one round; zoom 0 s).
- `objektas_b`: 468,3 s → 372,4 s (b's full Pass-1 sends 8 pages; the time is NOT dominated
  by Pass-1 output tokens, so a narrow prompt saves little on b).
- `objektas_c`: fell open — `no_floor_plan_kind` (three A3 sheets carry no floor-plan title
  in their text layer). Cost to read c from scratch: 5,56 USD by the sprint's meter
  (70k output tokens incl. zoom). This makes a corpus-wide fresh re-read ~15–25 USD, not 7.
- `objektas_a`, `objektas_g`, `objektas_h`: skipped by the old gate script (defect (a), see §10).
- Accuracy on b and d: WORSE — see §10.
- Verdict: narrow mode stays OFF. Founder chose parallel voting + zoom skip on the full
  Pass-1 (branch `v4/pass1-fast`).

Gate criteria (for reference — narrow FAILED):

- totals ±1 pp of 57,50 %
- rows ±10 % within 1 pp of 9,0 %
- € ±10 % within 1 pp of 18,0 %
- scorecard tiers unchanged (21/24 · 32/32 · 29/30 · 2/4)

## §6 Open — not this task

- The doors reader (37,87 s) and the fixtures reader (20,87 s) are the next runtime line to
  shave. Both read the plan image again for information the drawing's text and legends already
  carry (door schedule + legend counts). They are OUT OF SCOPE for this change: the narrow
  Pass-1 keeps their inputs unchanged.
- Legend-lane budget on big projects (`objektas_g`) — unclear whether the ~1500 s is still
  Pass-1-dominated or has shifted to the lanes with narrow mode on. The gate script measures
  that per project.
- `objektas_a` has two text-schema calls (eksplikacija + apdailos) which the narrow route also
  pays; those are already cheap (text, substring-guarded). No change expected.
- `objektas_c` and `objektas_g` historically have fuzzy eksplikacija tables (the no-vision gate
  recorded both as rooms_from_table-sparse). If pdfplumber + text-schema still return no rows
  there, narrow mode falls open to today's full Pass-1 on those two — gate script records that
  under `pass1_narrow.reason`.

## §10 Gate run 2026-10-28

### Gate script defects (found on first run)

**(a) `run_vision_on_truth_set.py --only` silently skipped a, g, h.** That helper reads the
registry and only processes projects with `has_cached_extract: false`. Three of the six corpus
projects have `has_cached_extract: true` (a, g, h) and were "0 project(s) to process" on every
gate run — their `ai_extract_narrow.json` files were simply copies of the baseline.
Fixed 2026-10-28: `pass1_narrow_gate.sh` now calls `pass1_fast_measure.py --tag narrow` which
handles all corpus slugs regardless of the registry flag.

**(b) `git checkout -- ground_truth/*/ai_extract.json` left `ai_extract_meta.json` modified.**
The sprint helper writes a sidecar `ai_extract_meta.json` alongside the main file; the broad
wildcard restore did not touch it. Fixed: the gate script now explicitly restores both files
per slug and fails loudly if `git status --short ground_truth` is non-empty after restore.

### Projects that ran

Only b and d ran narrow (a/g/h skipped by defect (a); c fell open).

**`objektas_c`** fell open with `reason: "no_floor_plan_kind"` — the three A3 sheets carry no
floor-plan title in the text layer (page-kind returns no `floor_plan` entries). A full Pass-1
read of c (including zoom) cost 5,56 USD by the sprint's meter (~70k output tokens incl. zoom).
This anchors a corpus-wide fresh re-read at ~15–25 USD (six projects × ~3–5 USD each), not the
~7 USD the §5 estimate assumed before the gate.

### Runtime

| slug         | baseline (s) | narrow (s) | delta  |
|--------------|:------------:|:----------:|:------:|
| objektas_d   |   212,4      |    80,7    | -62 %  |
| objektas_b   |   468,3      |   372,4    | -21 %  |

`objektas_b`'s full Pass-1 already sends 8 pages (the largest page-count in the corpus after
the page-filter). The time is not Pass-1 output-token-dominated; narrow mode saves the token
tail but not the image transfer or the apdailos / doors readers — hence the modest win.

### Accuracy: WORSE on both projects

**`objektas_b`** (narrow vs stored baseline):
- Rows ±10 %: 1,8 % → 0,9 % (halved)
- Reveals family: −10,6 % → −36,9 %

**`objektas_d`** (narrow vs stored baseline):
- Rows ±10 %: 14,0 % → 12,0 %
- € ±10 %: 15,0 % → 6,1 %
- Reveals: −6,4 % → −41,5 %
- Scorecard exterior doors: 4/4 → 3/4 (room 04's 1370-wide exterior door read as a 900 interior door)

### Root cause: invented sizes and missed niches

The narrow prompt asks the model for per-room `elementai` (openings, niches, ceiling type) only —
the room list and areas come from the table. Without the full schema's dimensional context, the
model fills in standard-ish sizes that are wrong:

- `objektas_d` actual: 2650×1500 / 2940×1500 / 3405×2100 (read from annotations in stored read).
  Narrow produced: 1500×1500 × 3, plus a 910×2100 hidden door and a 1510×2390 wardrobe in every
  room. Every size is a plausible default — not what the drawing shows.
- `objektas_b` (11 rooms with LED niches): 11 → 4 niches found. The ceiling plan carries the
  niche lengths in text annotations the narrow prompt did not route to.

These are not prompt-tuning problems. They reflect that opening sizes and niche lengths require
the full multi-page context the narrow prompt strips.

### Verdict

Narrow mode FAILED the gate. The founder chose the zero-accuracy-risk lever instead:
keep the full Pass-1 and (1) run its voting rounds in parallel (`ENABLE_PARALLEL_VOTING=1`),
(2) skip the zoom pass when the room list came from the drawing's table (the 2026-10-25 rule
already handles this — see `docs/superpowers/research/2026-10-28-pass1-fast.md`).
`SAMATU_PASS1_NARROW` stays OFF (default).
