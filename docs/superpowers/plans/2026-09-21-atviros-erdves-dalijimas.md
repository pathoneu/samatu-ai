# Atviros erdvės dalijimas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; real-drawing check;
> browser check on the local demo project; commit per task; never push.

**Goal:** two rooms that no wall separates get their own outlines and their own walls from ONE line a person draws —
the imaginary boundary is never counted as a wall. Nothing is saved server-side; quantities follow the existing path.

Spec: `docs/superpowers/specs/2026-09-21-atviros-erdves-dalijimas-design.md`.

### Task 1: `vector_rooms.split_space` + `dimension_sum` imaginary edges
**Files:** `backend/extractor/vector_rooms.py`, `backend/extractor/dimension_sum.py`, tests.
- [x] Tests (synthetic, `two_rooms` without its partition, seats at 2,2 m and 5,7 m): a vertical line at x = 4,3 m →
  two parts ≈ 12,3 m² and 9,3 m², each with ONE `menamos` edge, `perimetras_m` = the part's outline minus that edge;
  a line that leaves both numbers on one side → `bad_line`; points outside the shared face → `not_shared`; three
  seats → `too_many`; no walls → `no_walls`. `sum_perimeters`: a room whose outline has a `menamos` edge sums its
  three real walls, says „sutampa", and never reports that edge as a wall without a dimension.
- [x] Implement; commit.

### Task 2: API
**Files:** `backend/api/room_outline.py` (second endpoint), `backend/tests/test_room_split_api.py`.
- [x] Tests: both rooms come back with `corrected` outlines, `_konturas.saltinis == "padalinta"`, `menamos`, no
  `_atvira_erdve`, perimeters summed from strings; nothing saved; `bad_line` as a 200 answer; 404/401/422.
- [x] Implement (shares the helpers of `outline-at`); commit.

### Task 3: Patikra
**Files:** `frontend/src/lib/roomOutline.js` (+ tests: `splitRequest` two-point state, `roomsWithSplit`,
`splitFailureKey`), `roomOutlineApi.js`, `RoomDrawingPane.jsx`, `CheckLayer.jsx` + `checkOverlay.js` (imaginary edge
dashed, first point marked), `FactRow.jsx`, `RoomSheet.jsx`, `room_facts.py` (sentence + `outline.menamos`), i18n.
- [x] Browser: `demo-objektas_h` room 04 → „Padalinti erdvę" → two clicks → both rooms outlined, perimeter facts,
  consequence strip → „Atšaukti pataisymą". Console clean. Commit.

### Task 4: gates, record
- [x] Backend full suite, frontend units, eslint, eval unchanged; execution log; memory. Commit. No push.

---

## Vykdymo žurnalas (2026-09-21)

**Commit'ai (vietiniai, nepush'inta):** `91ff4f6` (dizainas ir planas), `3f2eb17` (`split_space` + menamos kraštinės
`dimension_sum`), `0107f7d` (API), `4f3100a` (Patikra), + šis žurnalas.

**Kas pasikeitė prieš planą**
- Erdvė imama ties ta durų riba, kur jos plotas geriausiai atitinka lentelės sumą: H ties 1,25 m — 71 m² su kaimynu
  viduje (1,4 m anga tarp sienos GALO ir sienos PLOKŠTUMOS lieka atvira), ties 1,6 m — 60 m².
- Atraiža: linija per nišą sienos gabale palieka 0,1–0,2 m² trečią dalį — ji atitenka patalpai, kurią liečia
  labiausiai (≤ 0,5 m²); didesnė trečia dalis → `bad_line`.
- `others_pct` parametro neprireikė (YAGNI).
- Perimetro faktas „padalijote patys — riba menama" sakomas ir tada, kai perimetras lieka įvertis.

**Tikras H brėžinys:** riba ties lentynų kolona (x = 0,634 lapo pločio): 04 — 26,61 m² (lentelėje 26,31; 1,1 %),
05 — 33,94 m² (35,50; 4,4 %) — riba ten, kur ją turėjo omeny ir dizaineris. Perimetrai be ribos 18,39 + 19,38 =
37,77 m (iki tol pagal plotą: 16,08 + 21,69); abi patalpos gauna savo angas (04: koridorius 2,13 m + 4 langai;
05: koridorius 1,56 m, langas 1,36 m, stiklinė siena 5,07 m).

**Naršyklė** (`demo-objektas_h`, 04): „Padalinti erdvę brėžinyje" → „1 iš 2…" → paspaudimas (kryžiukas) → „2 iš 2…"
→ paspaudimas → savas kontūras su punktyrine riba, sienos su užrašais, angos; perimetras 16,08 → 18,41 m (įvertis
pagal SAVO sienas: 1 iš 9 sienų be matmens); „Sąmatoje pasikeitė 19 eilučių" (virtuvės plytelės 9,65 → 11,05 m²…) →
„Atšaukti pataisymą" grąžino bendrą erdvę abiem patalpoms. Konsolė švari.

**Vartai:** žr. `docs/superpowers/specs/2026-09-21-geometrijos-ribos-design.md` (bendras paleidimas visai dienos
partijai): backend 3690 passed / 3 skipped, frontend 750/750, eslint 0 klaidų, eval nepakitęs (9,83 / 7,06 %).

**Nepadaryta (sąmoningai):** erdvės su 3+ patalpomis; laužytos ribos.
