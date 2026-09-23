# Patikra kaip klausimų eilė — įgyvendinimo planas

> Spec: `docs/superpowers/specs/2026-09-21-klausimu-eile-design.md`. Vykdoma šioje sesijoje, TDD,
> kiekviena dalis patikrinama ant tikrų H/G ir naršyklėje PRIEŠ rodant steigėjui. Niekas nepushinama.

**Tikslas:** Patikra atsidaro su trumpu projekto klausimų sąrašu; kiekvienas klausimas turi programos
siūlomą atsakymą; vienas veiksmo šablonas; patalpų lapas lieka antrinis.

**Architektūra:** klausimai — gryna funkcija virš esamų `room_facts` (be PDF, greita). Atsakymai eina
esamais rašymo keliais. Vienintelė nauja geometrija — siūloma bendros erdvės riba (`propose_split`).
Frontend: naujas puslapis + bendras `useProjectFixes` kabliukas, iškeltas iš `RoomSheet.jsx`.

---

## 1 dalis — backend: klausimai iš faktų

**Failai:** `backend/extractor/project_questions.py` (naujas), `backend/api/project_questions.py` (naujas),
`backend/main.py` (router), `backend/tests/test_project_questions.py` (naujas).

- [ ] Testai (sintetiniai projektai, tik tai, ko reikia faktams):
  - aukštis: 3 patalpos su prielaida + 1 su perskaitytu → VIENAS `aukstis` klausimas, 3 items,
    `proposed` = dažniausias naudojamas, `why` mini perskaitytas patalpas;
  - perimetras: `missing` su įverčiu ir `assumed` → `numbers` items su `proposed`;
  - konturas: `_konturo_priezastis` be `_atvira_erdve` → `outline` item su `reason`; bendros erdvės
    patalpos į `konturas` NEpatenka, o duoda `erdve:04+05` (po vieną kiekvienai erdvei; 3+ narių — ne);
  - angos: `suggestions` → items; klausimas be pasiūlymų → `manual`;
  - grindys/apdaila: `choices` su mašinine `proposed` reikšme ir etikete;
  - apimtis: išjungta patalpa klausimų neduoda;
  - tvarka: aukstis, konturas, erdve, perimetras, plotas, angos, grindys, apdaila;
  - skaitikliai `asked` / `read`; projektas be klausimų → `questions == []`;
  - tekstuose nėra draudžiamo žargono (tas pats sargas kaip faktams: `user_text`).
- [ ] Įgyvendinti `build_questions`; endpoint `GET /api/projects/{id}/questions` (auth kaip `/facts`,
  `scrub_prose`), API testas (200, 404 svetimam projektui).
- [ ] Tikri duomenys: skriptas scratchpad'e per lokalų DB (`demo-objektas_h-senas`, `demo-objektas_g`) —
  sudėtis kaip spec lentelėje. Commit.

## 2 dalis — backend: siūloma riba

**Failai:** `backend/extractor/vector_rooms.py`, `backend/api/room_outline.py`,
`backend/tests/test_vector_rooms.py`, `backend/tests/test_room_split_api.py`.

- [ ] Refaktorius be elgsenos pokyčio: `_shared_face(...)`, `_cut_rooms(...)` iš `split_space`
  (esami `split_space` testai lieka žali).
- [ ] Testai `propose_split` (sintetinis planas iš `synthetic_plan.py`): erdvė su sienos išsikišimu →
  riba per išsikišimo viršūnę, abi dalys ±8 %; erdvė be išsikišimo → pusiausvyros linija, plotai pagal
  lentelę; nėra bendros erdvės → `not_shared`; 3 numeriai → `too_many`; `line_pct` guli erdvės viduje.
- [ ] Įgyvendinti; endpoint `POST …/rooms/{nr}/split-proposal` (bendras `_todays_reading`, nieko
  nesaugo, atsakymas = split-space forma + `line_pct`); API testai.
- [ ] Tikras H: pasiūlyta riba, plotai vs lentelė, laikas. Commit.

## 3 dalis — frontend: gryna logika

**Failai:** `frontend/src/lib/questions.js` + `questions.test.js`, `frontend/src/lib/questionsApi.js`.

- [ ] Testai → kodas: `nextOpenQuestion(questions, skipped, afterId)`, `questionState`, `progressOf`,
  `heightAnswer(project, items, value, perRoom)` → `lubu_auksciai` lentelė; `numbersAnswer(project, field,
  values)` → rooms su `userEditPatch`; `choicesAnswer` (grindys → rooms; apdaila → `walls_paint_override`
  lentelė); `openingsAnswer(project, picks)` → rooms su `addOpening`+`openingsPatch`; tuščias atsakymas →
  `null` (nieko nesiunčiama); projektas nemutuojamas; `answerSummary` (sakinys juostai).
- [ ] `fetchQuestions`, `fetchSplitProposal`. Commit.

## 4 dalis — frontend: bendras nusileidimo kelias

**Failai:** `frontend/src/lib/useProjectFixes.js` (naujas), `frontend/src/pages/RoomSheet.jsx`.

- [ ] Iškelti `run` / `land` / `undoLastFix` / `lastFix` / `ripple` į kabliuką (parametrai: `project`,
  `setProject`, `t`, `afterLand`). `RoomSheet.jsx` naudoja kabliuką — elgsena ta pati.
- [ ] Naršyklėje: patalpos lape aukščio įrašymas → juosta → atšaukimas veikia kaip veikęs. Commit.

## 5 dalis — frontend: Klausimų ekranas

**Failai:** `frontend/src/pages/PatikraQuestions.jsx`, `frontend/src/components/questions/*`,
`frontend/src/App.jsx` (maršrutas per `PatikraEntry`), `frontend/src/components/roomsheet/RoomSheetStrip.jsx`
(nuoroda atgal), `frontend/src/components/viewer/CheckLayer.jsx` + `lib/checkOverlay.js` (`proposal`),
`frontend/src/i18n/lt.json`, `en.json`.

- [ ] Rėlis + kortelė + kūnai: `number_all`, `numbers`, `choices`, `openings` (su brėžiniu pažymėtai
  patalpai), pasekmės juosta viršuje, „Praleisti", pabaigos būsena.
- [ ] `outline`: brėžinys iš karto rodymo režimu, patalpos viena po kitos.
- [ ] `split`: pasiūlymo užkrovimas, peržiūra (kontūrai + punktyras), „Tinka" / „Nubrėšiu pats".
- [ ] Maršrutas ir nuorodos (Klausimai ↔ patalpos ↔ bendri dalykai ↔ sąmata).
- [ ] Naršyklėje ant H ir G KOPIJŲ (steigėjo demo būsenos neliečiamos): kiekviena rūšis iki pasekmės
  ir atšaukimo; konsolė švari; 1500×950 ir siauresnis langas. Commit po kiekvienos veikiančios rūšies.

## 6 dalis — vartai ir dokumentai

- [ ] Visas backend `pytest`, `npm run test:units`, eslint paliestiems failams, geometrijos vartai.
- [ ] Vykdymo žurnalas šiame faile; atmintis (`project_*` + `MEMORY.md`); ataskaita steigėjui: kur
  žiūrėti localhost'e, kas pamatuota, kas liko jo sprendimui.

---

## Vykdymo žurnalas (2026-09-21 → 2026-09-23)

Viskas LOKALIAI ant `viewer-rebuild`, nepushinta (steigėjo OK laukia visa 70 commit'ų eilė). Šios dalies
commit'ai: b757f73 (keturi dalykai iš jo bandymo), 220ff80 (spec + planas), bcd9e8d (1 dalis), 587d6f3
(2 dalis), 2bcf6bf (3 dalis), 06c40d4 (4 dalis), a6500de (5 dalis), f22c4a3 (paspaudimo priežastis prie
brėžinio) ir žurnalo commit'as — 33 failai, +2872 / −207 eilučių iki žurnalo.

**1 dalis — klausimai iš faktų.** `extractor/project_questions.py` (`build_questions`, 16 testų) +
`GET /api/projects/{id}/questions` (2 API testai, registruota po `room_outline_router`). Tikri duomenys iš
lokalaus DB: šviežias H — 66 faktai, 22 laukia žmogaus → **5 klausimai** (lubų aukštis 9 patalpoms, parodyti
01, riba 04/05, 6 patalpų sienų ilgiai, 6 angos sienose); G — 54 / 19 → 5. `build_questions` ~1 ms (be PDF).
Kontūro / erdvės klausimai kyla tik kol tos patalpos perimetras dar laukia (`waiting`, ne `everyone`);
`_apimtis` išbrauktos patalpos neklausia nieko.

**2 dalis — siūloma riba.** `vector_rooms.propose_split`: kandidatės tiesios per KIEKVIENĄ bendro paviršiaus
kampą („kampas", priimama tik kai abi dalys ±8 % nuo lentelės) + pusiausvyra pagal plotų santykį („plotai");
visos pjaunamos tuo pačiu `_cut_rooms`, kaip ranka brėžta linija. Du dalykai rasti TIK ant tikro H ir
pataisyti: (a) linija, pastumta 0,75 pt nuo kampo, išmesdavo kolonos paviršių iš abiejų perimetrų (36,77 iš
37,77 m) → linija tiksliai per kampą, menamos atkarpos = pjūvio ruožai per ATVIRĄ erdvę, viršūnės įterpiamos
ruožų galuose; (b) `dimension_sum._corners` sujungdavo sienos paviršių ir ribą į vieną tiesų kraštą (04
P = 21,96 vietoj 17,95) → `also=boundary_ends` (testas laukia 11,8 m). Rezultatas ant H: „kampas" ties
x = 0,62501 → 04 25,74 m² (lentelė 26,31), 05 34,81 (35,50); 04 perimetras tampa PERSKAITYTAS 17,93 m
(kontūras 17,95); sienų suma 37,75 iš 37,77 m; 1,4 s. Ranka brėžta riba (0,634) nepakito: 18,39 / 19,38.

**3 dalis — gryna logika.** `lib/questions.js` (`nextOpenQuestion`, `questionAfterAnswer`, `progressOf`,
`heightAnswer`, `numbersAnswer`, `floorAnswer`, `wallsAnswer`, `openingsAnswer`, `answerSummary`) —
projektas niekada nemutuojamas; tuščias atsakymas → `null`. Klaida, rasta naršyklėje: santrauka rodė
`[object Object]` ×11 — atsakymai grąžina `touched` (numerius), ne `rooms` (siunčiamą masyvą).

**4 dalis — vienas nusileidimo kelias.** `lib/useProjectFixes.js` iškeltas iš `RoomSheet.jsx`
(`run/land/undoLastFix/lastFix/ripple`, `mergeDarbuSarasasEdits`, `flushProjectSaves` prieš perskaitymą).
Patalpos lapas: aukštis → juosta → atšaukimas veikia kaip veikęs; abiejose juostose nuoroda „Klausimai".

**5 dalis — Klausimų ekranas.** `pages/PatikraQuestions.jsx`, `components/questions/QuestionBodies.jsx`,
`pages/PatikraEntry.jsx` (`/project/:id/patikra` → klausimai; `?kambarys=` / `?etapas=` → patalpos lapas),
`CheckLayer` piešia pasiūlymą (abu kontūrai + punktyras), `checkOverlay` — faktas kitame lape be dėžutės →
patalpos dėžutė per `mapPct` arba visas lapas. Naršyklėje ant H ir G KOPIJŲ (steigėjo demo neliesti):
H — aukštis 9 patalpoms, tambūro paspaudimas (ir netinkamo paspaudimo priežastis juostoje), pasiūlymo
„Tinka", perimetrai, 6 durys (angokraščiai 70 → 100,9 m), atšaukimas, praleidimas, pabaiga; G — aukštis su
viena kitokia patalpa, grindų pasirinkimai 7 lape, „Nubrėšiu pats" dviem paspaudimais → 21 eilutė; nuorodos
patalpos lapas ↔ klausimai. Naršyklėje rasta ir pataisyta: vien rankinių angų klausimas be brėžinio →
fokusas į pirmą `manual` patalpą; pasirinkimų mygtukai laužė pavadinimus → eilutės viena po kita; grindų
klausimas rodė patalpos lapą, ne grindų planą → `OWN_PLACE`; nepavykęs paspaudimas — priežastis juostoje.

**6 dalis — vartai.** Frontend `npm run test:units` 766 / 766 (du kartus: prieš ir po daugiskaitos
pataisos); eslint švarus paliestiems failams (App.jsx eslint konfigūracijos neapima — tik įspėjimas);
geometrijos fixture vartai 3 passed; visas backend `pytest`: 3715 passed / 3 skipped per 5 min 5 s (buvo 3690 — +25 šios dalies testai); eval vartai
(`eval_harness.py --totals-only --recompute --geometry`): nepakito — in-sample 9,83 %, OOS 7,06 %; eilutės ±10 % G / H / korpusas 20,0 / 29,2 / 24,8 %; `baseline_multi.json` identiškas 09-20 paleidimui iki laiko žymos; harness'o exit 1 yra sena 2 % per-projekto riba (B, C), ne šios dalies pokytis. Po kompiuterio perkrovimo
(2026-09-23) ekranas atsidaro iš karto: `demo-objektas_h-senas` → 5 klausimai, konsolė švari. Pataisyta
daugiskaita „11 patalpos" → „11 patalpų" (`readNote_one/_few/_other`, `count`).

**Sprendimai.** `LANE_VERSION` paliktas 7: `_corners(also=…)` keičia tik patalpas su `menamos` kraštais,
kurių riba baigiasi sienos paviršiaus gale — tokių saugomų projektų nėra (ranka brėžta H riba pamatuota
nepakitusi), o versijos kėlimas visiems saugomiems projektams uždegtų perskaitymo juostą be naudos.
Bandomosios kopijos `test-klausimai-h/g/h2` ištrintos iš lokalaus DB; demo projektai nepaliesti.

**Kur žiūrėti (localhost):** `http://localhost:5173/project/demo-objektas_h-senas/patikra` — šviežias H,
5 klausimai; `…/demo-objektas_g/patikra` — G; `…/demo-objektas_h/patikra` — jo paties taisytas H, liko 2.
Patalpos lapas — mygtukas „Peržiūrėti pagal patalpas" arba `?kambarys=01`.

**Lieka steigėjui:** push (70 commit'ų); vidaus durų angokraščių ir kampų konvencija; tambūro sienos;
grindų m² apmokestinimas; kampų numatytoji reikšmė; sustabdytas `_detail_m2` porinimas; sekami PDF su
kliento duomenimis; prod bandomoji paskyra; Vercel dev prisijungimas; mokamas bake-off / Codex auditas.
