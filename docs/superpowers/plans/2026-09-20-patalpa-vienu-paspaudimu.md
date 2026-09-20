# Patalpa vienu paspaudimu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; real-drawing check;
> browser check on the local demo projects; commit per task; never push.

**Goal:** in Patikra, one click inside a room gives it the wall-exact outline and re-reads its walls — with the
consequence shown and one-click undo. Nothing is saved server-side; quantities follow the existing path.

Spec: `docs/superpowers/specs/2026-09-20-patalpa-vienu-paspaudimu-design.md`.

### Task 1: `vector_rooms.outline_at`
**Files:** `backend/extractor/vector_rooms.py`, `backend/tests/test_vector_rooms.py`.
- [x] Tests (synthetic): a click in room 1 of `two_rooms` → its 4×3 m outline, area within 2 %; a click inside
  another room's trusted outline → `{"status": "taken", "nr": "02"}`; outside the walls → `outside`; a sheet
  without walls → `no_walls`; one face holding two table rooms (no partition) with a 12 m² table area → `open`;
  a face whose area disagrees with the table by 30 % → `ok` with `paklaida`; no table area → `ok`, `paklaida` None.
- [x] `_match(..., strong_tol=AREA_WARN)`; `outline_at` = solid → per door limit: bridges → `_match` with the one
  click as a strong seat, `others` as `solved`, `strong_tol=inf`. Commit.

### Task 2: API
**Files:** `backend/api/room_outline.py` (new), `backend/main.py` (router), `backend/tests/test_room_outline_api.py`.
- [x] Tests: returns the room's geometry keys with `polygon_source == "corrected"`, `_konturas.saltinis ==
  "parodyta"`, a perimeter SUMMED from the strings and `_angos_sienose`; `kitu_angos` names this room for the
  neighbour; the stored project is untouched; `taken` / `outside` come back as 200 with their status; 400 for
  coordinates outside 0…1 or a missing page; 404 for an unknown room and for a stranger; 401 anonymous; a user
  perimeter (`user_override`) survives.
- [x] Endpoint: owner filter, rate bucket `room_outline`, scale from `_meta.geometrija.masteliai` else from the
  sheet's own strings, lane on a deep copy, whitelist `GEOMETRY_ROOM_KEYS`. Commit.

### Task 3: Patikra
**Files:** `frontend/src/lib/roomOutline.js` (+ test: `displayPointOf`, `outlinePatch`, `outlineFailureKey`),
`frontend/src/lib/roomOutlineApi.js`, `RoomDrawingPane.jsx` (pick mode + banner + button), `FactRow.jsx` (button on
the perimeter fact without an outline), `RoomSheet.jsx` (handler → `saveRoomEdit` → `land`), i18n.
- [x] Browser: `demo-objektas_h` room 01 → „Parodyti patalpą" → click inside → outline drawn, perimeter fact
  updated, consequence strip → „Atšaukti pataisymą"; a click inside a neighbour says whose room it is; G 07.
  Console clean. Commit.

### Task 4: gates, record
- [x] Backend full suite, frontend units, eslint, eval unchanged; execution log; memory; re-run the demo script
  (LANE_VERSION 5). Commit. No push.

---

## Vykdymo žurnalas (2026-09-20)

**Commit'ai (vietiniai, nepush'inta):** `ece59f7` (dizainas ir planas), `a8dd957` (`outline_at`), `3e5df12` (API +
juosta angas skaito kiekvieną kartą), `d479615` (Patikra), + šis žurnalas su perimetro fakto sakiniu.

**Kas pasikeitė prieš planą**
- `outline_at` gretimą veidą per angą be durų paima TIK kai tai paaiškina lentelės plotą (±8 %) — pirmas variantas
  („bet kas, kas priartina") sintetiniame plane prijungė kaimyno kambarį. Papildomas parametras `other_seats_pct`:
  erdvė, kurioje stovi kitos patalpos atspausdintas numeris, yra bendra (`open` + `su`).
- Serveris juostą leidžia DU kartus (prieš — kitų patalpų kontūrams, masteliams ir sutapdinimui; po — sienoms ir
  angoms); matmenų eilutės skaitomos vieną kartą. Išmatuota: H ≈ 1,2 s, G ≈ 5,4 s, B ≈ 8 s.
- Juosta angas dabar skaito KIEKVIENAI patalpai su kontūru kiekvieną kartą (vektorinėms irgi) — kitaip kaimyno
  „gretima patalpa" nevirsdavo numeriu, kai patalpa gaudavo kontūrą vėliau. H juostos laikas nepakito (0,86 s).
- Perimetro faktas pasako, kieno kontūras: „Patalpą brėžinyje parodėte patys" (+ plotų palyginimas, kai nesutampa).

**Tikri brėžiniai**
- H 01 (juosta atsisakė: kontūras 2,86 m² prieš lentelės 4,48 m²): paspaudus jo numerio vietoje — kontūras su niša,
  perimetras SUDĖTAS iš užrašų „600 + 996 + 1140 + 690 + 1596 + 1140 + 690 = 6,85 m" (kontūras rodo 6,77 m —
  sutampa); iki tol buvo 8,60 m „įvertis iš plano vaizdo".
- G 07: plane savo erdvės NETURI (veidai 1,57…32,34 m²: nė vienas neatitinka 5,64 m²; ta pati vonia surašyta du
  kartus — faktas tai jau sako ir siūlo patalpą išjungti). Paspaudimai teisingai atmetami („priskirta patalpai 01 / 06").
- G 03/05/06 (jau vektoriniai): paspaudimas atkuria tą patį veidą ir tą patį perimetrą.

**Naršyklė** (`demo-objektas_h`, 01): „Parodyti patalpą brėžinyje" → juosta „Spustelėkite patalpos 01 VIDUJE…" →
paspaudimas → kontūras, žalios sienos su užrašais, violetinės angos, perimetro faktas „perskaityta", juosta
„Pakeista. Sąmatos eilutės nepasikeitė" (tambūro sienos pagal paskirtį neskaičiuojamos) → „Atšaukti pataisymą"
grąžina viską; paspaudus koridoriuje — „Ši vieta jau priskirta patalpai 03", pasirinkimas lieka įjungtas.
Konsolėje naujų klaidų nėra.

**Vartai:** backend 3651 passed, 3 skipped; frontend 743/743; eslint 0 klaidų; eval nepakitęs (9,83 % / 7,06 %;
eilutės ±10 %: G 20,0 %, H 29,2 %, korpusas 24,3 %).

**Nepadaryta (sąmoningai):** viršūnių tempimas; atviros erdvės padalijimas linija (H 04/05 — didžiausios patalpos);
rastrinis atsarginis kelias lapams be vektorinių sienų.
