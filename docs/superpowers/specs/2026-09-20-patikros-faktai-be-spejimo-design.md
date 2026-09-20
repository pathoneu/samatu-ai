# Patikros faktai be spėjimo — grindų danga, apdaila, ryškios iškarpos (sub-projektas 3)

2026-09-20. Trečias „Patikra v2" sub-projektas (pirmi du: `2026-09-17-geometrija-is-brezinio-design.md`,
`2026-09-19-patikra-ant-brezinio-design.md`). €0 — jokio Vision kvietimo.

## Kodėl

Steigėjo verdiktas po pirmo tikro Patikros naudojimo (2026-09-17): „pasirinkimai keisti, kai kur procentais…
lapai blurry… nuima labai mažai rankinio darbo". Po 1 ir 2 sub-projektų perimetras ir brėžinio pusė sutvarkyti;
dešinėje pusėje liko trys dalykai, išmatuoti 2026-09-20 ant vietinių `demo-objektas_g` / `demo-objektas_h`:

1. **Grindų danga nespėjama iš brėžinio, o iš paskirties.** Visose 20 patalpų faktas „Grindys" yra geltonas
   („Brėžinys nesako — parinkta pagal patalpos paskirtį… jei kitokia — pakeiskite paskirtį"). Abu projektai TURI
   grindų dangų planą su teksto sluoksniu:
   - H 7 lapas: dangos nubraižytos spalvotu raštu, o legendos eilutė parašyta TA PAČIA spalva
     (ruda „Grindys — …, eglutės raštas 98,37 m²", oranžinė / žalia / mėlyna — trys plytelių rūšys);
   - G 7 lapas: plytelių patalpose parašyta „plytelės … 60×60 cm … 3,95 m²", svetainėje „laminuota grindų
     danga 76,65 m²".
   Taisyklė pagal paskirtį klysta ten, kur brėžinys aiškus: H 01 (tambūras) plane — parketas, mes skaičiuojame
   plyteles; G 09 (techninė patalpa) plane — plytelės 6,96 m², mes skaičiuojame laminatą. Taisymas šiandien —
   keisti PASKIRTĮ, o tai keičia ir sienų, lubų taisykles.
   Variklyje `tile_floor_override` keičia tik plyteles: parketo plotas ir grindjuostės toliau eina iš paskirties
   (`rt_rules["floor"]`), todėl „plytelės" parketo patalpoje suskaičiuotų ABI dangas.
2. **Apdaila rašoma procentais arba klaidingai.** G: „Sienos: dažoma 92 %, plytelės 8 %". H 07/08: „Sienos:
   dažoma", nors sąmatoje tai patalpai 21,5 m² plytelių ir 2,75 m² dažymo.
3. **Faktų iškarpos neryškios.** `api/evidence.render_crop` atvaizduoja VISĄ lapą ≤ 160 dpi per poppler ir
   iškerpa; maža vieta (eksplikacijos eilutė, matmenų eilutės) išeina 180–260 px pločio. Ryškus brėžinys jau yra
   kairėje, bet miniatiūra ir didinimo langas — ne.

## Ką darome

### A. Ryškios iškarpos (backend, `api/evidence.py`)
`render_crop` atvaizduoja TIK prašomą stačiakampį per PDFium (`page.render(scale, crop=…)`) tokia raiška, kad
ilgoji kraštinė būtų ~`MAX_CROP_PX` (1600 px), bet ne mažiau nei prašytas dpi ir ne daugiau nei 600 dpi.
Viso lapo užklausa lieka kaip buvo (ribojama `MAX_PAGE_PX`). Talpyklos raktas gauna versiją, kad seni neryškūs
failai nebūtų rodomi. Poppler lieka atsarginis kelias, jei PDFium nepavyksta. API forma nesikeičia — frontend'o
keisti nereikia (didinimo langas jau prašo ryškių plytelių tuo pačiu endpoint'u).

### B. Apdaila kvadratais, kaip sąmatoje (backend, `room_facts._walls_description`)
„Sienos: dažoma 93,04 m², plytelės 5,86 m²; lubos: dažomos 37,86 m²" — tie patys skaičiai, kuriuos ši patalpa
deda į sąmatą (`walls_paintable_m2`, `plyteles_sienos_m2`, kitos apdailos — iš breakdown dalies × sienų ploto
tik jei variklis jas skaičiuoja; jei ne — pavadinimas be skaičiaus). Procentų nebelieka. Kai patalpa „neskaičiuojama"
pasirinkimu — kaip ir dabar rodomas perskaitymas, ne nulis.

### C. Grindų danga: skaitoma iš grindų plano + tiesioginis pasirinkimas
- **Variklis** (`universal_rules.calc_room_quantities`): naujas patalpos laukas `grindu_danga` ∈
  `plyteles | minksta | be_dangos`. Kai yra — jis vienas nustato ir plytelių plotą, ir minkštos dangos plotą,
  ir grindjuostes, ir išlyginamąjį. Kai nėra — elgsena identiška šiandienei (`tile_floor_override`, paskirtis).
  `plyteles_grindys_m2_override` (tikslus plytelių plotas) lieka viršesnis plytelių plotui.
- **Skaitytuvas** (`extractor/floor_coverings.py`, naujas, grynas): grindų dangų lape
  1. **užrašas patalpoje** — teksto eilutė su dangos žodžiu (plytel…, akmens mas… → plytelės; parket…, laminat…,
     laminuot…, vinil…, LVT, SPC, PVC, kilimin…, linole…, „grindų danga", „grindys –" → minkšta danga), kurios
     centras patenka į patalpos kontūrą; šalia esantis „X,XX m²" pridedamas kaip brėžinio užrašas;
  2. **rašto spalva = legendos spalva** — spalvota (ne juoda / pilka) legendos eilutė su dangos žodžiu ir tos
     pačios spalvos brūkšniai patalpoje (kontūre, o kai patalpa kontūro neturi — aplink jos numerį).
  Eilutės apie grindjuostes, siūles, klojimo pradžią, šildymą — ne dangos. Dvi skirtingų klasių dangos vienoje
  patalpoje → nieko netvirtinama (lieka klausimas). Nieko neradus → kaip šiandien (paskirtis), bet sakinys pasako,
  kas grindų plane parašyta apskritai.
- **Juosta**: `geometry_lane.apply_geometry` pabaigoje (jau turi vietas, kontūrus ir lapų sutapdinimą) kviečia
  skaitytuvą; rašo `grindu_danga`, `grindu_danga_saltinis = "grindu_planas"`, `_grindu_danga` (lapas, įrodymo
  rūšis, brėžinio tekstas, stačiakampis). Vartotojo pasirinkimo (`user_override`) neliečia. `_meta.geometrija.
  grindu_dangos` — kas perskaityta.
- **Faktas** (`room_facts._fact_grindys`): perskaityta → žalia eilutė „Grindų plane (7 psl.) šioje patalpoje
  parašyta: „plytelės … 3,95 m²"" / „…nubraižyta tokiu pat raštu kaip legendos eilutė „…"", šaltinio
  stačiakampis tame lape („Rodyti brėžinyje" nušoka ten); jo pasirinkimas → „Dangą pasirinkote jūs"; kitaip —
  geltona kaip dabar. `editable = {field: "grindu_danga", kind: "choice"}`.
- **UI** (`FactRow`): trys mygtukai — „Plytelės", „Parketas, laminatas ar vinilas", „Be dangos (betonas)" — ir
  pasekmės sakinys. Paskirties keisti nebereikia. Pakartotinis skaitymas jo pasirinkimą išlaiko
  (`mergeReextract`).

## Ko nedarome (sąmoningai)
- Plytelių ploto iš užrašo („3,95 m²") į kiekį nekeliame — tik cituojame; tam reikia atskiro sprendimo dėl
  inkarų (`_floor_anchors`) ir eval'o.
- „Toks pat raštas kaip gretimoje patalpoje" (G miegamieji be užrašo) — netvirtiname; G išmatuota, kad laminato
  ir plytelių raštas ten tos pačios spalvos ir pločio. Tos patalpos lieka „pagal paskirtį" su aiškesniu sakiniu.
- Mišrios patalpos (dvi dangos) ploto nedalijame.
- Pataisymo pasekmė / „jūsų" ženkliukas / atšaukimas — 2 sub-projekto 2 pjūvis.
- H „tambūras" sienų taisyklė (nedažomos) — atskiras klausimas, ne šio pjūvio.

## Tikrinimas
- TDD: sintetiniai PDF (reportlab) abiem įrodymo rūšims + neigiami atvejai (grindjuosčių legenda, juodas
  tekstas, dvi klasės); variklio testai (`grindu_danga` × trys reikšmės, nulis pokyčio be lauko); fakto testai;
  iškarpos testas (maža vieta ≥ 900 px ilgąja kraštine).
- Tikri brėžiniai: fixture vartai `fixtures_geometry_gate.json` papildomi — H: 11/11 dangų (01 → minkšta),
  G: 6 perskaitytos (09 → plytelės), likusios neperskaitytos.
- Eval (`--totals-only --recompute --geometry`): antraštė nepablogėja; eilutės ±10 % G/H/korpusas ne mažiau nei
  15,0 / 29,2 / 24,3 %.
- Naršyklė (vietinis `demo-objektas_h`, `demo-objektas_g`): faktas žalias su brėžinio citata, „Rodyti brėžinyje"
  nušoka į grindų planą, pasirinkimas perskaičiuoja sąmatą, apdaila be procentų, iškarpos ryškios; konsolė švari.
