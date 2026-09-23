# Kodėl sąmata „netiksli, bet beveik" — sisteminės priežastys per šešis projektus

> 2026-09-23, steigėjo užduotis: „ieškoti klaidos ar paklaidos, kodėl programėlė apskaičiuoja netiksliai, bet
> beveik, ir kodėl kai kurios eilutės pridedamos, kurių neturėtų, arba nepridedamos, kurios turėtų … ir taip su
> visais projektais / sąmatomis, kad būtų surasta tikra problema ir pritaikyta globaliai."
>
> Metodas: kiekvieno projekto su rangovo sąmata (A, B, C, D, G, H) gyva perskaičiuota sąmata sulyginta su jo
> eilutėmis per užšaldytą koncepto lentelę (`backend/extractor/row_scorecard.py`, `eval_harness.py --rows
> --recompute --geometry --detailed`), tada kiekviena šeima, kuri sistemiškai skiriasi, atsekta iki formulės ir
> jos įvesčių. Tik kiekiai, be €. Jokių kliento pavadinimų. Niekas nederinta pagal jo skaičius — kur skirtumas
> yra jo konvencija, taip ir parašyta.

## 1. Bendras vaizdas prieš pataisas

Eilučių, kurias atkartojame ±10 %: A 37,7 %, B 9,9 %, C 19,4 %, D 32,0 %, G 20,0 %, H 29,2 % (korpuso
vidurkis 24,8 %). Šeimų lentelė (mūsų Σ prieš jo Σ, %):

| Šeima | A | B | C | D | G | H | Išvada |
|---|---|---|---|---|---|---|---|
| Beapvadinių durų angos | −56 | −55 | — | −51 | — | −56 | **sisteminė**: visur perpus mažiau |
| Angokraščiai | −13 | −26 | −13 | +41 | — | +11 | apibrėžimas pritaikytas vienam projektui |
| Plytelės (sienos+grindys) | +10 | −2 | +67 | +77 | +34 | · | angos neatimamos; virtuvės juosta per visą perimetrą |
| Dažymo kampai | −10 | −19 | +32 | +7 | +136 | +6 | sudėtis — spėjimų mišinys, jo konvencija |
| Rotband lyginimas | −12 | −11 | +78 | −18 | — | −43 | 30 % prielaida; jo dalis 17–53 % |
| LED nišos | −1 | −18 | −8 | −2 | — | −8 | visur po truputį mažiau — skaitymo paklaida |
| Šviestuvai (priglaistomi) | +3 | −7 | · | (+700) | — | +75 | D — koncepto lentelės artefaktas; H — Vision suskaičiuoja 30, jis 20 |
| GKP lubos | −6 | +26 | −17 | 0 | — | −1 | lubų tipo skaitymas, projektinė |
| Sienų+lubų dažymas | — | +25 | −20 | −14 | — | +12 | mišru; H +12 % ≈ jo lubos + dizainerio 320 m² sienos |
| Nuolydis duše | 0 | +100 | +100 | 0 | +50 | · | „kiekvienas san. mazgas gauna dušą" |
| WC rėmai / pertvaros sutvirtinimas | 0 | +50 | 0 | 0 | +50 | 0 | san. skaitiklių viršijimas vienetu |

Eilutės, kurias išrašome VISUOSE projektuose, o jis nė viename: „Lubų karnizo sumontavimas / dažymas" (22–151 m
per projektą, 0 iš 6 sąmatų), „Grindjuosčių dažymas", „Slenksniai", „Apsauginės dangos", „Statybvietės
sutvarkymas" ir visos medžiagų eilutės (glaistas kg, dažai l, profiliai, savisriegiai, klijai) — jo sąmatoje
medžiagos yra viena eilutė „Medžiagos montavimui". Jo eilutės, kurių neturime: 32 — vėdinimo medžiagų
specifikacija (B), 22 — šablono eilutės be kiekio („suveskite patys": nišos pertvarose, magnetinių profilių
karkasas, TRACK sistema, bide dušiukai…), 10 — granuliarumas (jis skaido smulkiau), pertvarų m² (D, H),
langų rėmų sandarinimas (A, H), lauko įranga.

## 2. Tikros priežastys ir kas pataisyta globaliai

### 2.1 Durys, surašytos iš abiejų pusių (dubliavimas) — variklio klaida

Vidaus durys stovi DVIEJŲ patalpų `elementai` sąrašuose: koridoriaus sąraše visos jo durys, miegamojo sąraše —
jo durys, ta pati anga. H: 11 vidaus durų elementų ~9 fizinėms durims; po steigėjo atsakymo į angų klausimą
(6 durys pridėtos iš kitos pusės) — 17. Angokraščiai šoko 70 → 100 m, beapvadinių paruošimas dubliavosi.

Pataisyta: `universal_rules.mark_shared_doors` — projekto lygio praėjimas prieš kiekvieną skaičiavimą
(ištraukimas, Prielaidų perskaičiavimas, patalpos lapo perskaičiavimas): durys, kurios veda į patalpą X (anga,
iš kurios jos pridėtos, arba sienų anga to pločio pagal geometrijos juostą), suporuojamos su X sąraše esančiomis
tokio pat pločio durimis; kiekvienas `kiekis` vienetas poruojasi vieną kartą; skaičiuojama mažesnio numerio
patalpoje, kitos elementas pažymimas `_bendra_su`. Sienų plotas atimamas ABIEJOSE patalpose (skylė abiejose
sienos pusėse), tik angų eilutės (angokraščiai, beapvadinių paruošimas) skaičiuoja vieną kartą. Angų klausimas
(`room_facts._listed_beyond`) nebesiūlo angos, kurios durys jau įrašytos gretimoje patalpoje — sako „durys
įrašytos prie tos patalpos".

### 2.2 Angokraščiai ir beapvadinės durys — apibrėžimas, pritaikytas vienam projektui

Iki šiol: angokraščiai = VISOS durys (vidaus ir lauko), lauko langai = 0 („fasado darbai") — birželio
kalibravimas pagal vieną A skaičių (pažeidžia 2026-09-05 taisyklę). Beapvadinių paruošimas = tik Vision
pažymėtos paslėptos durys. Jo praktika visuose penkiuose projektuose: angokraščiai = langai + lauko durys
(A 84 prieš 89, B 99 prieš 94, D 30 prieš 32 — ±6 %; C −17 %; H −32 %, nes H langų dydžiai — standartiniai
numatytieji, ne perskaityti), vidaus durys su apvadais — nieko (apvadas dengia angokraštį), beapvadinės —
atskira eilutė 2h + w. Beapvadinių jis skaičiuoja daugiau nei brėžinys pažymi: A ~7 (pažymėta 6), B ~11 (5),
D 2 (1), H 8 (3).

Pataisyta: angokraščiai = langai (patalpos pusė) + lauko durys; vidaus durys su apvadais — 0; beapvadinių
paruošimas = pažymėtos paslėptos + nepažymėtos vidaus durys, KAI projekto lygio prielaida
`vidaus_durys_beapvadines` teigiama. Prielaida: jo pasirinkimas Prielaidose, kitaip išvedama iš brėžinio —
projektas, kuriame yra bent vienos paslėptos/beapvadinės durys (žymė plane arba durų žiniaraštis), laikomas
dizainerio su beapvadinėmis durimis; be jokio požymio (C) — durys su apvadais. Eilutė neša prielaidos tekstą.
Tai yra sprendimas, kurį steigėjas gali apversti vienu jungikliu; skaičiai per projektus — žemiau.

### 2.3 Plytelės: angos neatimamos, virtuvės juosta per visą perimetrą — variklio klaidos

Plytelių juosta buvo `dalis × perimetras × aukštis` be angų: G trys vonios +13 % lygiai per duris. Virtuvės
0,6 m juosta ėjo per VISĄ patalpos perimetrą: D 11,7 m², H 12,6 m² plytelių, kurių niekas neklijuoja
(stalviršis 3–4 m). Pataisyta: juosta netenka angų (durys iki juostos aukščio, langas — dalis virš 0,9 m
palangės); virtuvės juosta — palei stalviršį, prielaida `kitchen_counter_length_m` = 3,0 m (Prielaidos, su
tekstu). Dažymo bazė nesikeičia (ji jau atėmė angas).

### 2.4 Lubų karnizas — numatytoji eilutė, kurios niekas neužsako

`lubu_karnizo_m` = perimetras + 5 % kiekvienai gyvenamajai patalpai. 0 iš 6 sąmatų. Pataisyta: karnizas tik
kai brėžinio tekste jis minimas (`symbol_legend` skenuoja „karniz"); saugomiems projektams be tokios žymos —
nėra. Eilutė grįžta pati, kai kitas projektas karnizą įvardija.

## 3. Kas lieka jo sprendimu arba tolesniam skaitymui (nedaryta)

- **Dažymo kampai**: sudėtis = perimetras (senos formulės liekana) + 4 × h vidiniai + angų kraštai su
  numatytais dydžiais + pertvarų sandūros; jo skaičiai per projektus nuo −19 % iki +136 %. Kurie kampai
  armuojami — jo konvencija (atviras sprendimas nuo 09-06). Skaitymo pusė: vektoriniai kontūrai jau duoda
  tikrą kampų skaičių — galima pakeisti „4 kampai" prielaidą, kai jis pasakys, kuriuos skaičiuoti.
- **Rotband**: 30 % dažomų sienų — pasirinkimas „Ką skaičiuoti" (dalis / nėra / visos). Jo dalis: A 34 %,
  B 34 %, D 37 %, H 53 %, C 17 %. Iš brėžinio tai būtų sienų storis (mūrinės ↔ GKP) — atskiras darbas.
- **Šviestuvai / difuzoriai**: Vision skaičiuoja elektros plano išvadus; H 30 prieš jo 20 priglaistomų, D
  14 prieš 9. Legenda skiria „įleidžiami" ir kitus — skaitymo tikslumas, ne formulė.
- **LED nišos −8 %** visur: mes — juostos ilgis, jis — nišos formavimo ilgis (gali būti su grįžimais);
  nederinta.
- **San. mazgų komplektai**: kai santechnikos simbolių nėra (C), kiekvienas san. mazgas gauna WC, praustuvą,
  dušą, nuolydį — jo sąmatoje 2 WC, 1 dušas. Skaitymas iš santechnikos plano, kai jis yra, — jau veikia (G, H).
- **Langų dydžiai H** — standartiniai (1200×1500), todėl H angokraščiai −32 %; sienų angų juosta rodo tikrus
  pločius (04: 1,37 / 1,36 / 1,35 / 0,89 m) — pločius galima imti iš ten, aukščius — iš išklotinių.
- Jo eilutės, kurių neskaičiuojame: pertvarų m², langų rėmų sandarinimas (= Σ (2w + 2h) langų — apskaičiuojama
  iš tų pačių elementų), betonavimas prie langų, TRACK sistemos, bortelis LED nišoje — kiekviena atskira eilutė,
  jo šablono klausimas.

## 4. Pamatuota po pataisų

Tie patys vartai po pataisų (`eval_harness.py --rows --recompute --geometry` ir `--totals-only`):

| Projektas | Eilutės ±10 % prieš → po | € ±10 % prieš → po | Eval MAE prieš → po |
|---|---|---|---|
| A | 37,7 → 39,6 % | 47,5 → 51,9 % | 2,81 → 2,81 % |
| B | 9,9 → 9,9 % | 21,0 → 21,0 % | 16,63 → 16,63 % |
| C | 19,4 → 22,2 % | 8,4 → 12,1 % | 15,13 → 15,13 % |
| D | 32,0 → 36,0 % | 28,3 → 60,3 % | 7,10 → 5,10 % |
| G (OOS) | 20,0 → 20,0 % | 53,2 → 53,2 % | 8,10 → 8,10 % |
| H (OOS) | 29,2 → 29,2 % | 32,5 → 32,5 % | 6,80 → 6,80 % |
| Korpusas / in-sample | 24,8 → 26,9 % | 26,3 → 36,3 % | 9,83 → 9,37 % (OOS 7,06 nepakito) |

Šeimos, kurias pataisos lietė (mūsų / jo):

| Šeima | A | B | C | D | H |
|---|---|---|---|---|---|
| Angokraščiai prieš | −13 % | −26 % | −13 % | +41 % | +11 % |
| Angokraščiai po | 85,7 / 89,4 (−4 %) | 99,0 / 94,0 (+5 %) | 37,2 / 34,5 (+8 %) | 29,8 / 31,8 (−6 %) | 47,4 / 63,2 (−25 %, langų dydžiai numatytieji) |
| Beapvadinių paruošimas prieš | −56 % | −55 % | — | −51 % | −56 % |
| Beapvadinių paruošimas po | 52,7 / 39,2 (+34 %) | 70,6 / 55,5 (+27 %) | — | 15,0 / 10,2 (+47 %) | 53,6 / 40,9 (+31 %) |
| Plytelės po | +15 % (sienos+grindys) | −2 % (šeima) | +64 % (patalpa 06 paskirtis) | +46 % (buvo +77 %) | · |
| G plytelės sienos | | | | | 55,0 / 46,1 (+19 %, buvo +34 %) |

Beapvadinių durų eilutė iš „perpus mažiau" tapo „ketvirčiu daugiau": absoliuti paklaida sumažėjo visur (A 22 → 13 m,
B 30 → 15 m, H 23 → 13 m, D 5,2 → 4,8 m), o likutis turi dvi priežastis: (1) B, C, D neturi vektorinių sienų, tad
iš abiejų pusių surašytų durų ten suporuoti nėra iš ko — jos vis dar dubliuojasi; (2) jis ne visas nepažymėtas
vidaus duris laiko beapvadinėmis (A 7 iš ~11, B ~11 iš ~14) — kurios su apvadais, pasako tik durų žiniaraštis
(skaitytuvas `door_type_reader` H žiniaraštyje nerado nė vienos „beapvadinės"). Angokraščiai be vidaus durų su
apvadais sutampa ±8 % keturiuose projektuose iš penkių; penktame (H) langų dydžiai — numatytieji.

## 5. Ką patikrinti steigėjui

1. Beapvadinių durų prielaida: ar jo projektuose visos nepažymėtos vidaus durys yra beapvadinės? Jungiklis
   Prielaidose („Vidaus durys beapvadinės: taip / ne"); skaičiai skyriuje 4.
2. Angokraščiai be vidaus durų su apvadais — ar taip ir sąmatoje? (A, B, D sutampa ±6 %.)
3. Virtuvės stalviršio ilgis 3,0 m — numatytasis; įrašomas Prielaidose.
4. Karnizo nebėra, kol brėžinys jo nemini — ar taip ir dirba?
