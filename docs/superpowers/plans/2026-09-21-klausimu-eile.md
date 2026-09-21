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
