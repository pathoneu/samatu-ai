# Rangovas P1 vs Sąmatų AI — Line-by-Line Audit

**Project:** P1 — Naujos statybos namas Bacevičiaus g. Kaunas (224 m² su garažu)
**Rangovo PDF:** `/Users/ignasgaldikas/samatu-ai/training-data/projektas_1/projektas_1_pasiulymas.pdf` (112 lines, 8 skyriai, 80,161 € be PVM)
**Mūsų output:** project `eeaad5fd-e1af-4cd9-9bb9-50d3c739922f`, 16 pozicijos
**Auditor:** brutally honest

---

## Headline numbers

| | Rangovas | Mūsų |
|---|---|---|
| Lines / pozicijos | 112 | 16 |
| Skyriai | 8 (Gipso kartono, Glaistymas-dažymas, Plytelės, Rekuperacija, Santechnika, Grindys, Papildomi, Statybvietės) | 5 (Glaistymas-dažymas, GKP, Plytelės, Hidroizoliacija, Pridėtiniai) |
| Bendras plotas reference | ~205 m² | 180 m² |
| Sienų/lubų dažymas | 424.75 m² (line 16) + 68.28 m² (>3m) = 493.03 m² | 536.42 m² |
| Dažymo kampai | 580.54 m | 497.18 m |
| Plytelės sienos+grindys | 230 m² (1200×1200 + 1200×600 + didžiaformatės) | 91.60 m² (60.48 + 31.12) |
| Hidroizoliacija | 3 vnt | 50.75 m² |
| Grindjuostės | 63 m įleistos + 30.8 m paprastos | 176.56 m (vienos) |
| GKP lubos | 74.91 + 68.28 = 143.19 m² | 86.46 + 62.42 = 148.88 m² |

We're at **14% line coverage** (16/112). Even excluding HVAC + santechnika (45 lines, out-of-scope for vidaus apdaila pipeline), Rangovas's interior scope is **~67 lines** — we cover **24%** of what an LT samatininkas itemizes.

---

## 1. RANGOVAS HAS, WE DON'T (priority gap-fill)

### Skyrius: Gipso kartono montavimas

| Rangovo eilutė | Vnt | Kiekis | Kaip mes galėtume apskaičiuoti |
|---|---|---|---|
| **3. Laidų apsiuvimas garaže** | m² | 26.57 | Garažo lubų `plotas_m2` × dalis (kur eina laidai). Užtenka per-room flag `laidu_apsiuvimas_m2` su default = 0; vartotojas įjungia garažui. |
| **4. Nišų formavimas iš GKP (paslėptam apšvietimui, užuolaidų karnizams)** | b/m | 54.98 | `Σ langų pločiai + 0.4m × 1.3` užuolaidų nišom + LED nišos iš lubų plano. Naudoti `_zoom.nisu_metrai` jei užfiksuota; default formula: `Σ(panoraminis_langas.plotis + 0.40)`. Mūsų `nisu_metrai = 0` per visus kambarius — VISIŠKAI praleista. |
| **5. Pertvaros tarp miegamojo ir WC** | vnt | 1 | Aptikti suite-tipo bedroom + adjacent en-suite WC iš eksplikacijos kaimynystės grafo. Output: `vnt 1` su pastaba "tarp X ir Y". |
| **6. Dėžutės iš GKP WC mechanizmams paslėpti (miegamasis vonia)** | vnt | 1 | Per kiekvieną WC su potinkiniu klozetu: 1 vnt dėžutė. Mes turim 5 klozetus (`durys_total` + WC paskirties patalpos), bet 0 dėžučių. |
| **7. Pertvarėlės lentynoms dušo kabinoje** | vnt | 1 | Per dušo zona (mes aptinkam `hidroizoliacijos_vnt = 3`, bet šių shelf-niche nišų nepateikiam). |
| **8. Dėžutės iš GKP WC mechanizmams (bendras WC)** | vnt | 1 | Tas pats kaip #6 — duplicate per kitam WC. |
| **9. Priglaistomi gipsiniai difuzoriai apvalūs** | vnt | 7 | Skaitytinas iš lubų plano (recuperator difuzoriai). Mes neturim lubų plano parsing'o. |
| **10. Priglaistomi plyšiniai difuzoriai** | vnt | 13 | Tas pats — iš lubų plano. |
| **11. Lubinių priglaistomų šviestuvų montavimas** | vnt | 69 | Iš lubų plano arba šviestuvų plano. **69 vnt — masyvi praleista pozicija.** |
| **12-14. Reviziniai dureliai 600×600 / 1500×500 / 300×300** | vnt | 3 / 1 / 3 | Skaitytinas iš lubų plano arba santechnikos rūšiavimo. Per WC: 1 didelis (1500×500) dušo paneliui + 1 mažas (300×300) trapo lygiui. |
| **14b. Angokraščių apdirbimas GKP** | m | 94.02 | Mūsų `angokrasciu_gkp_m = 0` per visus kambarius. Formulė: `Σ((2×H_lango + W_lango) × kiekis) + Σ((2×H_durys + W_durys) × kiekis)` paslėptoms duroms ir paneliniams langams. **KRITINĖ PRALEISTA POZICIJA — 94 m, kažkas tarp 6-10 €/m, jei taip — 600-900 €. ** |

### Skyrius: Glaistymas / dažymas

| Rangovo eilutė | Vnt | Kiekis | Kaip galėtume apskaičiuoti |
|---|---|---|---|
| **15. Sienų lyginimas sausu gipsiniu tinku "Rotband"** | m² | 138.69 | Tai NE-GKP sienos (mūro / betono blokeliai), reikalaujantys storesnio sluoksnio prieš glaistymą. Reikalingas per-room `sienu_konstrukcija` flag (mūras/betonas/GKP). Default: 50% sienų gauna Rotband, 50% — tik glaistas. |
| **17. Lubų glaistymas/dažymas (virš 3m aukščio)** | m² | 68.28 | Mes turim tą primityvą (`gkp_lubu_virs_3m_m2 = 62.42`), bet nesukuriame ATSKIROS dažymo pozicijos virš 3m. Reikia split'inti `Sienų ir lubų glaistymas` į `<3m` ir `>3m` (skirtinga kaina dėl pastolių). |
| **18. Sienų dekoravimas molio tinku** | m² | 160 | Premium finish accent walls. Reikia per-room `dekoratyvinis_pavirsius_m2` flag, default 0; vartotojas užpildo. |
| **19. Durų angų paruošimas beapvasdinėms durims** | m | 55.52 | Per paslėptas duris (`tipas: pasleptos`): 7 vnt × ~7.9 m/duris = 55 m. Formulė: `Σ((2×H + W) × paslepto_duru_kiekis)`. Mūsų `pasleptu_duru_staktu_m = 0` — VISIŠKAI praleista, nors `durys_total` rodo 8 paslėptas duris. |
| **20. Dažymo kampų montavimas** | m | 580.54 | Mūsų 497.18 m. Skirtumas −16.7%, žr. §3. |
| **21-23. Šviestuvų / difuzorių apdirbimas** | vnt | 69, 7, 13 | Antroji pozicija PO montavimo (skirtingas darbas: glaistymas + perdažymas aplink). Reikia automatiškai sukurti porą `montavimas` + `apdirbimas` kiekvienam šviestuvo/difuzoriaus tipui. |
| **24-26. Revizinių durelių apdirbimas** | vnt | 3, 1, 3 | Same poros logika kaip #21-23. |
| **27. Nišų iš GKP paslėptam LED glaistymas/dažymas** | m | 54.98 | Tas pats kiekis kaip GKP nišos formavimo (#4) — automatiškai sukurti antrą poziciją glaistymui. |

### Skyrius: Plytelės

| Rangovo eilutė | Vnt | Kiekis | Kaip galėtume apskaičiuoti |
|---|---|---|---|
| **28-32. Plytelės su DYDŽIU** (1200×1200×6, 1200×600×9, didžiaformatės, atskirai sienos+grindys ir nišos angokraščiai) | m², b/m | 157.34 / 34.49 / 52.59 / 7.52 / 10.49 | Mes pateikiam vieną agregatą `60.48 + 31.12 = 91.6 m²`. **Pralaimim −60%.** Reikia plytelių specifikacijos parsing'o iš brėžinių (sienų išklotinės arba specifikacijos lentelės). |
| **33. Lentynėliai iš plytelių dušo kabinoje** | vnt | 3 | Per dušo kabinos zoną: default 1 vnt lentynėlė. |
| **34. Nuolydžio formavimas dušo kabinoje** | vnt | 1 | Per linijinį trapą / žemu kraštą trapą (`linear_drain` flag). |
| **35. Hidroizoliacijos įrengimas** | vnt | 3 | Mes turim 50.75 m² — RANGOVO MAŽIAU ABSTRAKTUS, jis skaičiuoja vnt. (zona). Mes vnt formoje neišleidžiam — žr. §4 frazinis padalinimas. |
| **36. Skylių gręžimas plytelėse** | vnt | 109 | Per santechnikos taškus + lentynų kabes + rankšluosčių laikiklius. Default formulė: `klozeto_kiekis × 4 + praustuvo_kiekis × 6 + dušo_kiekis × 8 + WC_kiekis × 5`. ~25-30 skylių per vonios kambarį. |
| **37. Kampų silikonavimas** | m | 128.97 | Per vonios/WC: `(perimetras_grindys + perimetras_lubu_pjūvis_su_plytelem) + dušo_kabinos_perimetras`. Mūsų pozicijų sąraše VISAI nėra. |
| **38. Plytelių pjovimas 45° kampu, kampo apdirbimas epoksidu** | m | 45.72 | Per išorinius plytelių kampus (vonios kraštai, dušo įvaikai). Counted iš sienų išklotinės kampų ženklų. |
| **39. Išlyginamojo pylimas** | m² | 39.43 | Mes turim 180 m² per visą butą. Rangovo skaičiuoja TIK plyteliuotų zonų išlyginamasis (dušas + vonia + garažo įėjimas), parketo zonai jis turi atskirą poziciją (#102: 143.19 m²). Mūsų agregatas 180 = parketas + plytelės sutampa, bet sąraše vienoje vietoje. **Reikia split'inti.** |
| **40. Laiptų garaže įrengimas** | vnt | 2 | Iš pjūvio aptiktinas garažo grindų lygio skirtumas. |
| **41. Plytelių pripjovimas prie trapo garaže** | m | 9 | Per linijinį trapą (per `linear_drain` flag) garaže. |
| **42. Aliuminio apdailinio kampo montavimas ant plytelių garaže** | m | 17.77 | Garažo grindų-sienos sandūros perimetras kur plytelė susitinka su betonu. |

### Skyrius: Grindys

| Rangovo eilutė | Vnt | Kiekis | Kaip galėtume apskaičiuoti |
|---|---|---|---|
| **101. Parketlenčių klijavimas 45° eglutė** | m² | 108.08 | Mūsų `pvc_grindys_m2 = 148.88`. Rangovo dalis: parketas 108 + laminatas (jokio?) + PVC (jokio? — visa "guminė garaže" 10.8 m²). **Mes maišom parketas + PVC + laminatas vienon pozicijon "Parketo / laminato / PVC grindys".** Reikia per-room `grindu_danga_tipas` (parketas/laminatas/PVC/guma/vinilas) flag. |
| **103. Į sieną įleistos grindjuostės** | m | 63 | Premium grindjuostės (recessed). Rangovo split'ina nuo paprastų. Mūsų vienas agregatas 176.56 m (kuris ir taip per didelis vs Rangovas's 63+30.8 = 93.8 m). Žr. §3. |
| **104. Paprastos grindjuostės** | m | 30.8 | Atskira pozicija nuo įleistų. |

### Skyrius: Papildomi darbai (line items 105-109)

| Rangovo eilutė | Vnt | Kiekis | Komentaras |
|---|---|---|---|
| 105. Durų angos platinimas į miegamojo rūbinę | vnt | 1 | Renovation-only, vartotojo flag. |
| 106-107. Mėnulio ir TV sienos dekoravimas (Mėnulio dekoras) | vnt | 1 | Premium accent. Vartotojo flag. |
| 108. Guminės dangos montavimas garaže | m² | 10.8 | Per garažo plotą — jei `paskirtis = garazas`, default flooring = guma, ne PVC/parketas. |

### Skyrius: Statybvietės išlaidos

| Rangovo eilutė | Vnt | Kiekis | Kaip galėtume apskaičiuoti |
|---|---|---|---|
| **110. Šiukšlių išvežimas** | m³ | 12 | Default: `bendras_plotas × 0.05 m³/m²` arba `bendras_plotas × 0.067` (priklauso nuo statybos tipo). |
| **111. Pastolių nuoma (>3m)** | d.d. | 90 | Per `gkp_lubu_virs_3m_m2 > 0` aptikta — 62 m² × ~1.5 d.d./m² = 90 d.d. (sutampa su Rangovo). |

**Verdict (1):** Mums trūksta ~25 universal pozicijų, kurias kiekvienas LT samatininkas turi. Big-ticket missing items, sorted by absolute price impact:

1. **Šviestuvų / difuzorių montavimas + apdirbimas** (~89 vnt × ~30 €/vnt = ~2,700 €) — privalomas iš lubų plano
2. **Plytelių specifikacija pagal dydį** (~230 m² × kainos skirtumas 5-15 €/m² priklausomai nuo dydžio = ~1,500-3,000 € accuracy delta)
3. **Angokraščių apdirbimas GKP** (94 m × 15 €/m = 1,410 €)
4. **Reviziniai dureliai** (7 vnt × ~50 € + 7 vnt apdirbimas × 30 € = ~560 €)
5. **Skylių gręžimas plytelėse** (109 × 7 € = 763 €)
6. **Paslėptų durų staktų apdirbimas** (55 m × 15 € = 833 €)
7. **Sienų lyginimas Rotband** (138.69 m² × 7 € = 970 €)
8. **Nišų formavimas + glaistymas dažymas** (55 m × (12+13) = 1,374 €)

That's ~10,000 € of work hidden from our pasiūlymas. For an 80k € project, **we're missing 12.5% of the kiekiai**. A samatininkas using our tool would get embarrassed by every contractor who actually itemizes properly.

---

## 2. WE HAVE, RANGOVAS DOESN'T

| Mūsų pozicija | Kiekis | Rangovas turi atitikmenį? |
|---|---|---|
| **Glaisto medžiaga** (kg) | 670.54 kg | NE — Rangovas medžiagas pateikia kiekvienoje work-line per-vnt. Mes split'inam darbus + medžiagas. **Universally legitimate** — vartotojas gali matyti medžiagų kiekius atskirai (perka pats arba klausia rangovo). Tačiau LT konvencija — medžiagos įtrauktos į pozicijos kainą su pastaba "su medžiagomis". |
| **Grunto medžiaga** (l) | 76.65 l | NE — same as above. |
| **Dažų medžiaga (2 sluoksniai)** (l) | 107.27 l | NE — same. |
| **Sienų ir lubų dažymas (2 sluoksniai)** | 536.42 m² | TAIP — line 16 + 17, bet Rangovas neišleidžia "sluoksniai" prie pozicijos aprašymo. |
| **Sienų ir lubų gruntavimas (1 sluoksnis)** | 536.42 m² | NE — Rangovas integravęs gruntavimą į "glaistymas/dažymas" poziciją (line 16 kaina 14 €/m² apima gruntą). **Mūsų atskira pozicija — naudinga vartotojui, kuris nori detaliai matyti.** Bet LT contractor convention — single line. |
| **Hidroizoliacija (m²)** | 50.75 m² | TAIP — bet Rangovas pateikia `vnt = 3` (per zoną), mes — m². |

**Verdict (2):** Mes per-detailingai išskaidžiavom medžiagas (glaistas-kg, dažai-l, gruntas-l). Tai naudinga *prieš* perkant medžiagas, bet rangovo pasiūlyme tai yra noise. **Recommend:** medžiagas paslėpti į collapsable detail panel po pagrindinės pozicijos, default-rodyti darbo kiekį (m²) + suvestę kainą.

Mūsų atskirą "gruntavimas" poziciją galima palikti — kai kurie samatininkai (pvz. P3 pasiūlymo Rangovas iš 2026-01-15) tai išskaičia. Convention-permissive.

---

## 3. BOTH HAVE, BUT QUANTITIES DIFFER >10%

| Pozicija | Mūsų | Rangovo | Δ% | Likely cause |
|---|---|---|---|---|
| **Sienų / lubų dažymas** | 536.42 m² | 424.75 + 68.28 = 493.03 m² | +8.8% | OK, within tolerance. Mes truputį per dideli. Galimai dvigubai skaičiuojam atvirus L-formų kampus arba neatimam molio tinko 160 m² (Rangovo line 18 — atskira pozicija, todėl Rangovo dažymas mažesnis). **Tikrasis Rangovo dažymas + molio tinkas = 653 m²**, mūsų 536. **Mes UNDER-counting'uojam −18%** kai įskaičiuojam molio tinką. |
| **Glaistymo kampai** | 497.18 m | 580.54 m | **−14.4%** | Rangovas turi 580 m, mes 497. CLAUDE.md formula: `outer_corners × H + lubų periferija`. Rangovas, atrodo, įskaičiuoja: vidiniai kampai (4 × H per kambarį), išoriniai kampai, lubų-sienos sandūra (= lubų periferija × kambarių skaičiaus), GKP nišų išorės kampai. **Mums trūksta nišų išorinių kampų komponento** (54.98 m × ~3 = ~165 m). Pridėjus — 497 + 83 = 580 m. **Žinom kur skylė.** |
| **Grindjuostės** | 176.56 m | 63 + 30.8 = 93.8 m | **+88%** | **MUMS ŽYMIAI PER DAUG.** Galimai dvigubai skaičiuojam (per kambarį visi durys atimami, bet kambarių jungtyse durys atimamos tik vieną kartą). Rangovas's 93.8 m / `bendras_plotas` 180 = 0.52 m/m². LT konvencija: 0.4-0.6 m/m². Mūsų 176/180 = **0.98 m/m² — 2× per didelis.** Formulė `perimetras − Σdurys` taikoma KIEKVIENAM kambariui dvigubiną sąsajinius perėjimus. Reikia globalaus sąrašo unique segmentų, ne per-kambarį sumavimo. |
| **GKP lubų virš 3m** | 62.42 m² | 68.28 m² | −8.6% | Within tolerance. Rangovas truputį didesnis — galbūt įskaičiuoja garažo aukštą zoną. |
| **GKP lubų standart** | 86.46 m² | 74.91 m² | +15.4% | Mes per dideli. Galbūt įskaičiuojam tambūro lubas (7.36 m² betoninės, ne GKP). Reikia per-kambarį `lubu_tipas == "gkp"` filter — turim, bet galbūt fallback paliktas "gkp". |
| **Hidroizoliacija** | 50.75 m² | 3 vnt | n/a | Skirtingas matavimo principas. Mūsų m² geras vidiniam computation, bet **vartotojui nepateikiam kaip "3 vnt drėgnos zonos"** — Rangovas's vnt-skaičiavimas yra konvencija. Reikia output dvi formas: m² (techninis) + vnt (komercinis). |

**Verdict (3):**

- **Grindjuostės +88%** is our worst formula bug. Net-net, čia probably 80+ € klaida vidutiniam projektui. **Aukščiausio prioriteto fix.**
- **Glaistymo kampai −14%** dėl praleistų nišų išorinių kampų — known root cause, fix'as paprastas.
- **Dažymas +9%** within tolerance, bet dėl molio tinko nepradėtos atskiros pozicijos efektyviai pateikiam −18% accuracy kai projektas turi specialius dekoratyvinius paviršius.

---

## 4. RANGOVAS'S PHRASING WE SHOULD COPY

LT samatininkų lexicon — exact strings to adopt verbatim into `pozicijos.aprasymas`:

**GKP skyriuje:**
- "GKP montavimas ant lubų, įrengiant dvigubą karkasą" (NOT "GKP lubos (standart aukštis)" — too vague about karkasas)
- "GKP montavimas ant lubų, įrengiant dvigubą karkasą (kai aukštis virš 3m)"
- "Laidų apsiuvimas garaže b/m" — note `b/m` ne `m`
- "Nišų formavimas iš GKP (paslėptam apšvietimui, užuolaidų karnizams ir kt.)"
- "Pertvaros įrengimas tarp [room A] ir [room B]"
- "Dėžutės iš GKP formavimas WC mechanizmams paslėpti ([room name])"
- "Priglaistomų gipsinių difūzorių montavimas apvalių"
- "Priglaistomų plyšinių difūzorių montavimas"
- "Lubinių priglaistomų šviestuvų montavimas"
- "Revizinių durelių 600×600 įrengimas" (kaip atskira pozicija per dydį)
- "Angokraščių apdirbimas GKP"

**Glaistymas / dažymas skyriuje:**
- "Sienų lyginimas sausu gipsiniu tinku 'Rotband'"
- "Sienų / lubų glaistymas / dažymas" (NOT "Sienų ir lubų glaistymas (paviršiaus parengimas)" — Rangovo formuluotė trumpesnė ir atspindi end-to-end darbą)
- "Lubų glaistymas / dažymas (virš 3m aukščio)"
- "Sienų dekoravimas molio tinku"
- "Durų angų paruošimas beapvasdinėms durims"
- "Dažymo kampų montavimas" (NOT "Glaistymo kampai (vidiniai + išoriniai + angokraščiai)" — Rangovo trumpesnis ir tiksliau atspindi DARBO objektą — kampo metalinės juostelės montavimą, ne abstraktų "glaistymo kampą")
- "Priglaistomų gipsinių šviestuvų apdirbimas"
- "Priglaistomų plyšinių difuzorių apdirbimas"
- "Nišų iš GKP paslėptam LED apšvietimui glaistymas dažymas"

**Plytelės skyriuje:**
- "Plytelių klijavimas ant sienų ir grindų [DYDIS]" — su DYDŽIU expliciškai
- "Plytelių klijavimas ant sienų [DYDIS] (nišos angokraščiai)"
- "Didžiaformačių plytelių klijavimas"
- "Hidroizoliacijos įrengimas" (NOT "Hidroizoliacija drėgnose patalpose (grindys + sienos drėgmės zonoje)")
- "Skylių gręžimas plytelėse"
- "Kampų silikonavimas"
- "Plytelių supjovimas 45° kampu, kampo apdirbimas epoksidu"
- "Išlyginamojo pylimas" (NOT "Išlyginamasis grindyse (savaime išsilyginantis mišinys)" — Rangovo neutraliau, tinka ir įprastam, ir savaime išsilyginančiam)

**Grindys skyriuje:**
- "Parketlenčių klijavimas 45° eglutė" — eksplicitas pattern'as
- "Į sieną įleistų grindjuosčių įrengimas"
- "Paprastų grindjuosčių montavimas"

**Statybvietės:**
- "Šiukšlių išvežimas" (m³, ne kg)
- "Pastolių nuoma (aukštesnių nei 3m)" — d.d. (darbo dienos), ne vnt

**Skyriaus pavadinimai:** mes vartojam "Glaistymas dazymas" (be lietuviškų raidžių), "Pridetiniai elementai", "Plyteles" — visi su klaidomis. Rangovas naudoja:
- "Gipso kartono montavimas"
- "Sienų lubų glaistymas dažymas"
- "Plytelių klijavimas"
- "Grindų montavimas"
- "Papildomi darbai ir medžiagos"
- "Statybvietės išlaidos"

**Skyriaus pavadinimo migration map:**
| Mūsų | Į |
|---|---|
| `Glaistymas dazymas` | `Sienų lubų glaistymas dažymas` |
| `GKP montavimas` | `Gipso kartono montavimas` |
| `Plyteles` | `Plytelių klijavimas` |
| `Hidroizoliacija` | merge į `Plytelių klijavimas` skyrių (Rangovas taip daro) |
| `Pridetiniai elementai` | split'inti į `Grindų montavimas` + `Papildomi darbai ir medžiagos` + `Statybvietės išlaidos` |

---

## Bottom line

We're **not competitive** in P1. 16 pozicijos vs Rangovo 67 (interior scope). Our customer-facing sąmata looks like a Walmart receipt next to Rangovo's invoice. Worse: 3 of our 16 pozicijos have quantity bugs (grindjuostės +88%, kampai −14%, GKP standart +15%).

**Top 3 fixes ranked by ROI:**

1. **Add ~15 missing universal positions** from §1 (angokraščių GKP apdirbimas, paslėptų durų staktos, šviestuvų/difuzorių montavimas+apdirbimas, reviziniai dureliai, skylių gręžimas, kampų silikonavimas, plytelių 45° pjovimas, lentynėliai, dėžutės, statybvietės, šiukšlių išvežimas, pastolių nuoma). Each has a deterministic formula from primitives we ALREADY extract or can extract from lubų / santechnikos planų pages we currently skip.

2. **Fix grindjuostės double-counting** — global unique segment list, not per-room sum.

3. **Adopt Rangovo's lexicon verbatim** for `aprasymas` field. Skyriaus names with proper Lithuanian diacritics. Prevents the "this tool was built by people who don't speak the language" smell.

Optional: collapse medžiagų (glaistas-kg, dažai-l, gruntas-l) into nested detail panels, default-show work quantity. Adopt vnt-based hidroizoliacijos counting (with m² as expandable detail).
