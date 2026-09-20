# Angos iš sienų — durys ir langai, kuriuos rodo pats sienų brėžinys

2026-09-20. €0. Steigėjo nurodymas: „pradėk nemokamus be mano sprendimo".

## Kodėl
Faktas „Durys ir langai" šiandien sako: „Brėžinys jų vietos nenurodo, todėl pažymėti negaliu — perskaičiuokite
patalpoje." Tai vienintelis faktas be jokio įrodymo brėžinyje, ir jo skaičius ateina tik iš Vision.
Išmatuota 2026-09-20 ant vietinių `demo-objektas_h` / `demo-objektas_g`:
- sienų masyvas (tas pats, iš kurio braižomi kontūrai) jau žino kiekvieną angą: H — 25 angos, G — 18; tarp
  patalpų 0,77–1,40 m (durys, perėjimai), į lauką 0,64–2,84 m (langai, įėjimo durys);
- H: Vision duris surašė tik koridoriui (5 + 2 paslėptos), o patalpoms 06, 07, 10, 11 — NĖ VIENŲ, nors sienose
  jų durys aiškios (0,77 / 0,80 / 1,18 / 0,87 m). Tų patalpų sienų plotas ir grindjuostės skaičiuojami be durų
  atėmimo. G: svetainei 3 durys, sienose — 5 + įėjimas;
- Patikroje durų PRIDĖTI negalima, jei Vision patalpoje nerado nė vienų: žingsniuoklis (+/−) keičia tik jau
  esamas eilutes.

## Ką darome (kiekių logikos nekeičiame — kiekiai keičiasi tik jam paspaudus)
1. **`vector_rooms`** — kiekvienai išspręstai patalpai grąžina `angos`: `{plotis_m, storis_m, line_pct, i}`;
   `i` = kitos patalpos nr | `"vidus"` (patalpa be savo kontūro) | `"laukas"`. Anga tarp dviejų TOS PAČIOS
   patalpos dalių (sujungti veidai) — ne anga. Skaičiuojama vieną kartą, plačiausiu durų limitu, visoms
   patalpoms, išspręstoms bet kuriame praėjime.
2. **Juosta** rašo `_angos_sienose` patalpoms su vektoriniu kontūru (dingus — nuima); `LANE_VERSION = 4`
   (išsaugoti projektai gauna tai per nemokamą perskaitymą).
3. **Faktas „Durys ir langai"**: `openings` (brėžiniui) ir sakinys, kuris SUTIKRINA: kiek durų / langų
   suskaičiuota plane ir kiek angų rasta sienose (į kurią patalpą, kokio pločio). Sutampa → „perskaityta" su
   vietomis brėžinyje. Nesutampa → geltona eilutė, pasakanti, ko trūksta („Sienose radau angą į patalpą 03
   (0,77 m), o durų šioje patalpoje nesuskaičiuota"), ir `suggestions` — ką pridėti vienu paspaudimu.
4. **Patikra**: angos nupieštos ant kontūro (mėlyna atkarpa skersai angos + plotis); redagavime — „+ Durys",
   „+ Langas" ir pasiūlymai iš sienų („Pridėti duris — anga 0,77 m į 03"). Pridėtos durys gauna standartinį
   aukštį 2,10 m ir plotį pagal angą (artimiausias 10 cm), pažymėtos kaip jo (`_angos_user_at`) — toliau veikia
   esamas kelias: perskaičiavimas, pasekmės juosta, „Atšaukti".

## Ko nedarome
- Automatiškai durų į kiekius nededame (kiekvienos angos atėmimas abiejose patalpose — skaičiavimo konvencija;
  be jo patvirtinimo jos nekeičiame). Atskirai išmatuosime, ką tai duotų eval'e, ir parodysime jam.
- Durų / lango atskyrimo lauko sienoje (įėjimo durys ir siauras langas atrodo vienodai) — sakinys sako „anga į
  lauką", ne „langas".
- Atviros erdvės narių (bendras kontūras) ir patalpų be vektorinio kontūro.

## Tikrinimas
TDD ant sintetinio plano (`two_rooms`: 0,9 m durys tarp patalpų, 0,9 m durys į lauką); tikrų brėžinių vartai
(H: 06 → [03, laukas], 07 → [03], 10 → [09]; G: 03 → [02], 05 → [01], 06 → [01]); faktų testai; frontend
units; naršyklė (H 06: geltona eilutė → „Pridėti duris" → pasekmės juosta → „Atšaukti"); eval nepaliestas.

## Pataisos vykdant (2026-09-20)
- **Ne tik vektoriniai kontūrai.** `_angos_sienose` gauna kiekviena patalpa su PATIKIMU kontūru (vektorinis,
  rastrinės juostos `sienu_konturas`, žmogaus `corrected`/`manual`): G brėžinyje visi kontūrai rastriniai, o
  sienų masyvas tas pats. Skaitomas VIENAS plano lapas (tas, kuriame daugiausia dar neskaitytų patalpų kontūrų),
  ant jo per `sutapdinimas` užklojami visi to plano patikimi kontūrai; rezultatas grąžinamas į pačios patalpos
  kontūro lapo koordinates (`_angos_sienose.page` = kontūro lapas) — Patikra piešia kontūrą ir angas kartu.
- **Kas už angos.** Taškas priklauso kontūrui, kuriame guli GILIAUSIAI; jei nė viename — artimiausiam per
  `FOREIGN_OUTLINE_TOL_PT` (svetimas kontūras stovi keli taškai nuo sienos). Dvi angos pusės yra ta pati patalpa
  tik kai abi tikrai jos viduje; kitaip artimesnė pusė pasilieka patalpą, kita ieškoma be jos (6 cm pertvara
  1:100 yra plonesnė už toleranciją).
- **Faktas lygina tik BENDRĄ skaičių** (įėjimo durys — irgi anga į lauką). Sienose daugiau → geltona eilutė;
  sienose mažiau → be pavojaus signalo (sienos rodo ne viską: G 09 durų masyve nėra). Pasiūlymai — tik kai
  kitaip suprasti negalima (0 durų ir yra anga į patalpą; 0 langų ir yra anga į lauką).
- **Žinomos ribos.** G fikstūros 5 ir 6 lapai su kitais nesusitapdina (sienų sutapimas 0,89 ir 0,24 — planas
  6 lape pastumtas, o sienų dėžė kita), todėl ten kaimynas lieka „gretima patalpa"; atviros erdvės nariai ir
  patalpos be kontūro angų neturi. Tai — „geometrijos ribų" darbo dalis, ne šio.
