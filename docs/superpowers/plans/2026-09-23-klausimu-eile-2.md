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

---

## Vykdymo žurnalas (2026-09-23)

Viskas LOKALIAI ant `viewer-rebuild`, nepushinta. Commit'ai: 971e750 (spec + planas), aa1902d (1 dalis),
9686369 (2 ir 3 dalys), žurnalo commit'as.

**1 dalis — juosta priima ribą pati.** `geometry_lane._divide_shared_spaces`: kiekvienai dviejų narių
atvirai erdvei su tvirtomis vietomis ir lentelės plotais — `propose_split`; abi patalpos gauna kontūrą
(`vektoriniai_konturai`, `_konturas.saltinis = padalinta_programos`, `menamos`, `su`, `pagal`, `riba_pct`),
`_atvira_erdve` lieka, ką tik įrašytas dalies įvertis išmetamas — sienas skaito `dimension_sum`. Faktų sakinys
„Bendrą erdvę su patalpa 05 padalijau pats — riba per sienos galą… sienų sumai įtakos neturi. Pakeisti galite čia";
`outline.riba = "programos"` → patalpos lape mygtukas „Padalinti erdvę" lieka perbraižymui. Ribos klausimas
lieka tik be pasiūlymo, jo `why`: plotai iš lentelės, riba tik sienų ilgiams paskirstyti. `LANE_VERSION` 8.
Sintetinis planas be pertvaros: padalyta „plotai", abiejų perimetrų suma = bendro kontūro. Tikras H: „kampas"
ties x = 0,625 → 04 17,93 m PERSKAITYTA (350 + 800 + 350 + 1000 + 6975 + 3643 + 1170; buvo įvertis 16,08),
05 19,82 m kontūro įvertis (1 iš 6 sienų be matmens; buvo 21,69); 04 gauna 5 angas, 05 — 3. Klausimų H:
5 → 3 (dingo „Kur riba"; sienų ilgių klausime liko 01, 03, 05, 07, 08 — po tambūro 4). Vartų JSON: 04 į
sudėtus, `ribos` tikrinamos, `min_tusti` 5 → 4, `angu_nera` tik 01. G ir A nepakito (atvirų erdvių nėra).

**2 dalis — kontūro pasiūlymas.** `vector_rooms._match`: atmestas veidas → `proposals` (5-a grąžinama
reikšmė; `outline_at` išpakuoja 5), priežastis „sienos prie numerio uždaro X m², lentelėje Y m²";
`trace_vector_rooms` → `siulymai` (mažiausia paklaida). Juosta: `_konturo_siulymas` (+ `plotas_uzrasas_m2`),
`meta.konturu_siulymai`; išmetamas, kai kontūras rastas ar patikimas. Faktai: `outline_proposal`. Klausimas:
`proposed_outline`, `sentence` („Prie numerio 01 sienos uždaro 2,86 m² (sienų 6,77 m), lentelėje 4,48 m² (−36 %)
— todėl kontūro pats nepriėmiau…"), `perimetras_dabar`. API: `OutlineAt.pritarta` → `saltinis = pasiulyta`
(sakinys „Kontūrą pasiūliau pagal sienas prie patalpos numerio — patvirtinote"), `_konturo_siulymas` tarp
geometrijos raktų (frontend'e taip pat). Ekranas: `OutlineBody` — sakinys, „Tinka — šis kontūras" (tas pats
`outline-at` taške `taskas_pct` su `pritarta`), „jei patalpa didesnė — spustelėkite kitur", laukelis „Sienų
ilgis, m" + „Įrašyti" (`perimetras_m` kaip įrašytas ranka; santrauka `answeredPerimeterTyped`); pasiūlymas
piešiamas punktyru (checkOverlay be linijos, brėžinys atsidaro ant jo), juosta prie brėžinio sako, ką daryti;
„lauko pusė" pranešimas 39 m² atvejui. Naršyklėje ant H kopijos: „Tinka" → 01 kontūras 2,86 m², sienos
6,85 m perskaitytos (600 + 996 + 1140 + 690 + 1596 + 1140 + 690), juosta „Nė vienas sąmatos kiekis
nepasikeitė" (tambūro sienos nedažomos, grindjuostės praleistos — teisinga); atšaukimas grąžina pasiūlymą.

**3 dalis — angų matmenys.** `OpeningsBody`: prie kiekvienos angos rūšis (durys / langas), plotis × aukštis
(m); vidaus durims > 1,2 m ar < 0,6 m — įspėjimas po anga; `openingsAnswer(project, items, picked, edits)`.
Naršyklėje: 08 anga 1,40 → 0,90, „Pridėti pažymėtas (6)" → 16 eilučių, angokraščiai 70,00 → 100,40 m (su
1,40 buvo 100,9); DB: 08 `duris 900 × 2100`, `_is_sienu_angos: "09"`.

**4 dalis — tekstai ir vartai.** `splitArea` → „lentelėje X m² · kontūras Y m²"; angų `why` — „plotį, aukštį
ir rūšį galite pataisyti čia pat"; daugiskaita `readNote`. Vartai: frontend `npm run test:units` 768 / 768,
eslint švarus paliestiems failams, geometrijos vartai 3 passed (A, G, H), visas backend `pytest` 3722 passed / 3 skipped per 5 min 3 s (buvo 3715 — +7 šio rato testai),
eval nepakito, išskyrus vieną H skaičių: bendra H suma 463,52 → 462,35 m² (paklaida 12,27 → 11,98 %) — virtuvės plytelių juosta prie ilgesnio 04 perimetro; in-sample 9,83 %, OOS 7,06 %, eilutės ±10 % G / H / korpusas 20,0 / 29,2 / 24,8 % nepakito; `baseline_multi.json` kitaip identiškas rytiniam paleidimui. Demo projektai perskaityti nauja juosta (`scripts/apply_geometry_to_local_project.py`):
`demo-objektas_h-senas` — 04 17,93 perskaityta / 05 19,82, tambūro pasiūlymas; `demo-objektas_h` — jo paties
ranka brėžta riba ir parodytas tambūras nepaliesti; `demo-objektas_g` — be pokyčių. Bandomoji kopija
`test-klausimai2-h` ištrinta.

**5 dalis — paspaudimas kaimyno patalpoje (po pirmo rato, tą pačią dieną).** Steigėjas: „jei patalpa
didesnė — spustelėkite kitur" nieko neduoda, tik pažymi 03. Pamatuota: tambūro kišenė 2,86 m² per 1,0 m angą
be durų jungiasi su koridoriaus 03 kontūru (10,76 m², lentelėje 10,12) — riba menama. Padaryta: (a)
`_propose_cut` (ribos paieška ant BET KOKIO veido), `propose_split` / `split_space` / `_space_to_divide` su
`face_pct`; (b) `_match`: kišenė + kaimyno veidas per angą → viena erdvė (`groups` su `kisene`), kai abi dalys
±8 % nuo lentelės — H: 01 4,31 m² / 03 9,73 m² („plotai"), klausimas „Parodykite patalpą 01" dingsta (šviežias H:
5 → 3 klausimai: aukštis, 5 sienų ilgiai su siūlymais, 6 angos); (c) `trace_vector_rooms(solved_pct=…)` —
žmogaus / rastrinės juostos kontūrai perduodami kaip `solved` (niekada nesiūlomi, nejungiami, nedalijami; testas),
juostos SAVI kontūrai perskaitomi kiekvieną kartą; (d) `joined_space` + `outline-at` → `status: "shared"`
(abu kontūrai, punktyras, `su`), `pritarta` → `_divided`, `split-space` su `su`; ekrane — kortelė „Čia patalpa
03 — sienos jos nuo 01 neskiria… Siūlau ribą pagal lentelės plotus" su „Tinka" / „Nubrėšiu pats" / „Atgal",
patalpos lape — pranešimas (`outlineShared`). Sintetinis planas `pocket_and_room` (1×3 m kišenė, 5×3 m
kambarys, 1,0 m anga, 7 matmenų eilutės — mažiau nei 5 eilutės lapui mastelio neduoda). Klaida, rasta vartuose:
sweep'o nutraukimas skaičiavo `solved` dvigubai → A prarado 101 (antras durų limitas nebevykdytas) — pataisyta,
A vėl 11 kontūrų. Vartų JSON H: `ribos` [[01, 03], [04, 05]], `angu_nera` []. Demo perskaityti dar kartą: jo
h-senas ir demo-objektas_h (01 „pasiulyta" / „parodyta", 03 jo skaičius) nepaliesti; G 03 kontūras persiskaitė
(8,3 → 7,96 m įvertis). Vartai: geometrijos 3 passed, backend 3728 passed / 3 skipped, frontend 769 / 769, eslint
švarus, eval nepakito, išskyrus H bendrą sumą 462,35 → 454,09 m² (paklaida 11,98 → 9,98 %) — koridoriaus sienos be tambūro juostos; in-sample 9,83 %, OOS 7,06 %, eilutės nepakito.

**Sąmatos palyginimas su jo sąmata (H, `demo-objektas_h-senas` po jo atsakymų; `row_scorecard`):** jo 35
eilutės, 24 su kiekiu; ±10 % — 6, ±25 % — 2, toli — 7, nėra — 9. Sutampa: GKP lubos 136,37 / 137,71 m²,
LED nišos 30,37 / 33,19 m, WC rėmai 2 / 2, praustuvų potinkinės 2 / 2, dėžutės 2 / 2. Toli: Rotband 94 /
169 m², beapvadinių durų angos 18,2 / 40,9 m, angokraščiai 100,3 / 63,2 m (prieš jo 6 pridėtas duris buvo
70,0), šviestuvai 35 / 20, difuzoriai 10 / 9 (+2 plyšiniai), apdirbimas 40 / 27, potinkinės dušo/vonios 3 / 2.
Arti: dažymas 457 / 413 m² (+11 %), kampai 466 / 413 m (+13 %). Nėra: pertvaros, magnetinių profilių karkasas,
bortelis LED nišoje, nišos pertvarose, langų sandarinimas, betonavimas prie langų. Hipotezė iš skaičių:
jo angokraščiai (63,2) = langai + lauko durys + kelios vidaus durys su apvadais, o beapvadinės vidaus durys
eina į atskirą eilutę (40,9 m = ~8 × (2 × 2,1 + 0,8)); mes visas angas dedame į angokraščius — tai jo
sprendimas (vidaus durų angokraščių konvencija), ne mano.

**Kas nepadaryta sąmoningai:** naujos angų rūšies („anga be durų") variklyje nėra — nuimta varnelė arba
pataisytas plotis; H 04 (5 angos sienose vs 2 langai + paslėptos durys) ir 09 lieka „pažiūrėkite patys".
