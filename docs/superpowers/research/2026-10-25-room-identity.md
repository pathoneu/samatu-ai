# Room identity from the drawing (v4 Phase 3a) — 2026-10-25

Branch `v4/room-identity` from `togal-v2` @ c9e5ab37 (after the perimeters merge 97f8a9d5). LANE_VERSION 16 → 17.
Worker: Opus 5.5. Not merged. No paid call anywhere: every run below had the key removed or dead, and constructing a
client or sending a message raised.

## Resume point

- DONE and measured: everything in §1–§4. Open items for the manager: §5.
- If this is picked up again: the branch is committed (hash in the merge-log row / the hand-back). Nothing is
  half-done.

## 1. What changed

**`backend/extractor/room_identity.py` (new, pure).** One matcher used by three callers.
- `identity_from_table(model_rooms, eks)`: when the room table came from the drawing's text
  (`_meta.source` ∈ `pdfplumber_table`, `ocr_table`), its rows ARE the room list, in table order: number as drawn
  (`<unit>-<nr>` for stacked unit tables, with `_vienetas` and `_nr_brezinyje`), name, area. A model room lends its
  readings (openings, heights, finishes, its box) to the row it matches; it never keeps its key (`_modelio_nr`
  records it). Passes, each pairing only when unique both ways: same number (unless the names flatly contradict —
  the old row guard); same name (bracketed remark, accents, punctuation ignored) and area within 0,005 m²; agreeing
  names and same area; same name and area within 2 %; same name alone. Twins with one name and one area stay
  unpaired rather than swapped.
- A model room no row matches is **dropped** with a note (`warnings`, code `room_not_in_table`, plain LT, decimal
  comma, `is_banned`-clean). A row no model room matched becomes a room from the table alone (`_tik_lenteleje`) on
  the plan sheet the model read the rooms on.
- A table that matches fewer than half of the model's rooms is not taken as the list (`None` → the old join runs
  unchanged): a bundled drawing's other building must not replace the rooms.
- `join_rows` = the old join's area / perimeter / evidence stamp, statement for statement (`stamp_row_evidence` is
  the body of `vision_call._stamp_eksplikacija_evidence`, which now delegates to it).
- `mark_model_list`: no text-layer table → every room carries `_pavadinimas_saltinis = "modelis"`.
- `rekey_stored_rooms`: the free re-read's version — only `nr` changes on a matched stored room (plus
  `_vienetas`, `_nr_brezinyje`, `_modelio_nr`), nothing he set moves, no room is added or dropped; refuses when an
  unmatched room already wears a drawn number another room would take.

**`vision_call.extract_interior` Step 2.4.** After the foreign-table guard, `identity_from_table` runs on the
text-layer rows; when it answers, its list replaces `parsed["patalpos"]`, `join_rows` joins the table, dropped
rooms get their note, `_meta.kambariu_tapatybe` records what happened (rows, matched, table-only, dropped,
`perkeisti_numeriai`). When the guard had said „insufficient" only because the model's numbers matched no row, and
≥ 3 rooms matched by identity, the guard verdict becomes `accept` (`by: kambariu_tapatybe`, the first verdict kept
under `pirmas`) so the ceiling anchor reads the table's own total (objektas_i: the unit sums' sum). Otherwise the
old join runs exactly as before; afterwards rooms of a model list are marked. Because the room table now merges,
the plan-area lane (it only runs when nothing merged) no longer runs on objektas_i — that is the lane that summed
both units plus the subtotals into a 3 × ceiling anchor (cold-run doc §1.2, „hidden fault").

**`api/free_reread.renumber_rooms`** runs before the lane in `read_drawing`. Skips without opening the PDF when
`_meta.kambariu_tapatybe` exists (assembled from the drawing, or already checked) or when every room wears a number
of the stored `_eksplikacija` (b, h, a, d: no PDF read; pdfplumber needs ~65 s on objektas_b). Otherwise reads the
table from the text layer (objektas_i 4 s, c 3 s, g 20 s — once per project), re-keys, writes
`_perkeisti_numeriai` (composed with an earlier map) and `_meta.kambariu_tapatybe`; the answer carries
`_perkeisti_numeriai` and `santrauka.perkeisti_numeriai`. **`api/detect_run.narrow`** finds a re-keyed room under
its stored key (a room outside the chosen sheets comes back as stored, with the drawing's number).

**Frontend (outside my assigned list, required by the rule „the server saves nothing; the browser merges by
number").** `lib/roomRenumber.js`: `renumberProject` applies the map to the stored project before the by-number
merge — rooms of both lists, `_per_room_overrides`, `_apimtis.patalpos_ne` / `patalpu_sritys_ne` (and the copy under
`_overrides.apimtis`), the rows' `contributions[].room_nr`; `carryIdentity` gives a verified room (kept whole by the
re-read) its `_vienetas` / `_nr_brezinyje`. `lib/freeReread.js` calls both and keeps `_meta.kambariu_tapatybe`.
Without a map the merge is byte-for-byte the old one.

**`scripts/cold_run/run_cold.py`.** The cold variant now builds its room list through `identity_from_table` +
`join_rows` (the paid reading's own assembly, no model rooms); new variant `app` = production's stored model rooms
(nr/name/area only) through the same assembly; summary line per variant.

**`geometry_lane.LANE_VERSION` 17** (the lane reads as at 16; the version offers stored projects the re-read).

## 2. Before / after on objektas_i (the contractor's two uploads)

| path | A placed | A outlined | B placed | B outlined | keys |
|---|---|---|---|---|---|
| free re-read of the production blob, togal-v2 (renumbering off) | 17 | **14** | 17 | **1** | K1…K8, D1…D9 |
| free re-read of the production blob, this branch | 17 | **17** | 17 | **17** | 1-1…1-8, 2-1…2-9 |
| cold runner `cold` (table → assembly → lane) | 17 | 17 | 17 | 17 | 1-1…2-9 |
| cold runner `app` (production's model rooms → assembly → lane) | 17 | 17 | 17 | 17 | 1-1…2-9 |
| cold runner `seeded` (production's keys, old way) | 17 | 1 | 17 | 1 | K1…D9 |

„Placed" = located by a room badge; with K-keys the badge digit „1" served K1 and D1 alike, so two rooms stood on
one badge and their outlines were refused. Free re-read: in-process `POST /api/projects/{id}/free-reread`
(FastAPI TestClient, temp DB + local storage, auth disabled), 17 → 17 rooms, every area unchanged, map
`K1→1-1 … K8→1-8, D1→2-1 … D9→2-9`, summed perimeters A 11, B 13 (as the cold run), ~11–14 s lane. `app` and `cold`
agree room for room (placement, outline m², outline perimeter, perimeter + source, drawn doors / windows): 0 rooms
differ on A, 0 on B. Matching: 17/17 by name + area on both uploads, 0 dropped.

## 3. The corpus is unchanged

- **Room lists** (test `test_corpus_room_lists_are_unchanged`, over the cached `ai_extract.json`): b and h (text-layer
  tables) → same keys, same count, same order, nothing renamed or dropped, and no room field differs except
  `plotas_match`; a and d (their tables were read by the model) and c, g (no table) → the identity path does not
  run, the model's list stands.
- **Eval passes** (`--recompute --gate`; replay `--recompute --replay-geometry --gate`; € via the gitignored priced
  parse copied in): see §4.
- **Reading scorecard** (`scripts/reading_scorecard.py`): byte-identical to togal-v2 (run from a `git archive` of
  togal-v2 against the same fixtures): door pairs 21/24, exterior doors 32/32, windows 29/30, passages 2/4.

## 4. Checks

| check | result |
|---|---|
| plain `--totals-only --recompute --gate` | billed lines **22,60 %**, GATE OK — identical |
| plain `--rows --recompute --gate` | rows ±10 % **26,1 %**, € ±10 % **34,7 %**, GATE OK — identical |
| replay `--totals-only --recompute --replay-geometry --gate` | billed lines **22,92 %**, GATE FAIL 10 = the ten known lines (vs the plain baseline) — identical |
| replay `--rows --recompute --replay-geometry --gate` | **27,4 % / 37,9 %**, GATE OK — identical |
| reading scorecard | byte-identical to togal-v2 |
| golden replay of the real `extract_interior` on objektas_h (stub client, stored answers) | 7/7 pass — Step 2.4's identity path ran on h's text-layer table and production's rooms, rows and totals came out unchanged |
| new tests | `backend/tests/test_room_identity_2026_10_25.py` 22 pass (incl. the corpus test, 6 projects); `frontend/src/lib/roomRenumber.test.js` 6 pass |
| frontend units | 1644 pass / 1 skipped / 0 fail; eslint clean on the touched files |
| full backend suite (`SAMATU_AUTH_DISABLED=1`) | first run 5562 passed / 59 skipped / **1 failed** — `test_free_reread_api::test_the_read_returns…` asserted the exact `santrauka` shape; fixed by adding `perkeisti_numeriai` only when rooms were renumbered. Second run (with the `.vision_cache` linked, so the golden replay runs): **5572 passed / 50 skipped / 0 failed** (9 min 18 s) |

Why the eval cannot move: neither pass runs Step 2.4 (both start from the stored rooms of `ai_extract.json`), and
the lane reads as at 16. The corpus room-list test and the golden replay are what exercise the new assembly.

## 5. For the manager

1. **No-table projects: badges are not made the room list.** The brief said „where no table exists, the lane's
   badge-located rooms are the list". A badge gives a number and a place, never a name or an area, so a badge-only
   list would be rooms with nothing to price; and on objektas_a the badges seat 10 of 11 rooms, so the 11th would
   vanish. What ships instead: the model's list stands and every room says `_pavadinimas_saltinis = "modelis"`. If
   you want the badges to *verify* the model's numbers (mark `_nr_saltinis` from `_vieta.saltinis == "zenkliukas"`
   after the lane), it is a few lines after Step 2.44d.
2. **The note goes to `warnings`, not `_lt_warnings`.** `apply_lt_sanity` rebuilds `_lt_warnings` from scratch at
   Step 4, so a note written there never reaches the screen (the 2026-10-06 elevation-twin precedent).
3. **The paid re-read (`rereadApply` → `mergeReextract`) is not renumbered.** A stored K-keyed project re-read
   *paid* gets a fresh list keyed 1-1…; the by-number merge sees 17 new rooms (touched old ones kept as „missing").
   The free re-read is offered first (LANE_VERSION 17) and re-keys the stored project, after which a paid re-read
   matches; a paid re-read on a never-re-read K-project would need the same map, which only a name + area match of
   stored vs fresh can give (the same `rekey_stored_rooms`, client side or server side). Not done.
4. **Readers after Step 2.4 (doors, apdailos, fixtures, niches — paid)** match their answers to rooms by number then
   name. On a two-unit sheet the model may answer „1" for both units; those readers were not exercised here (no paid
   call). The rooms' names are now the table's („Koridorius", not „Koridorius (kairysis korpusas)"), so a name
   fallback between the two units has two candidates; I did not check how each reader treats that — worth one paid
   run on objektas_i before relying on those readers there.
5. Patikra does not yet show `_perkeisti_numeriai` („K2 → 1-2"); the map is on the project for it.
