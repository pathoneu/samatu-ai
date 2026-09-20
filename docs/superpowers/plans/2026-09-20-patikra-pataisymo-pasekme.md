# Patikra: pataisymo pasekmė, „jūsų", „Atšaukti" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; browser check on the
> local demo projects before the UI commit; commit per task; never push.

**Goal:** a fix on the check sheet shows what it changed right where it was made, can be undone with one
click, and every fact that is his says so.

**Architecture:** backend adds one boolean (`yours`) per fact in `room_facts.py`; frontend gets three pure
functions in `lib/roomSheet.js` (`factKeyForField`, `consequenceOf`, `undoPatch`), a `FixConsequence` strip
rendered under the fixed `FactRow`, and `lastFix` state in `RoomSheet`.

Spec: `docs/superpowers/specs/2026-09-20-patikra-pataisymo-pasekme-design.md`.

### Task 1: `yours` on the facts
**Files:** `backend/extractor/room_facts.py`, `backend/tests/test_room_facts_yours.py` (new).
- [ ] Tests: each of the six facts is `yours` exactly when the value is his — plotas (`plotas_saltinis ∈
  user_override/manual`, `plotas_source ∈ manual/manual_polygon`), perimetras (`perimetras_saltinis ∈
  user_override/manual`), aukštis (`lubu_aukstis_saltinis == user_override` or `_overrides.lubu_auksciai[nr]`),
  apdaila (`_overrides.walls_paint_override[nr]` set), angos (`_angos_user_at` or an element with
  `_dydis_user`), grindys (`grindu_danga_saltinis == user_override`); a plain read room has `yours` false on all.
- [ ] Implement `_is_yours(project, room, key)` and set it in `build_room_facts` (one place). Commit.

### Task 2: pure functions
**Files:** `frontend/src/lib/roomSheet.js` (+ test).
- [ ] Tests: `factKeyForField` (plotas_m2→plotas, perimetras_m→perimetras, lubu_auksciai→aukstis,
  walls_paint_override→apdaila, grindu_danga/paskirtis→grindys, elementai→angos, unknown→null);
  `consequenceOf(diff, 3)` → `{count, lines:[{label, before, after, unit, kind}], more}` — added/removed first,
  then by relative change, never more than 3, zero changes → empty lines; `undoPatch(prev, current)` → prev's
  keys plus `null` for top-level keys the fix added.
- [ ] Implement. Commit.

### Task 3: the strip, the badge, undo
**Files:** `frontend/src/components/roomsheet/FixConsequence.jsx` (new), `FactRow.jsx`, `RoomSheet.jsx`, i18n.
- [ ] `land(result, {factKey})` stores `lastFix = {factKey, diff, prevProject}` instead of the bottom ripple;
  `undoLastFix` writes `undoPatch(prev, current)` through `updateProject`, flushes, reloads the facts, toasts.
  `lastFix` is cleared on room change.
- [ ] `FactRow` shows „jūsų" beside the label when `fact.yours`; `RoomSheet` renders `<FixConsequence>` right
  under the fixed fact's row.
- [ ] Browser (H 03, G 09), console clean; `npm run test:units`, eslint. Commit.

### Task 4: gates and record
- [ ] Backend full suite, frontend units; execution log here; memory; commit. No push.

---

## Execution log — 2026-09-20

| task | commit | what the browser showed (local `demo-objektas_h`, `demo-objektas_g`) |
|---|---|---|
| 1 `yours` | `ad87383` | one flag per fact, the same signals a re-read keeps (`mergeReextract.roomTouched`) |
| 2–3 strip, badge, undo | `832830a` | H 03: „Priimti 21,23 m" → perimeter 21,23 m with „jūsų", strip „Pakeista. Sąmatos eilutės nepasikeitė." (true — the estimate was already what the rows used), „Atšaukti pataisymą" → blank field again, toast; G 09: floor covering → strip „Sąmatoje pasikeitė 5 eilutės: … plytelių klijavimas 10,54 → 3,76 m² … ir dar 2", undo → back to „perskaityta iš grindų plano"; the page does not move; console clean (one stale HMR entry from editing the viewer while it was mounted) |

Notes: the undo writes the PREVIOUS project object back (`lib/roomSheet.undoPatch` — plus `null` for keys the
fix added), so the numbers return exactly, not through a recompute. One level, the last fix on the room; it is
forgotten when he moves to another room. The bottom „Persiskaičiavo…" line remains for actions that are not a
fact fix (scope, quantity override).

Not done here: dragging outline vertices on the sheet and re-reading the walls after it; fact-type columns
across rooms; multi-level undo.
