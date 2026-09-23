# Klausimų eilė, antras ratas — steigėjo pastabos 2026-09-23

> Steigėjas perėjo klausimų ekraną ant H (`demo-objektas_h-senas`) ir paliko keturias pastabas. Visos
> pamatuotos ant tikro brėžinio prieš rašant šį dokumentą. Sprendimai čia; planas —
> `docs/superpowers/plans/2026-09-23-klausimu-eile-2.md`.

## Pastabos ir kas už jų

1. **„Paspaudus du kartus ant tambūro, patalpos 01 pasižymi 4 ir 5 patalpos — neaišku, kaip čia pažymėti."**
   Pamatuota: prie numerio 01 sienos uždaro tik 2,86 m² kišenę (lentelėje 4,48 m², −36 %), kairiau —
   39 m² lauko pusė be numerių, dešiniau — koridorius 03 ir bendra 04/05 erdvė. Klausimas „parodykite
   patalpą" be jokio pasiūlymo yra aklas: jis nežino, kur spausti, o kai pataiko ne ten, mato tik kitų
   patalpų kontūrus. Programa TURI pasiūlyti tai, ką rado (kišenę), pasakyti, kodėl pati nepriėmė, ir
   duoti kelią be paspaudimo — įrašyti sienų ilgį ranka.
2. **„O koks tau skirtumas, kur riba?"** — 04/05 riba sienų sumos nekeičia. Ką ji keičia H: 05 grindjuostės
   (perimetras 21,69 → 19,82 m: −2 m) ir 04 virtuvės plytelių juosta (0,6 m × perimetras: +1,1 m² plytelių,
   −1,1 m² dažymo). Sąmatos eilutės — pagal darbus, ne pagal patalpas. Vadinasi: klausti neverta, kai
   programa gali pasiūlyti pati; ribą ji priima pati, pasako, kur ir kodėl, ir leidžia pakeisti.
3. **„Jei lentelėje yra parašyti tikslūs matmenys, kodėl jie išvis bandomi perskaičiuoti?"** — jie
   neperskaičiuojami: plotas visada imamas iš lentelės. Kontūras reikalingas tik SIENŲ ILGIAMS, kurių
   lentelė neturi; jo plotas buvo rodomas kaip patikra, bet skaitėsi kaip konkuruojantis skaičius.
   Tekstai turi sakyti: „plotas iš lentelės; kontūro reikia sienoms; sutampa".
4. **„Durys 1,40 pločio nebus tikrai — turi būti galimybė pataisyti durų išmatavimus."** — angų
   klausime kiekvienos angos plotis, aukštis ir rūšis (durys / langas) turi būti taisomi vietoje; neįprastas
   plotis (vidaus durims > 1,2 m arba < 0,6 m) pasakomas iš anksto.
5. **„Ten, kur peržiūrėti visus kambarius, keitei kažką?"** — ne, tik keturi dalykai iš jo ankstesnių
   pastabų (juosta sako KODĖL niekas nepasikeitė; angų pločiai brėžinyje visada; ryški instrukcija ir gyva
   ribos linija; mygtukas „Klausimai"). Atsakoma ataskaitoje.

## Ko NEDAROME

- Naujos angų rūšies („anga be durų") variklyje — jis prašė taisyti matmenis, ne naujo tipo. Nuimta varnelė
  lieka atsakymu „tai ne durys".
- Trijų ir daugiau patalpų erdvių dalijimo — kaip ir anksčiau.
- Sienų ilgio „matavimo" iš kontūro kaip perskaityto skaičiaus — kontūro ilgis lieka įverčiu, kol jo
  nepatvirtina užrašyti matmenys arba žmogus.

## Sprendimai

### A. Bendros dviejų patalpų erdvės ribą programa priima pati (geometrijos juosta)

`geometry_lane.apply_geometry`: kiekvienai dviejų narių atvirai erdvei su tvirtomis vietomis ir lentelės
plotais kviečiamas `vector_rooms.propose_split`. Kai yra pasiūlymas („kampas" — per sienos galą, kur
abi dalys ±8 % nuo lentelės; kitaip „plotai" — pagal plotų santykį), abi patalpos gauna savo kontūrą:
`polygon_source = "vektoriniai_konturai"` (juostos, ne žmogaus — kitas paleidimas perdaro),
`_konturas = {…, menamos, su, saltinis: "padalinta_programos", pagal, riba_pct}`; `_atvira_erdve`
LIEKA (bendras kontūras rodomas punktyru, „Nubrėšiu pats" tebeveikia). Ką tik įrašytas dalies įvertis
išmetamas — sienas skaito `dimension_sum` kaip kiekvienam kontūrui: užrašyti ilgiai → perskaityta,
kitaip kontūro įvertis su priežastimi. Kai pasiūlymo nėra — viskas kaip iki šiol (įverčiai + klausimas
„Kur riba", kuriame liko tik „Nubrėšiu pats" kelias, o `why` sako, kad plotai iš lentelės ir sienų suma
nuo ribos nesikeičia). `meta.ribos` / `meta.ribos_nepasiulytos`. `LANE_VERSION` 7 → 8.

Faktų sakinys (`_fact_perimetras`, `saltinis == "padalinta_programos"`): „Bendrą erdvę su patalpa 05
padalijau pats — riba per sienos galą, kur su ja sutinka lentelės plotai (pagal plotų santykį); riba ne
siena, į perimetrą neįskaičiuota, sienų sumai įtakos neturi. Pakeisti: „Padalinti erdvę"."

Tikra H: 04 → 17,93 m perskaityta, 05 → 19,82 m; klausimas „Kur riba" dingsta; sienų ilgių klausime
lieka 01, 03, 07, 08. Pasekmė sąmatoje pamatuojama ir pasakoma ataskaitoje (grindjuostės, plytelių juosta).

### B. Kontūro pasiūlymas, kai sienos uždaro kitokį plotą nei lentelė

`vector_rooms._match.accept`: kai kontūras atmetamas dėl ploto nesutapimo, jis grąžinamas kaip
`siulymai[nr] = {polygon_pct, plotas_m2, perimetras_m, paklaida, sujungta, durys_m, page, taskas_pct}`
(`taskas_pct` — taškas kontūro viduje). `trace_vector_rooms` → `res["siulymai"]` (mažiausia paklaida per
durų ribas). Juosta rašo `_konturo_siulymas` (išmeta, kai kontūras rastas). Priežasties tekstas:
„sienos prie numerio uždaro 2,86 m², lentelėje 4,48 m²" (vietoj „nesutampa su lentele: …").

Faktai: `_perimeter_drawing` → `outline_proposal` (be kontūro). Klausimas `konturas`: elementas gauna
`proposed_outline` ir sakinį: „Prie numerio 01 sienos uždaro 2,86 m² (sienų 6,77 m), lentelėje 4,48 m²
(−36 %) — todėl kontūro pats nepriėmiau. Jei tai visa patalpa — „Tinka". Jei patalpa didesnė —
spustelėkite kitoje jos vietoje. Arba įrašykite sienų ilgį ranka." + `perimetras_dabar` (skaičius, su
kuriuo dabar skaičiuojama).

Ekranas: pasiūlymas piešiamas kaip ribos pasiūlymas (kontūras + numeris, be linijos); mygtukai
„Tinka" (POST `outline-at` su `taskas_pct` ir `pritarta: true` → `_konturas.saltinis = "pasiulyta"`,
sakinys „Kontūrą pasiūliau pagal sienas prie patalpos numerio — patvirtinote"), brėžinys lieka
paspaudimo režime („jei patalpa didesnė — spustelėkite kitur"), ir laukelis „Sienų ilgis ranka: [8,6] m
Įrašyti" (`perimetras_m` kaip įrašytas ranka). Nepavykusio paspaudimo priežastys lieka juostoje; 39 m²
atvejis sako „čia lauko pusė arba erdvė, bendra su kita patalpa".

### C. Angų matmenys taisomi klausime

`OpeningsBody`: prie kiekvienos angos — plotis (m), aukštis (m), rūšis (durys / langas); pakeitus,
elementas siunčiamas su pataisytais `plotis_mm / aukstis_mm / tipas`. Įspėjimas po anga, kai vidaus
durų plotis > 1,2 m arba < 0,6 m: „Durims 1,40 m — neįprastas plotis. Patikrinkite: gal tai anga be
durų, niša ar dvi durys." `openingsAnswer(project, items, picked, edits)` — gryna, testuojama.

### D. Tekstai

`splitArea` → „lentelėje {{table}} m² · kontūras {{area}} m²"; `why` ribos klausimui — „Plotus imu iš
lentelės; riba reikalinga tik sienų ilgiams paskirstyti — sienų suma nuo jos nesikeičia."; kontūro
nesutapimo priežastis — kaip B.


### E. „Spustelėkite kitoje jos vietoje" — paspaudimas kaimyno patalpoje (antra pastaba po pirmo rato)

Steigėjas: „paspaudus kitoje vietoje nieko negali padaryti, tik pasižymi kitas kambarys — kodėl negali papildyti?"
Pamatuota H: tambūro kišenė 2,86 m² per 1,0 m angą be durų jungiasi su koridoriaus 03 kontūru (10,76 m²,
lentelėje 10,12). Dizainerio riba tarp 01 ir 03 — menama. Sprendimas dviem lygiais:
- **Juosta pati** (`vector_rooms._match`): kai patalpos sienos uždaro MAŽIAU nei lentelė, o už angos be durų
  stovi kaimyno kontūras, su kuriuo lentelė sutinka, abi tampa viena erdve (`groups` su `kisene`), kurią juosta
  padalija savo riba — tik jei abi dalys lieka ±8 % nuo lentelės; kitaip kišenė lieka pasiūlymu, kaimynas
  nepaliestas. H: 01 → 4,31 m² (4,48), 03 → 9,73 (10,12), „plotai"; klausimas „Parodykite patalpą 01" dingsta.
  Žmogaus (ar rastrinės juostos) kontūrai perduodami skaitymui kaip `solved` — jie niekada nesiūlomi, nejungiami
  ir nedalijami; juostos SAVI kontūrai perskaitomi kiekvieną kartą (saugomas projektas gauna, ką juosta išmoko).
- **Paspaudimu** (`outline-at` → `status: "shared"`): kai vieta priklauso juostos nubrėžtam kaimynui, o šios
  patalpos sienos uždaro kišenę šalia — grąžinamas ribos pasiūlymas per sujungtą erdvę (`joined_space`), abu
  kontūrai + punktyras; „Tinka" (`pritarta`) pritaiko abiem (`padalinta`), „Nubrėšiu pats" — `split-space` su
  `su` pjauna sujungtą erdvę jo linija. Patalpos lape — pranešimas, kuris nukreipia į klausimų ekraną.

## Tikrinimas

1. Vienetų testai: juosta (sintetinis planas be pertvaros → padalyta, `pagal`, sienų suma = bendro
   kontūro), `vector_rooms` (pasiūlymas grąžinamas), faktai (sakiniai), klausimai (elementas su
   pasiūlymu; ribos klausimas tik be pasiūlymo), API (`pritarta`), frontend (`openingsAnswer` su
   pataisymais, `checkOverlay` pasiūlymas be linijos).
2. Geometrijos vartai ant tikrų A/G/H (`fixtures_geometry_gate.json` — 04/05 pereina į sudėtus).
3. Naršyklėje ant H kopijos: tambūro pasiūlymas → „Tinka" → sienos perskaitytos; angų 1,40 → 0,90 ir
   pridėta; ribos klausimo nebėra; pasekmės juosta ir atšaukimas. G — klausimai nepablogėjo.
4. Vartai: visas backend `pytest`, `npm run test:units`, eslint, eval (H OOS skaičiai pasikeis — pasakoma,
   kiek ir kodėl; nieko nederinta pagal sąmatą).
