# Geometrija iš brėžinio (Patikra v2, 1 dalis) — dizainas, 2026-09-17

> Sub-projektas 1 iš 3. Visas darbas €0: cached nuskaitymai (G, H, A–D fixtures), vektorinis PDF
> sluoksnis, jokių Vision paleidimų. Kiekvienas žingsnis patikrinamas testais ir skaičiais prieš
> rodant. Kiti sub-projektai: 2) Patikra ant peržiūros lango (Togal/Kreo stiliaus), 3) pigūs
> pataisymai (ryškios iškarpos, grindų dangos pasirinkimas). Jie gaus savo dizainą po šio.

## Tikslas

Patalpos perimetras ir kontūras turi būti **perskaityti iš brėžinio**, ne spėti:

- perimetras = **suma matmenų eilučių**, kurios parašytos prie šios patalpos sienų (bet kuriame to
  paties aukšto lape: išdėstymo planas, sienų dažymo planas, pertvarų planas);
- kontūras = patalpos riba iš vektorinių sienų užpildų (kur PDF vektorinis) arba iš esamos rastro
  juostos; kontūras naudojamas tik dviem dalykams: **priskirti** eilutes patalpai ir **patikrinti**
  sumą (kontūro ilgis × mastelis sutampa ±3 %);
- ko brėžinys nesako, laukas lieka **tuščias su priežastimi** ir pasiūlymu, kurį žmogus gali priimti
  („kontūro įvertis 20,4 m"), niekada ne tylus skaičius.

Sėkmės kriterijai (matuojami, prieš/po):

| kriterijus | dabar | tikslas |
|---|---|---|
| H: patalpos su iš eilučių perskaitytu perimetru | 0/11 | ≥ 9/11, kiekviena ±3 % nuo kontūro kontrolės |
| H: patalpos su kontūru iš brėžinio (ne bbox) | 0/11 | ≥ 9/11, plotas ±5 % nuo lentelės |
| G: perimetrai iš eilučių (esama juosta) | 7/9 | ≥ 7/9 (be regresijos), kontūrai ≥ 7/9 |
| A–D eval `--recompute` bendras nuokrypis | 9,91 % | ne blogiau |
| sintetinis (kvadrato) perimetras rodomas kaip faktas | taip | niekada: tuščia + priežastis + įvertis |
| testai | | kiekvienam vienetui; nuoseklumo scenarijus 54/54 |

Ne tikslai (YAGNI): naujo CV modelio mokymas; skenuotų rastrų segmentacija (lieka esama juosta);
durų/langų aptikimas; Patikros sąsaja (sub-projektas 2); mokami paleidimai.

## Kodėl taip (faktai iš 2026-09-17 tyrimo)

- H 1 lapas: 111 eilučių, mediana 0,8 m — baldų matmenys; **6 lapas („sienų dažymo planas") turi
  kiekvienos dažomos sienos ilgį** (17 patalpų dydžio eilučių). Esama juosta jų nenaudojo: patalpą
  randa tik pagal ploto užrašą (H neturi), lapų 1 ir 6 nelaiko tuo pačiu planu, poruoja tik
  stačiakampes patalpas.
- H sienos vektoriuose — 176 vienos spalvos užpildai; prototipas be derinimo 7/11 ±11 %.
- Esama rastro juosta ant G 7/9 ±5 %, perimetrai ±1 % su eilutėmis; ant H 0/11 (sėja nuo ploto
  užrašo; baldai kerta užpildymą).

## Architektūra: keturi vienetai, aiškios ribos

Visi `backend/extractor/`, gryni (bytes/dicts įeina, dicts išeina), be tinklo.

### 1. `room_locator.py` — kur lape yra kuri patalpa

- Įvestis: PDF baitai, patalpų sąrašas (nr, pavadinimas, plotas_m2, bbox_pct iš Vision), plano
  lapų numeriai.
- Išvestis per patalpą: `{"page": n, "cx": pct, "cy": pct, "saltinis": "zenkliukas" | "plotas_uzrasas" | "bbox"}`.
- Kaip: tekstiniame sluoksnyje randa **numerio ženkliukus** (1–2 skaitmenys, mažas šriftas, lapo
  brėžinio zonoje, ne lentelėje ir ne antraštėje; H: 11/11 rasta); jei nėra — ploto užrašas
  (esama `_plotas_uzrasas`); jei nėra — Vision bbox centras. Šaltinis įrašomas.
- Klaidos: du vienodi ženkliukai lape → renkasi tą, kuris arčiau Vision bbox; nė vieno → bbox.

### 2. `sheet_alignment.py` — kurie lapai yra tas pats planas

- Įvestis: PDF baitai, plano lapų numeriai (iš esamos klasifikacijos: floor_plan, ceiling_plan…).
- Išvestis: grupės `{bazinis_lapas: [lapai]}` ir kiekvienam lapui transformacija į bazinį
  (poslinkis + mastelio daugiklis; H lapai 1 ir 6 sutampa 1:1).
- Kaip: sienų užpildų sąjungos gaubtas ir centroidas per lapą; lapai su tuo pačiu gaubtu ±1 % —
  viena grupė; kitaip — bandoma sulygiuoti pagal gaubtus; nesulygiuojami lapai lieka atskiri.
  Papildo esamą `frame_groups` (kuris grupuoja pagal eilučių rėmus), jo nekeičia.

### 3. `vector_rooms.py` — kontūrai iš vektorinių sienų

- Įvestis: PDF baitai, lapas, patalpų vietos (1 vienetas), lentelės plotai, mastelis
  (`plan_dimensions` jau duoda `scale_m_per_pt`).
- Išvestis per patalpą: `polygon_pct` (display-frame, kaip visur), `polygon_source="vektoriniai_konturai"`,
  `_konturas {page, plotas_m2, perimetras_m, paklaida, sienos_uzpildai}`; arba nieko su priežastimi
  (`_konturas_priezastis`: "atviras planas", "nesutampa su lentele", "nėra vektorinių sienų").
- Kaip: užpildai vienos dominuojančios spalvos ir sienos formos (plonas × ilgas) → sienų sąjunga;
  **durų angos uždaromos išilgai sienų** (sienos galas pratęsiamas iki kito galo, kai tarpas ≤ 1,2 m
  ir kryptis sutampa), ne buferiu; laisvos erdvės veidai; veidas priskiriamas patalpai, kurios
  ženkliukas jame, jei plotas ±5 % nuo lentelės; veidas su keliais ženkliukais (atviras planas)
  dalijamas linija tarp ženkliukų taip, kad dalių plotai atitiktų lentelę ±5 %, kitaip lieka
  nepadalytas su priežastimi. Kai lapas ne vektorinis → esama `wall_outline` juosta, bet sėjama
  nuo 1 vieneto vietos (ne tik nuo ploto užrašo).
- Klaidos: bet koks nesutapimas → priežastis, ne spėjimas. Vision bbox stačiakampis niekada
  nebevadinamas kontūru (`polygon_source="synthesized_from_bbox"` lieka tik kaip vieta lape, ne
  kaip riba).

### 4. `dimension_sum.py` — perimetras sudedant eilutes

- Įvestis: patalpų kontūrai (3 vienetas, arba esami `polygon_pct` iš rastro juostos), matmenų
  eilutės su linijomis iš visų aukšto lapų (esama `read_dimension_strings`), lapų lygiavimas (2).
- Išvestis per patalpą: `_sienos: [{page, edge_pct, ilgis_m | null, eilutes: [{text, value_m, page}], kontrole_m, sutampa}]`,
  `perimetras_m` = Σ ilgis_m **tik kai kiekviena siena turi eilutę**; `perimetras_saltinis="matmenu_eilutes"`;
  kitaip `perimetras_m=null`, `_perimetras_priezastis` („2 iš 6 sienų be matmens"),
  `_perimetras_ivertis_m` = kontūro ilgis × mastelis, `_perimetras_ivertis_saltinis="konturas"`.
- Kaip: kontūras suprastinamas iki sienų (viršūnės su >20° posūkiu); eilutė priskiriama sienai,
  jei lygiagreti, ne toliau kaip 0,35 m nuo sienos (bet kuriame sulygiuotame lape) ir jos linijos
  tarpsnis dengia ≥ 60 % sienos arba siena ≥ 60 % tarpsnio (segmentuotos sienos sumuojamos);
  vienai sienai sumuojama; suma prieš kontūro kontrolę ±3 % → `sutampa`.
- Sąveika su esama juosta: stačiakampė pora (`apply_dimension_strings`) lieka pirma; šis vienetas
  eina po jos toms patalpoms, kurios liko `unmatched`.

### Integracija į pipeline ir kiekius

- `vision_call.py`: po eksplikacijos ir plotų juostų: 1 → 2 → 3 → esama eilučių pora → 4. Rezultatas
  rašomas į patalpas ir į `_meta.geometrija` (kiek patalpų iš kur).
- `universal_rules.calc_room_quantities`: kai `perimetras_m` null, skaičiuoja su
  `_perimetras_ivertis_m`, o eilutėse ir ledgeryje ta patalpa žymima „perimetras — įvertis
  (kontūras), nepatvirtintas"; kvadrato sintezė (`_perimetras_floor_applied`) lieka tik kai nėra
  nei eilučių, nei kontūro, ir tada irgi tik kaip įvertis su priežastimi.
- `/recompute-interior` ir `/api/recompute-quantities`: priima `perimetras_m` null + įvertį;
  žmogaus įrašytas perimetras (`perimetras_saltinis="user_override"`) visada laimi (jau taip).
- `room_facts.py`: perimetro faktas rodo sudėtas eilutes („4154 + 3977 + 2643 + 3735 = 14,51 m,
  6 psl.") su jų vietomis kaip įrodymais; kai null — „Perimetras: — (2 sienos be matmens);
  priimti kontūro įvertį 20,4 m" (Patikros sąsajos pakeitimas minimalus: tekstas ir mygtukas, tikra
  sąsaja — sub-projektas 2).

## Testavimas

- Vienetų testai su sintetiniais PDF (reportlab: sienų stačiakampiai, matmenų tekstai su
  linijomis, ženkliukai): ženkliukų paieška, lapų lygiavimas, veidai iš sienų, durų angų
  uždarymas, atviro plano dalijimas, eilučių priskyrimas sienoms ir suma, tuščias laukas su
  priežastimi. Jokių klientų duomenų testuose.
- Fixture testai (praleidžiami, kai PDF nėra): H 1+6 lapai — ≥ 9/11 perimetrų iš eilučių ±3 % nuo
  kontrolės, ≥ 9/11 kontūrų ±5 % nuo lentelės; G — esamos juostos rezultatas nesikeičia.
- Regresija: `eval_harness.py --totals-only --recompute` prieš/po; `test_no_import_alias_shadowing`;
  nuoseklumo scenarijus (54 patikros) prieš lokalų backend'ą.
- Rankinis patikrinimas naršyklėje: H demo projekto Patikros lapas — perimetro faktas rodo
  eilučių sumą su įrodymu; patalpa be matmens rodo tuščią lauką su įverčiu.

## Rizikos

- Vektoriniai lapai su sienomis kaip brūkšniavimu (ne užpildu) — 3 vienetas neranda sienų → rastro
  juosta; kriterijus vis tiek matuojamas.
- Suplotinti rastrai (iLovePDF) — be tekstinio sluoksnio nėra nei eilučių, nei ženkliukų: viskas
  lieka kaip dabar (Vision + įverčiai su priežastimis). Tai sąžiningai pasakoma sąsajoje.
- Eilučių priskyrimas ne tai sienai (gretimos patalpos siena) — kontūro kontrolė ±3 % gaudo;
  neatitikimas → tuščias laukas, ne klaidingas skaičius.
