# Patikra ant brėžinio (Patikra v2, 2 dalis) — dizainas, 2026-09-19

> Sub-projektas 2 iš 3. €0: tik frontend'as ir deterministinis backend'as, jokių Vision paleidimų.
> Remiasi 1 dalimi (`2026-09-17-geometrija-is-brezinio-design.md`): sienų tikslumo kontūrai,
> `_sienos` su perskaitytomis eilutėmis, atviros erdvės, tikslūs lapų masteliai jau yra duomenyse.
> Kiekvienas žingsnis tikrinamas testais IR naršyklėje ant `demo-objektas_h` / `demo-objektas_g`
> prieš rodant.

## Kodėl

Steigėjo verdiktas po pirmo tikro paleidimo (2026-09-17): „brėžinyje sunkiai matosi kas pažymėta,
patys brėžinio lapai ir kairėje ir paspaudus ant padidinimo blurry, kai kur net nematau pažymėjimų…
vos ne gaunasi, kad žmogus pats skaičiuoja". Tyrimas tą pačią dieną: lyderiai (Togal, Kreo) viską
daro ANT brėžinio — kontūrai ant lapo, sąrašas šone sinchronizuotas su brėžiniu; patikra greitesnė
už rankinį darbą tik kai šaltinis matomas šalia reikšmės ir yra įskaitomas.

Šiandien Patikros kairė pusė yra serverio rastro iškarpa (110–160 dpi, iki 1600 px): neryški, o
„Padidinti lapą" atidaro tą patį rastrą. Tikras peržiūros langas (EmbedPDF/PDFium — ryškus bet
kokiu masteliu) yra tik 1 žingsnyje „Brėžinys".

## Tikslas (ši dalis — 1 pjūvis)

Patikros kairėje — **tikras peržiūros langas**, o ant jo tai, ką programa perskaitė apie šią patalpą:

1. patalpos **kontūras** (ryškus, ant tikrų sienų), atvirai erdvei — bendras kontūras punktyru;
2. **sienos su skaičiais**: kiekviena kontūro siena nuspalvinta pagal tai, iš kur jos ilgis —
   perskaityta plane (su tuo skaičiumi prie sienos), paimta nuo tokios pat priešingos sienos,
   trumpa atkarpa iš kontūro, **be matmens** (raudona) — ir pažymėtos pačios matmenų eilutės
   tame lape, kuriame jos užrašytos;
3. **sinchronizacija**: užvedus/paspaudus faktą dešinėje, brėžinys nušoka į to fakto lapą ir vietą
   (perimetras → sienų dažymo planas, plotas → eksplikacija…); „Į patalpą" grąžina prie kontūro;
4. iškarpų miniatiūros faktuose lieka (greitas žvilgsnis), bet paspaudus — ne rastro dialogas, o
   tas pats ryškus langas nušoka į vietą;
5. mastelis statuso juostoje — tikslus iš matmenų linijų („1:115"), ne „nekalibruotas".

Sėkmės kriterijai (tikrinami naršyklėje ant H):

| kriterijus | dabar | tikslas |
|---|---|---|
| kairės pusės ryškumas priartinus iki vienos patalpos | rastras 160 dpi, tekstas neįskaitomas | vektorinis, 1 mm tekstas įskaitomas |
| patalpos su matomu kontūru ant brėžinio (H) | 8/11 (nuo 1 dalies), bet ant rastro | 8/11 ant tikro lapo + 2 atviros erdvės nariams bendras kontūras + 01 ženkliukas |
| perimetro faktas parodo, KURIE skaičiai sudėti | tik sakinys | kiekviena siena nuspalvinta, skaičius prie jos, eilutės pažymėtos 6 lape |
| fakto paspaudimas → vieta brėžinyje | atidaro rastro dialogą | tas pats langas nušoka į lapą ir vietą < 1 s |
| mastelis H | „nekalibruotas" | „1:115 (iš brėžinio matmenų)" |
| regresijos | | frontend 709+ testai, eslint, backend rinkinys, Patikros srautas (priimti / pataisyti / kitas kambarys) veikia kaip veikė |

Ne tikslai (kiti pjūviai, kiekvienas su savo planu): kontūro viršūnių tempimas Patikroje (yra
1 žingsnyje „Taisyti zoną"; sujungimas — 2 pjūvis kartu su „kontūrą pataisius sienos perskaitomos
iš naujo"); pataisymo pasekmių juosta, ženkliukas „jūsų", undo; faktų stulpeliai per visas
patalpas; grindų dangos skaitymas iš grindų plano; apdaila be procentų (3 sub-projektas).

## Architektūra

### Backend (mažai)

- `dimension_sum`: kiekviena `_sienos[i].eilutes[j]` gauna `line_pct` — tos eilutės matmens linijos
  atkarpą JOS lape (lapo dalimis), kad brėžinyje būtų galima pažymėti pačius perskaitytus skaičius.
- `geometry_lane`: `_meta.geometrija.sutapdinimas` = `{lapas: {base, k, kx, ky, dx_pct, dy_pct}}` — kaip to paties
  plano lapai gula vienas ant kito (H 6 lapas pastumtas 2 pt), kad kontūrą būtų galima parodyti ir
  tame lape, kuriame užrašyti skaičiai.
- `room_facts`: perimetro faktas papildomai neša `walls` (iš `_sienos`: `edge_pct`, `ilgis_m`,
  `saltinis`, `kontrole_m`, `eilutes[{text, page, line_pct}]`) ir `outline` (`page`, `polygon_pct`,
  `open_space` kai patalpa — atviros erdvės narė). Kiti faktai nesikeičia: jų `source.page` +
  `source.rect_pct` jau yra.

### Frontend

- `lib/checkOverlay.js` (grynos funkcijos, testuojamos): iš patalpos, faktų ir `sutapdinimas` sudaro
  vieno LAPO sluoksnio duomenis — kontūro taškai, sienų atkarpos su būsena ir etikete, eilučių
  linijos, fakto rėmelis; lapų perkėlimas (`mapPct`); fokusavimo stačiakampis (`focusRectFor`).
- `components/viewer/CheckLayer.jsx`: SVG sluoksnis viename lape (kaip `RoomZoneLayer`), piešia tai,
  ką davė `checkOverlay`. Spalvos — semantinės (perskaityta / pasiskolinta / iš kontūro / nėra), ne
  temos akcentas; etiketės pastovaus ekrano dydžio.
- `TakeoffViewer`: naujas režimas `check={...}` — be matavimo įrankių ir miniatiūrų, su
  „Į patalpą" / „Visas lapas"; `focus={page, rect_pct, nonce}` → `scrollToPage` + `zoomToArea`.
  1 žingsnio elgsena nesikeičia (`check` nepaduotas → viskas kaip buvo).
- `components/roomsheet/RoomDrawingPane.jsx`: Patikros kairė pusė — užkrauna PDF (`pdfStore`),
  laiko vieną peržiūros lango egzempliorių per visas patalpas, perduoda `check` ir `focus`. Jei PDF
  nepasiekiamas — rodo esamą `RoomPlanPane` (rastras lieka kaip atsarginis kelias, ne kaip norma).
- `RoomSheet.jsx`: `RoomPlanPane` → `RoomDrawingPane`; fakto užvedimas/paspaudimas ir iškarpos
  paspaudimas valdo `focus`.
- `InteriorWorkspace`: `laneScales` ima ir `_meta.geometrija.masteliai`, kai porų juosta mastelio
  nedavė.

### Duomenų srautas

`fetchRoomFacts` → faktai (su `walls`, `outline`) → `checkOverlay.build(room, facts, lapai, activeFactKey)`
→ `{byPage: {lapas: {...}}, focus}` → `TakeoffViewer check/focus` → `CheckLayer` kiekviename lape.
Jokios matematikos frontend'e: ilgiai, būsenos ir sumos ateina iš backend'o.

## Klaidos ir ribos

- Nėra PDF / variklis neužsikrauna → `RoomPlanPane` (kaip dabar) ir viena eilutė kodėl.
- Patalpa be kontūro (H 01): ženkliukas jos vietoje + sakinys, kodėl kontūro nėra (iš
  `_konturo_priezastis`); atviros erdvės narė — bendras kontūras punktyru.
- Pasukti lapai: sluoksnis naudoja tą patį pasukimo apvalkalą kaip `RoomZoneLayer` (display-space
  dalys) — jokios savos pasukimo matematikos.
- Mobilus (< 768 px): lieka rastro `RoomPlanPane` (peržiūros langas ten ir 1 žingsnyje nerodomas).

## Testavimas

- Backend: `line_pct` ir `lapai` vienetų testai ant sintetinių lapų; perimetro fakto `walls` /
  `outline`; fixture vartai papildomi (H: kiekviena perskaityta eilutė turi `line_pct` 6 lape).
- Frontend: `checkOverlay.test.js` (lapų perkėlimas, sienų būsenos, fokusavimo stačiakampis, atvira
  erdvė, patalpa be kontūro); esami 709 testai; eslint.
- Naršyklė (privaloma kiekvienam žingsniui): H patalpos 02 (perskaityta), 03 (dalis sienų be
  matmens), 04 (atvira erdvė), 01 (be kontūro); G patalpa 04; patikrinti, kad „Teisinga",
  „Pataisyti", „Priimti X m", „kitas kambarys" veikia kaip veikė ir konsolėje nėra klaidų.
