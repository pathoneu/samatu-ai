# rangovo P1 Pasiūlymo Pozicijų Analizė

> **rangovo yra vienas LT rangovas — jo pozicijos rodo "kokio detalumo lygio sąmatos LT rangovai išleidžia."**
> Skaičiai ne ground truth, bet POZICIJŲ TIPAI ir GRANULARITY yra orientyras kuris turi atspindėti į mūsų output'ą.

P1: Naujos statybos namas Bacevičiaus g. Kaunas. Vidaus apdailos darbai. 2026-04-13.

## rangovo positions per skyrius

### Skyrius 1 — Gipso kartono montavimas

| Nr | Aprašymas | Vnt | Kiekis |
|----|-----------|-----|--------|
| 1 | GKP ant lubų, dvigubas karkasas | m² | 74.91 |
| 2 | GKP ant lubų, dvigubas karkasas (aukštis virš 3m) | m² | 68.28 |
| 3 | Laidų apsiuvimas garaže | b/m; m² | 26.57 |
| 4 | Nišų formavimas iš GKP (LED, užuolaidų karnizai) | b/m | 54.98 |
| 5 | Pertvaros tarp miegamojo ir WC | vnt | 1 |
| 6 | Dėžutės iš GKP WC mechanizmams paslėpti (miegamasis vonia) | vnt | 1 |
| 7 | Pertvarėlės lentynoms dušo kabinoje | vnt | 1 |
| 8 | Dėžutės iš GKP WC mechanizmams (bendras WC) | vnt | 1 |
| 9 | Priglaistomi gipsiniai difuzoriai apvalūs | vnt | 7 |
| 10 | Priglaistomi plyšiniai difuzoriai | vnt | 13 |
| 11 | Lubinių priglaistomų šviestuvų montavimas | vnt | 69 |
| 12 | Reviziniai dureliai 600×600 | vnt | 3 |
| 13 | Reviziniai dureliai 1500×500 | vnt | 1 |
| 14 | Reviziniai dureliai 300×300 | vnt | 3 |
| 14b | Angokraščių apdirbimas GKP | m | 94.02 |

### Skyrius 2 — Sienų lubų glaistymas dažymas

| Nr | Aprašymas | Vnt | Kiekis |
|----|-----------|-----|--------|
| 15 | Sienų lyginimas sausu gipsiniu tinku "Rotband" | m² | 138.69 |
| 16 | **Sienų / lubų glaistymas / dažymas** | m² | **424.75** |
| 17 | Lubų glaistymas/dažymas (virš 3m aukščio) | m² | 68.28 |
| 18 | Sienų dekoravimas molio tinku | m² | 160 |
| 19 | Durų angų paruošimas beapvasdinėms durims | m | 55.52 |
| 20 | **Dažymo kampų montavimas** | m | **580.54** |
| 21 | Priglaistomų gipsinių šviestuvų apdirbimas | vnt | 69 |
| 22 | Priglaistomų gipsinių difuzorių apdirbimas | vnt | 7 |
| 23 | Priglaistomų plyšinių difuzorių apdirbimas | vnt | 13 |
| 24 | Revizinių durelių 600×600 apdirbimas | vnt | 3 |
| 25 | Revizinių durelių 1500×500 apdirbimas | vnt | 1 |
| 26 | Revizinių durelių 300×300 apdirbimas | vnt | 3 |
| 27 | Nišų iš GKP paslėptam LED glaistymas dažymas | m | 54.98 |

### Skyrius 3 — Plytelių klijavimas

| Nr | Aprašymas | Vnt | Kiekis |
|----|-----------|-----|--------|
| 28 | Plytelių klijavimas 1200×1200×6 (sienos+grindys) | m² | 157.34 |
| 29 | Plytelių klijavimas 1200×1200×6 (nišos angokraščiai) | b/m | 34.49 |
| 30 | Plytelių klijavimas 1200×600×9 (sienos+grindys) | m² | 52.59 |
| 31 | Didžiaformatės plytelės | m² | 7.52 |
| 32 | Didžiaformatės plytelės (nišos angokraščiai) | m² | 10.49 |
| 33 | Lentynėliai iš plytelių dušo kabinoje | vnt | 3 |
| 34 | Nuolydžio formavimas dušo kabinoje | vnt | 1 |
| 35 | **Hidroizoliacijos įrengimas** | vnt | **3** |
| 36 | Skylių gręžimas plytelėse | vnt | 109 |
| 37 | Kampų silikonavimas | m | 128.97 |
| 38 | Plytelių supjovimas 45° kampu, kampo apdirbimas epoksidu | m | 45.72 |
| 39 | Išlyginamojo pylimas | m² | 39.43 |
| 40 | Laiptų garaže įrengimas | vnt | 2 |
| 41 | Plytelių pripjovimas prie trapo garaže | m | 9 |
| 42 | Aliuminio apdailinio kampo montavimas ant plytelių garaže | m | 17.77 |
| 43 | Garažo plytelės | vnt | 1 |

### Skyriai 4-5 — Rekuperacija, Santechnika

Out of interior-takeoff scope (HVAC + plumbing). Mūsų pipeline'as šiuos skyrius gali pažymėti "out_of_scope" ir nepateikti.

## Comparison: V8 baseline P1 vs rangovo P1

| Metric | V8 P1 | rangovo P1 | Δ% (V8 vs rangovo) | Verdict |
|--------|-------|---------|----------------|---------|
| Rooms detected | 13 | 13 (eksplikacija) | 0% | ✅ V8 matches |
| Bendras plotas m² | 205.55 | ~205 (sum from drawings) | ~0% | ✅ Match |
| **Sienų/lubų dažymas m²** | **446.6** | **424.75** | +5.1% | ✅ Within ±15% tolerance |
| **Dažymo kampai m** | **380.98** | **580.54** | **−34.4%** | ❌ V8 SEVERELY undercounts! |
| Plytelės sienos m² | 87.2 | ~157 (1200×1200×6 share) | ~−45% | ❌ V8 undercounts |
| GKP lubos m² | (not in V8 totals?) | 143.19 | n/a | ⚠ V8 may not produce |
| Angokraščių GKP m | (not in V8 totals?) | 94.02 | n/a | ⚠ V8 may not produce |
| Hidroizoliacijos vnt | 0 | 3 | n/a | ❌ V8 misses |

## Implications for new pipeline

1. **Output schema must be richer** than V8's `santrauka` totals. Need per-position list, organized by skyrius. Each position has: skyrius, aprašymas, vnt, kiekis, šaltinis (eksplikacija | iš brėžinio | apskaičiuota).

2. **V8 undercounts kampai by 34%** — formula gap. rangovo gets 580m for ~205m² apartment. CLAUDE.md formula says: perimetras (lubų periferija) + 4×H (vidiniai kampai) per room. For 13 rooms × ~24m/room = 312m. But rangovo gets 580m. Likely rangovo also includes:
   - Išoriniai kampai (kolonos, atsikišimai, L-formų išorė)
   - Angokraščių dažymo kampai (per durų reveal)
   - Lubos/sienos sandūra (lubų periferija KIEKVIENAM kambariui)
   - Plus GKP nišų išoriniai kampai

3. **V8 undercounts plytelės sienos** — rangovo lists separately by tile size (1200×1200×6 = 157m², 1200×600×9 = 52m², didžiaformatės = 7.52m²). V8 just gives 87.2m² aggregate. Pipeline should report by TILE SIZE (from brėžinio plytelių specifikacija ar wall-development legendos).

4. **rangovo includes positions V8 doesn't think about:**
   - Lubos virš 3m aukščio (atskira pozicija — kitokia kaina)
   - Skylių gręžimas plytelėse (109 vnt — kiekvienam santechnikos prijungimui, lentynai, kabykloi)
   - Kampų silikonavimas (vonia perimetrai prie grindų ir lubų)
   - Plytelių 45° pjovimas (estetiškas išorinis kampas)
   - Reviziniai dureliai (3 dydžiai × montavimas + apdirbimas)
   - Difuzorių apdirbimas atskirai nuo montavimo

5. **Granularity rule**: jei brėžinyje matoma SPECIFIKACIJA (pvz. plytelės 1200×1200, 1200×600), output'e turi pasirodyti atskiros pozicijos. Universal pipeline'as neaproksimuoja, jei specifika brėžinyje yra.

6. **Hidroizoliacija** — rangovo skaičiuoja 3 vnt (vonia + WC + dušas). Mūsų pipeline turi išvardinti `hidroizoliacijos_vnt` per kambarį pagal paskirtis (vonia/wc/skalbykla/dušo zonos).

## What this means for the Phase 1 prompt

The single Vision call must produce, in addition to per-room metrics, a **flat list of positions** with:
- `skyrius` (GKP / Glaistymas-Dažymas / Plytelės / Hidroizoliacija / Pridėtiniai elementai)
- `aprašymas` (LT contractor-style description)
- `vnt` (m² | m | b/m | vnt)
- `kiekis` (number)
- `pastaba` (e.g. tile size, room reference, "virš 3m")
- `šaltinis` (eksplikacija | brėžinio_matmenys | sutartiniai_ženklai | ROOM_TYPE_RULES_default)

This gives the user a **kiekių žiniaraštis** structure that maps cleanly to the contractor's working document.

---

# Cross-validation: rangovo P3

P3 pasiulymas (2026-01-15, "Naujos statybos namas Romainiuose", rangovas Rangovas A) has a DIFFERENT structure — only **1 skyrius** "Sienų lubų glaistymas dažymas" with 15 positions. This shows: pipeline must adapt to PROJECT SCOPE, not force a 5-skyrius structure.

P3 positions (NOT in P1) — broadens the universal vocabulary:
- **Stiklo audinio klijavimas ant vėsinamų lubų** (m²) — fiberglass mesh on cooled ceilings
- **Paslėptų durų staktų apdirbimas gipso kartonu bei glaistymas dažymas** (b/m)
- **Durų varčios dažymas** (vnt) — door leaf painting (not just frame)
- **Moldingų dažymas** (bv/m) — decorative molding paint
- **Lubų iš gipso kartono montavimas laiptinėje** (vnt) — stairwell ceiling
- Different paint products separately ("Benjamin Moore", "Supreme Ultimate") — premium tier separation

P3 vs V8 comparison — V8 over-estimates here:
- V8 dažymas P3 = 734.6 m² | rangovo total dažymas P3 = 95 + 139.79 + 250.95 + 134.79 + 29.34 = 649.87 m² | V8 +13%
- V8 kampai P3 = 583.66 m | rangovo P3 = 329.77 m | **V8 +77%** (opposite direction from P1!)

So V8 is unstable across projects — sometimes under, sometimes over. Different formula interpretations between V8 and rangovo, not a consistent bias.

# Universal LT position vocabulary (confirmed across P1+P3)

These positions appear in LT contractor pasiulymai for residential interior work. Our pipeline output should be able to produce ANY of these when justified by the drawings:

**GKP / Drywall:**
- GKP montavimas ant lubų (m², separately for >3m)
- Laidų apsiuvimas (m or m²)
- Nišų formavimas iš GKP (b/m, for LED + carniaus)
- Pertvaros tarp patalpų (vnt, with dimensions)
- Dėžutės iš GKP slėpti mechanizmus (vnt)
- Pertvarėlės dušo kabinoje (vnt)
- Reviziniai dureliai (vnt by size: 600×600, 1500×500, 300×300)

**Glaistymas / Dažymas:**
- Sienų lyginimas Rotband (m²)
- Sienų / lubų glaistymas / dažymas (m²)
- Lubų glaistymas/dažymas (virš 3m, separately)
- Stiklo audinio klijavimas (m²) — for cooling ceilings
- Sienų dekoravimas molio tinku (m²)
- Specifiniai dažai atskiros pozicijos (Benjamin Moore, Supreme Ultimate, etc.)
- Durų angų paruošimas beapvasdinėms durims (m or b/m)
- Paslėptų durų staktų apdirbimas (b/m)
- Durų varčios dažymas (vnt)
- Angokraščių glaistymas/dažymas (b/m)
- Moldingų dažymas (bv/m)
- **Dažymo kampų montavimas** (m) — universal, big variance across V8 vs rangovo
- LED profilių apdirbimas (m)
- Šviestuvų apdirbimas (vnt)
- Difuzorių apdirbimas (vnt, apvalūs/plyšiniai separately)
- Revizinių durelių apdirbimas (vnt)
- Nišų iš GKP LED glaistymas/dažymas (m)
- Lubų iš GKP montavimas laiptinėje (vnt)

**Plytelės:**
- Plytelių klijavimas su DYDŽIU (m², per tile size: 1200×1200×6, 1200×600×9, didžiaformatės)
- Plytelės nišos angokraščiai (b/m, per tile size)
- Lentynėliai iš plytelių (vnt)
- Nuolydžio formavimas (vnt)
- Hidroizoliacija (vnt) — per zone (vonia, wc, dušas, skalbykla)
- Skylių gręžimas plytelėse (vnt)
- Kampų silikonavimas (m)
- Plytelių 45° pjovimas (m)
- Išlyginamojo pylimas (m²)
- Aliuminio apdailinio kampo montavimas (m)
- Specialūs elementai: laiptai, garažo plytelės, prie trapo

**Out of interior takeoff scope (mark `_skyrius: out_of_scope`):**
- Rekuperacija / HVAC
- Santechnika / Plumbing
- Elektros instaliacija (other than kabykų taškai)

