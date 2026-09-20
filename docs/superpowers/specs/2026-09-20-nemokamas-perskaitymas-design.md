# Nemokamas perskaitymas išsaugotam projektui (be Vision)

2026-09-20. €0. Steigėjo nurodymas: „pradėk nemokamus be mano sprendimo".

## Kodėl
Geometrijos juosta (kontūrai iš vektorių, perimetrai iš užrašytų matmenų, grindų dangos iš grindų plano —
sub-projektai 1–3) veikia TIK pilno nuskaitymo metu (`vision_call` 2.44d žingsnis, €2–4 už projektą). Projektas,
perskaitytas anksčiau, jos rezultatų neturi: atidarius jį Patikroje matyti tas pats, kuo steigėjas skundėsi
2026-09-17 (spėti perimetrai, dėžučių kontūrai, danga pagal paskirtį). Vienintelis kelias šiandien — mokamas
„Perskaityti iš naujo" arba `scripts/apply_geometry_to_local_project.py`, kuris veikia tik su localhost.
Juostai Vision nereikia: jai užtenka saugykloje esančio PDF ir išsaugotų patalpų.

## Ką darome
- **Backend** `api/free_reread.py`:
  - `GET /api/projects/{id}/free-reread` → `{available, needed, versija, projekto_versija, reason}` — pigu (PDF
    buvimas saugykloje + `_meta.geometrija.versija`), be PDF skaitymo;
  - `POST /api/projects/{id}/free-reread` → paleidžia `apply_geometry` ant projekto KOPIJOS ir grąžina
    `{status, lane, patalpos, _meta, santrauka}`. Serveris NIEKO neišsaugo: suliejimas su jo pataisymais ir
    eilučių perstatymas lieka tame pačiame kelyje, kuriuo eina mokamas perskaitymas ir kiekvienas patalpos
    pataisymas (`mergeReextractRooms` → `/recompute-interior` → `mergeDarbuSarasasEdits` → `updateProject`).
  - autentifikacija + savininko filtras kaip `room_facts`; vienu metu vienas perskaitymas projektui (409);
    bendras dažnio ribotuvas; juosta niekada nemeta išimties, PDF nėra → 404 su aiškiu sakiniu.
- `geometry_lane.LANE_VERSION` (šiandien 3: 1 — geometrija, 2 — vietos Patikrai, 3 — grindų dangos) rašoma į
  `_meta.geometrija.versija`; „needed" = projekto versija mažesnė už dabartinę.
- **Frontend**: `lib/freeReread.js` (`mergeFreeReread` — gryna: patalpos per `mergeReextractRooms`, t. y. jo
  patikrintos patalpos ir jo įrašyti faktai lieka, skirtumai užrašomi į `_reread_diff`; `runFreeReread` —
  užklausa + eilučių perstatymas; nepavykus perstatyti NIEKAS neišsaugoma) ir `FreeRereadBanner` Patikroje bei
  projekto puslapyje: „Šį brėžinį galima perskaityti tiksliau — nemokamai…" → „Perskaityti nemokamai" → esamas
  `RereadDiffBanner` parodo, kas pasikeitė. `factDiff` papildomas grindų danga.

## Ko nedarome
Automatinio paleidimo be jo paspaudimo (perskaitymas keičia kiekius — tai įvykis, kurį jis turi matyti);
masinio admin veiksmo visiems projektams; patikrintų patalpų keitimo.

## Tikrinimas
Backend testai (statusas, savininkas, PDF nėra, serveris neišsaugo, lygiagretus 409, juostos klaida → 200 su
`lane: failed` ir nepakeistomis patalpomis); frontend units (`mergeFreeReread`: patikrinta patalpa lieka, jo
perimetras lieka, danga atsiranda ir patenka į skirtumą); naršyklė: senas H blob'as (2026-09-19 momentinė
kopija) kaip atskiras vietinis projektas → juosta → paspaudimas → kontūrai, sudėti perimetrai, dangos, skirtumų
juosta; konsolė švari. Eval neliečiamas (kiekių logika nekeičiama).
