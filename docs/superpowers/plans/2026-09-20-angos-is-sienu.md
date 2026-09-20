# Angos iš sienų — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; real-drawing gate;
> browser check on the local demo projects; commit per task; never push.

**Goal:** the door-and-window fact gets evidence on the drawing, a cross-check against the wall solid, and a
one-click way to add an opening the reader missed — without changing any quantity on its own.

Spec: `docs/superpowers/specs/2026-09-20-angos-is-sienu-design.md`.

### Task 1: `vector_rooms` — openings per room
**Files:** `backend/extractor/vector_rooms.py`, `backend/tests/test_vector_rooms.py`.
- [x] Tests (synthetic `two_rooms`): room 1 → one opening 0,9 m to room 2; room 2 → 0,9 m to room 1 and 0,9 m
  to `laukas`; `storis_m ≈ 0,2`; `line_pct` crosses the gap on the wall's axis; a room grown through a bridge
  (merged faces) does not report that bridge; a room without an outline reports nothing.
- [x] `_bridge_records` (poly, gap, thickness, threshold line, two side probes); `_bridges` = its polygons;
  `_openings(records, faces, solved, m_per_pt, W, H)` at the end of `trace_vector_rooms`. Commit.

### Task 2: lane + fact
**Files:** `backend/extractor/geometry_lane.py`, `backend/extractor/room_facts.py`, tests, fixture gate.
- [x] Lane writes/clears `_angos_sienose` (+ page); `LANE_VERSION = 4`; gate grows (H 06/07/10, G 03/05/06).
- [x] Fact: `openings`, comparison sentence, status, `suggestions` (only when the counted doors are 0 and
  interior openings exist / counted windows are 0 and exterior openings exist). Commit.

### Task 3: sheet
**Files:** `frontend/src/lib/roomSheet.js` (`addOpening` + test), `lib/checkOverlay.js` (+ test),
`viewer/CheckLayer.jsx`, `FactRow.jsx`, `RoomSheet.jsx`, `RoomDrawingPane.jsx` (legend), i18n.
- [x] Browser: H 06 amber row with the two wall openings drawn → „Pridėti duris" → consequence strip → undo;
  G 03 agrees (read); console clean. Commit.

### Task 4: measure, gates, record
- [x] Offline measurement for the founder: what deducting every wall opening in both rooms would do to the
  eval (no code shipped for it). Backend full suite, frontend units, eslint, eval unchanged; log; memory.

---

## Vykdymo žurnalas (2026-09-20)

**Commit'ai (vietiniai, nepush'inta):** `cff167e` (vector_rooms + juosta + vartai), `24fd7fa` (faktas),
`c4e41c5` (Patikros lapas), + šis žurnalas.

**Kas pasikeitė prieš planą** — žr. spec'o skyrių „Pataisos vykdant": angos visiems PATIKIMIEMS kontūrams (ne
tik vektoriniams), vienas skaitomas plano lapas su visais užklotais kontūrais, „giliausiai viduje / artimiausias
per toleranciją" taisyklė, faktas lygina tik bendrą skaičių.

**Tikri brėžiniai** (vartai `fixtures_geometry_gate.json`, sąrašai tik auga):
- H: 03 → 06, 07, 09, 11 (+3 į gretimas be kontūro) — 7 angos = 7 Vision durys; 06 → [03 0,77; laukas 1,37];
  07 → [03 0,80]; 08 → [09 1,40]; 09 → [03, 08, 10, laukas ×2]; 10 → [09 1,18]; 11 → [03 0,87; laukas 1,37];
  01, 04, 05 (be savo kontūro) angų neturi.
- G: 01 → 04, 05, 06, laukas 2,84 (+1,00 ir 2 į gretimas); 02 ↔ 03 0,85; 04 → [01; laukas 2,20]; 05, 06 → [01 0,80];
  07 (be vietos) angų neturi. Sutikrinus su Vision: G 02, 03, 04, 05, 06, 08 SUTAMPA; G 01 — 4 prieš 7;
  G 09 — sienose matyti tik 1 iš 3 (sakoma be pavojaus signalo).
- Faktas ant H: 06/07/10/11 (ir 02, 08) gauna „Pridėti duris …" vienu paspaudimu; 09 — geltona eilutė be pasiūlymo
  (1 durys prieš 3 angas į patalpas — kurių trūksta, sprendžia jis).

**Naršyklė** (`demo-objektas_h`, `demo-objektas_g`, 1500 × 950): H 06 — dvi violetinės angos ant kontūro, užvedus
faktą — pločiai „0,77" ir „1,37" patalpos išorėje; geltona eilutė → „Pridėti duris 0,80 × 2,10 m — anga į
patalpą 03" → faktas „2 vnt. … Sienose tiek pat angų", ženkliukas „jūsų", pasekmės juosta „Sąmatoje pasikeitė
14 eilučių" (angokraščiai 70 → 75 m, sienos 43,71 → 42,53 m²) → „Atšaukti pataisymą" grąžina viską. G 01 — 7
angos su pločiais, kaimynai įvardyti; G 03 sutampa. Konsolėje naujų klaidų nėra.

**Vartai:** backend pilnas rinkinys 3635 passed, 3 skipped; frontend 738/738; eslint 0 klaidų; eval NEPAKITĘS
(kontrolinis paleidimas: in-sample 9,83 %, OOS 7,06 %, eilutės ±10 % korpuse 24,3 %) — funkcija pati kiekių
nekeičia.

### Išmatuota steigėjui (kodas NEĮDĖTAS): kas būtų, jei sienų angos į kiekius eitų automatiškai
Scenarijus „pridėti tik tai, ko sąraše trūksta" (durys — angoms į patalpas virš suskaičiuotų durų, langai —
angoms į lauką virš suskaičiuotų langų), `eval_harness --totals-only --recompute --geometry`:

| | antraštė in-sample | OOS | eilutės ±10 %: A | H | korpusas |
|---|---|---|---|---|---|
| šiandien | 9,83 % | 7,06 % | 35,8 % | 29,2 % | 24,3 % |
| automatiškai pridėjus | 9,83 % | 7,06 % | 39,6 % | 25,0 % | 25,2 % |

Kas juda: A (pridėti 2 LANGAI) — angokraščiai 78 → 86 m ir dažymo kampai 443 → 452 m ABU įeina į ±10 %.
H (pridėtos 7 DURYS + 2 langai) — angokraščiai 70 → 115 m ir kampai 436 → 481 m ABU išeina iš ±10 %.
Išvada, kurią sprendžia jis, ne variklis: langų angokraščiai atitinka praktiką, o VIDAUS DURŲ angokraščiai ir
kampai, panašu, neskaičiuojami (staktą su apvadais jie uždengia). Kol to nenusprendė — durys pridedamos tik jo
paspaudimu, o pasekmę (kiek pridėjo angokraščių) jis mato iškart po paspaudimo ir gali atšaukti.

**Nepadaryta (sąmoningai):** automatinis atėmimas; durų / lango atskyrimas lauko sienoje; atviros erdvės narių
angos; G 5/6 lapų sutapdinimas (→ „geometrijos ribos").
