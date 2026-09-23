# Klausimų eilė, antras ratas — įgyvendinimo planas

> Spec: `docs/superpowers/specs/2026-09-23-klausimu-eile-2-design.md`. TDD, kiekviena dalis patikrinama
> ant tikro H ir naršyklėje PRIEŠ ataskaitą. Niekas nepushinama.

**Tikslas:** keturios steigėjo pastabos virsta elgsena: ribą programa priima pati; kontūrą pasiūlo net
kai plotas nesutampa, ir visada yra kelias be paspaudimo; angų matmenys taisomi; tekstai sako, kad plotai
iš lentelės.

## 1 dalis — juosta priima ribą pati

**Failai:** `backend/extractor/geometry_lane.py`, `backend/extractor/room_facts.py`,
`backend/extractor/project_questions.py`, `backend/tests/test_geometry_lane.py`,
`backend/tests/test_room_facts_perimeter_sum.py`, `backend/tests/fixtures_geometry_gate.json`.

- [ ] Testas: sintetinis planas be pertvaros → abi patalpos turi `_konturas.saltinis ==
  "padalinta_programos"`, `pagal in ("kampas","plotai")`, `menamos` po vieną, `_atvira_erdve` lieka,
  perimetrų suma ≈ bendro kontūro perimetras, plotai santykiu 12,6 : 9,0; `meta.ribos`.
- [ ] Įgyvendinti; `LANE_VERSION = 8`; antras paleidimas nieko nekeičia.
- [ ] Faktų sakinys „padalijau pats" (testas); ribos klausimo `why` (testas).
- [ ] Vartai: `fixtures_geometry_gate.json` H — 04/05 į `perimetrai_sudeti` (išmatuoti), tušti su įverčiu
  mažiau; gate žalias ant A/G/H. Commit.

## 2 dalis — kontūro pasiūlymas ir kelias be paspaudimo

**Failai:** `backend/extractor/vector_rooms.py`, `geometry_lane.py`, `room_facts.py`,
`project_questions.py`, `backend/api/room_outline.py`, testai; `frontend/src/lib/checkOverlay.js`,
`roomOutlineApi.js`, `questions.js`, `pages/PatikraQuestions.jsx`, `i18n/lt.json`, `en.json`.

- [ ] Testas `trace_vector_rooms`: patalpa, kurios kontūras nesutampa su lentele → `siulymai[nr]` su
  `taskas_pct` viduje; priežastis „sienos prie numerio uždaro …".
- [ ] Juosta: `_konturo_siulymas`; `meta.konturu_siulymai`. Faktai: `outline_proposal`. Klausimas:
  `proposed_outline`, `sentence`, `perimetras_dabar` (testas).
- [ ] API: `OutlineAt.pritarta` → `saltinis "pasiulyta"`; faktų sakinys (testas).
- [ ] Ekranas: pasiūlymas brėžinyje (checkOverlay be linijos — testas), „Tinka" / paspaudimas kitur /
  „Sienų ilgis ranka". Naršyklėje ant H kopijos. Commit.

## 3 dalis — angų matmenys

**Failai:** `frontend/src/components/questions/QuestionBodies.jsx`, `frontend/src/lib/questions.js` +
testas, `i18n`.

- [ ] Testas `openingsAnswer(project, items, picked, edits)`: pataisytas plotis/aukštis/rūšis nueina į
  `elementai`; nepataisyti — kaip buvo.
- [ ] `OpeningsBody`: laukeliai + rūšis + įspėjimas apie neįprastą plotį. Naršyklėje: 1,40 → 0,90. Commit.

## 4 dalis — tekstai, vartai, ataskaita

- [ ] `splitArea`, ribos `why`, nesutapimo priežastis; frontend testai, kurie pinasi prie senų tekstų.
- [ ] Visas backend `pytest`, `npm run test:units`, eslint, eval (H delta pasakoma), demo projektų
  perskaitymas (`scripts/apply_geometry_to_local_project.py` g, h, h-senas).
- [ ] Vykdymo žurnalas čia; atmintis; ataskaita steigėjui su atsakymais į 2, 3 ir 5 pastabas.
