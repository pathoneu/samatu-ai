# rangovas P2-P5 Cross-Project Audit — Sąmatų AI Coverage Gap

**Auditor:** evidence-first; recommendations gated on appearing in 2+ rangovo projects.
**Anchor:** P1 audit at `/Users/ignasgaldikas/samatu-ai/docs/superpowers/research/2026-04-28-rangovas-p1-audit.md` (16 vs 112 lines, 14% line coverage; identifies missing universals: angokraščių GKP, paslėptų durų staktos, šviestuvų/difuzorių montavimas+apdirbimas, reviziniai dureliai, skylių gręžimas, kampų silikonavimas, plytelių 45° pjovimas, statybvietės).

This audit replicates that work across P2-P5 to test whether the "missing universals" thesis holds beyond a single contract, and to find any items P1 missed.

PDFs read (pdfplumber, full text):
- P2 = `Naujos statybos namas Čiurlių g. 10 Bajorai Kauno r.` (2026-02-12) — 24,252 € be PVM
- P3 = `Naujos statybos namas Romainiuose / Norkaitis` (2026-01-15) — 18,602 € be PVM
- P4 = `Naujos statybos namas Šernų g. 18B Kaunas` (2025-07-16) — 25,021 € be PVM
- P5 = `Butas naujos statybos name Lazūnų g. 6` (2024-06-26) — 20,638 € be PVM

---

## 1. Per-project line counts and skyrius distribution

| Skyrius | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| Gipso kartono montavimas | 14 | 5 | 0 (merged) | 0 (merged) | 11 |
| Sienų lubų glaistymas dažymas | 13 | 6 | 15 | 15 | 8 |
| Plytelių klijavimas | 16 | 7 | 0 | 10 | 6 |
| Grindų / Grindų durų | 4 | 2 | 0 | 0 | 2 |
| Santechnika | ~7 | 7 | 0 | 0 | 11 |
| Elektros instaliacija | ~10 | 7 | 0 | 0 | 7 |
| Vėdinimas / kondicionavimas / šildymas | (in santechnika) | (in santechnika) | 0 | 0 | 3 |
| Papildomi darbai | 5 | 0 | 0 | 0 | 0 |
| Statybvietės išlaidos | 2 | 2 | 0 | 3 | 1 |
| **Total lines** | **~70 (interior scope)** | **36** | **15** | **28** | **49** |
| Total project € be PVM | ~80,161 | 24,252 | 18,602 | 25,021 | 20,638 |

P3 is unusual — only one skyrius (glaistymas dažymas + GKP merged into it). rangovas drops Gipso kartono header on P3/P4 and folds carpentry-style line items into the glaistymas section. So skyrius headers are NOT load-bearing in his lexicon — they are tag groupings, and lines move between groups.

P5 is the only one explicitly itemizing rekuperaciją + kondicionierius + klozeto montavimas — likely because it's a butas (apartment renovation) where the contractor includes more MEP scope.

P3 has no plytelių section at all — that project is paint-only (160 m² molio tinkas etc.). Important: not all jobs include the same skyriai.

---

## 2. Cross-project frequency table

For each unique LT line item across P2-P5, count appearances. Bold = matched our pipeline already; plain = MISSING. Sorted within frequency.

### 4/4 (every project)

| Item (rangovo phrasing) | P2 | P3 | P4 | P5 | We have? |
|---|---|---|---|---|---|
| Sienų lyginimas sausu gipsiniu tinku "Rotband" — m² | line 6 (37) | line 1 (95) | line 1 (132.36) | line 12 (32.41) | NO |
| Sienų, lubų glaistymas/dažymas — m² | line 7 (388) | line 3 (250.95) | line 2 (461.31) | line 13 (150.57) | YES (3 split lines: glaistymas + gruntas + dažai) |
| Dažymo kampų montavimas — m | line 8 (201.86) | line 11 (329.77) | line 5 (303.25) | line 14 (123.59) | YES (called "Glaistymo kampai (vidiniai + išoriniai + angokraščiai)") |

### 3/4

| Item | P2 | P3 | P4 | P5 | We have? |
|---|---|---|---|---|---|
| **Nišų formavimas iš GKP (paslėptam apšvietimui, užuolaidų karnizams ir kt.)** — m | line 2 (16.84) | — | — | line 4 (10.58) + appears in P1 (54.98) | Partial (`Užuolaidų / LED nišos` aggregate; per-project metrai often 0) |
| **Nišų iš GKP paslėptam led apšvietimui glaistymas dažymas** — m | line 11 (16.84) | line 14 (34.54) | — | line 19 (10.68) | NO (only montavimas, not the SECOND glaistymo line) |
| **Angokraščių apdirbimas GKP** — m | line 4 (34.53) | — | line 9 (85.45) | line 10 (31.8) | NO (`angokrasciu_gkp_m` always = 0 in current pipeline) |
| **Hidroizoliacijos įrengimas — vnt** | line 14 (2 vnt) | — | line 21 (2 vnt) | line 22 (1 vnt) | YES but as m², not vnt (UX mismatch) |
| **Skylių gręžimas plytelėse — vnt** | line 15 (21) | — | line 22 (49) | line 23 (17) | NO |
| **Kampų silikonavimas — m** | line 16 (38.15) | — | line 23 (60.54) | line 24 (25.36) | NO |
| **Plytelių supjovimas 45° kampu — m** | line 17 (18.6) | — | line 25 (32.52) | line 25 (5.91) | NO |
| **Nuolydžio formavimas dušo kabinoje — vnt** | line 13 (1) | — | line 18 (2) | line 21 (1) | NO |
| **Plytelių klijavimas ant sienų ir grindų (standartinio formato)** — m² | line 12 (55.27) | — | line 16 (101.57) | line 20 (32.97 "iki 120×60") | YES (split sienos+grindys) |
| **Šiukšlių išvežimas — m³ (or vnt)** | line 9 (10 m³) | — | line 26 (1 vnt) | line 46 (8 m³) | NO |
| **Priglaistomų gipsinių difūzorių apdirbimas** — vnt | — | — | line 6 (2) | line 16 (15 šviestuvai+difūzoriai together) + P1 has 7+13 | NO |
| **Priglaistomų revizinių durelių apdirbimas** — vnt | — | — | line 7b (1) | line 17 (1) + P1 has 7 vnt | NO |
| **Durų angų paruošimas beapvadinėms durims** — m / b/m | — | line 6 (23.92) | line 4 (33.97) | line 18 (10.22) + P1 (55.52) | NO (`pasleptu_duru_staktu_m` always 0) |
| **Smulkūs papildomi / smulkūs el. darbai — vnt** | line 5+ (1) | — | — | line 39+ etc. + similar P5 lines | NO (no buffer-line concept) |
| **Latako montavimas / linijinio trapo — vnt** | — | — | line 19 (2) | line 27 (1) + P1 line drains (line 41) | NO |

### 2/4

| Item | Where | We have? |
|---|---|---|
| **Dėžučių iš GKP formavimas tualetų mechanizmams paslėpti** — vnt | P2 line 3 (2 vnt), P5 line 5 (1 vnt) + P1 (2 vnt) | NO |
| **GKP monatavimas ant lubų, įrengiant dvigubą karkasą** — m² | P2 line 1 (111.84), P5 line 1 (41.28) + P1 (74.91) | YES (called "GKP lubos (standart aukštis)") |
| **Priglaistomų LED profilių apdirbimas/montavimas** — m | P3 line 12 (5.5), P5 line 8/15 (6.85+6.85) | NO (no LED-strip linear meter line) |
| **Priglaistomų gipsinių šviestuvų apdirbimas / montavimas** — vnt | P3 line 13 (37), P5 line 8/16 (9+15) + P1 (69 vnt) | NO |
| **Priglaistomų difūzorių montavimas (apvalūs / pailgi)** — vnt | P4 lines 6,7 (2+9), P5 line 7 (6) + P1 (7+13) | NO |
| **Paslėptų durų staktų apdirbimas** — m / b/m | P3 line 7 (5), P5 line 6 (10.22) + P1 (separately) | NO |
| **Wc rėmo montavimas** — vnt | P2 line 18 (2), P5 line 26 (1) | NO (santechnika out of vidaus apdaila scope, but rangovas includes it) |
| **Drėgmės surinkėjo nuoma** — d.d. | P2 line 10 (25 d.d.), P4 line 28 (8 d.d.) | NO |
| **Pastolių nuoma (>3m)** — d.d. | P4 line 27 (25), P1 (90) | YES partially (gkp_lubu_virs_3m_m2 detection) |
| **Plytelių glaistymas epoksidiniu glaistu** — m² | P2 line 12b (37.11), P1 implied | NO |
| **Angokraščių glaistymas dažymas** — b/m | P3 line 9 (23.8) — paint only, no GKP | YES partial |
| **Trapo montavimas katilinėje** — vnt | P4 line 20 (1), P5 line 27 (1, "latako") | NO |
| **Santechnikos taškų koregavimas** — vnt | P2 line 18 (1), P5 line 28 (1) | NO |
| **Rozetės/jungiklio komutavimas** — vnt | P2 line 1 (75), P5 line 41 (33) | NO |
| **Skylių šviestuvams gręžimas / į gipso kartoną dėžučių rozetėms** — vnt | P2 line 2 (57), P5 line 38 (5+13) | NO |
| **LED juostos komutavimas** — m | P2 line 4 (16.7), P5 line 43 (16.53) | NO |
| **Pakabinamų šviestuvų montavimas** — vnt | P2 line 3 (0), P5 line 42 (2) | NO |
| **PVC dangos klijavimas** — m² | P2 line 8 (98), P5 line 44 (36.99) | YES (lumped in "Parketo / laminato / PVC grindys") |
| **Grindjuosčių klijavimas** — m | (P2 implicit), P5 line 45 (23.07 "medinių iki 7cm") | YES partial |

### 1/4 (project-specific, ignored for recommendations)

P3-only: `Stiklo audinio klijavimas ant vėsinamų lubų` (134.79 m²), `Lubų glaistymas Benjamin Moore dažais` separated from sienų, `Moldingų dažymas` (27.1 b/m), `Durų varčios dažymas` (1 vnt), `Lubų iš gipso kartono montavimas laiptinėje`. These are premium-niche features; do not generalize.

P4-only: `Papildomas sienų glaistymas` (395.19 m² — looks like Q3+ secondary skim), `Stoglangių apdirbimas` (6 vnt — roof windows, project has attic), `Štrabų sienose užtaisymas` (18 m — chases for plumbing), `Gipso kartono pjovimas lubose, šešėlinei siūlei įrengti` (19 m — shadow gap detail), `Plyšinių difūzorių reguliavimas/perdarymas`, `Gipso kartono klijavimas ant sienos katilinėje WC rėmui uždengti` (1 vnt), `Katilinės betono lubų valymas` (1 vnt), `Plintusų supjovimas ir klijavimas`, `Durų angų siaurinimas žeminimas` (7.88 m).

P5-only: `GKP pertvarų įrengimas su 4 sluoksniais ir vata` (11.14 m²), `GKP "dėžučių" lubos (žeminimas)` (9.94 m), `Nišos įrengimas duše` (1 vnt), full santechnikos+rekuperacijos+kondicionavimo skyriai (apartment renovation scope).

P2-only: `Trasų kondicionieriams įrengimas` (2 vnt), `Signalizacijos daviklių pajungimas languose` (1 vnt), `Palangių montavimas` (4.94 m).

---

## 3. Top 10 items WE'RE MISSING (in 3+/4 of P2-P5, plus P1 anchor confirms)

These are universal LT-samatininkas standard items that every rangovo project itemizes but our pipeline produces 0 lines for. Ranked by combined frequency × monetary impact:

1. **Nišų iš GKP paslėptam led apšvietimui glaistymas dažymas** (3/4: P2/P3/P5 + P1). Always paired with the montavimas line (same kiekis). We have montavimas (called "Užuolaidų / LED nišos") but produce no second glaistymo line. Quick fix: when `nisu_metrai > 0` emit two pozicijos (montavimas + glaistymas dažymas), same kiekis, different skyrius.

2. **Angokraščių apdirbimas GKP** (3/4: P2/P4/P5 + P1 with 94.02 m). Our `angokrasciu_gkp_m` field exists in `_recompute_per_room_via_python` but is always 0 because no paskirtis triggers it. Formula: `Σ((2·H_lango + W_lango) × langai) + Σ((2·H_durys + W_durys) × pasleptos_durys)`. Per rangovo data: 32-85 m typical.

3. **Sienų lyginimas Rotband** (4/4 — every single project). Always present, kiekis 30-140 m². This is the layer BEFORE glaistymas — masonry/concrete walls need 3-5mm dry plaster before 1-2 mm glaistas. Our pipeline collapses all preparation into "glaistymas". Formula: per-room `sienu_konstrukcija ∈ {muras, betonas, gkp}`, default 50% of non-GKP wall area gets Rotband. Typical ratio: Rotband m² ≈ 0.3-0.5 × paintable_walls_m².

4. **Skylių gręžimas plytelėse — vnt** (3/4: P2/P4/P5 + P1=109). Tied to wet-room fixture count. Formula: `klozetai × 4 + praustuvai × 6 + dušai × 8 + WC × 5`. rangovo kiekiai 17-49 per project (1-2 vonios). Easy add.

5. **Kampų silikonavimas — m** (3/4: P2/P4/P5 + P1=128.97). Formula: per vonios/WC `(grindų_perimetras + plyteliuotų_lubų_periferija + dušo_kabinos_perimetras)`. rangovo kiekiai 25-60 m. Easy add.

6. **Plytelių supjovimas 45° kampu — m** (3/4: P2/P4/P5 + P1=45.72). Outer corners of tile zones (vonia kraštai, dušo niša). Formula: `Σ(išorinių plytelių kampų × ceiling_height_to_tile)`. rangovo kiekiai 5-32 m.

7. **Nuolydžio formavimas dušo kabinoje — vnt** (3/4: P2/P4/P5 + P1=1). Per dušo zoną. Formula: count `dušas_be_padėklo` zones (linear drain or floor-flush drain). rangovo always 1-2 vnt.

8. **Hidroizoliacijos kaip vnt, ne m²** (3/4 + P1). We HAVE m² output, but UX mismatch. rangovas itemizes per drėgna zona. Fix: emit `vnt = count(vonios + WC + skalbykla + katiline)` AS PRIMARY, m² as expandable detail.

9. **Šiukšlių išvežimas** (3/4: P2/P4/P5 + P1). Universal closing line. Formula: `bendras_plotas × 0.05-0.07 m³/m²`, output unit `m³` (P2/P5) or `vnt` (P4) — m³ more honest. rangovo kiekiai 8-12 m³ for 100-200 m² butas/namas.

10. **Durų angų paruošimas beapvadinėms durims — m** (3/4: P3/P4/P5 + P1=55.52 m). Per `durys_total` with `tipas: pasleptos`. Formula: `Σ((2·H + W) × pasleptu_duru_kiekis)`. Our `pasleptu_duru_staktu_m` always 0.

Honourable mentions (just below cutoff but still 2/4 + P1 confirms):

- **Šviestuvų / difūzorių / revizinių durelių montavimas + apdirbimas** (paired lines). 3/4 of projects have at least difūzorius. P1 had 89 vnt. Source: lubų plano reading. Major scope gap, but requires lubų-plano vision pass we don't have yet.
- **Dėžučių iš GKP WC mechanizmams** (P2+P5+P1). Per `klozetas su potinkiniu rėmu`, default 1 vnt per such WC.
- **Drėgmės surinkėjo nuoma** (P2+P4). d.d., 8-25 days. Pair with statybvietės skyrius.
- **LED profilių apdirbimas — m** (P3+P5). Linear, separate from nišos. 5-7 m typical.

---

## 4. Top 5 OVER-COVERAGE — we have, rangovas never includes

1. **Glaisto medžiaga (kg) as separate line.** None of P2-P5 has a line "glaisto medžiaga" — rangovas embeds the cost into the glaistymas/dažymas € rate and into the `Medžiagų kaina` column of THE SAME line. rangovo line format puts darbų € and medžiagų € side-by-side per line, eliminating the need for our split. **Recommend**: collapse our 6 paint-related lines (Rotband + glaistymas + glaistas-kg + gruntas + grunto-l + dažymas + dažai-l) into 2-3 lines with darbai/medžiagos columns inline.

2. **Grunto medžiaga (l) as separate line.** Same as #1.

3. **Dažų medžiaga (2 sluoksniai, l) as separate line.** Same as #1.

4. **Sienų ir lubų gruntavimas (1 sluoksnis) as separate line.** rangovas never separates gruntas from glaistymas/dažymas. P3 line 3 = "Sienų, lubų glaistymas/dažymas (Benajamin Moore dažai) — m² 250.95 @ 15 €/m²" — single line covers grunto + glaisto + 2 dažų sluoksniai. Our split makes the sąmata look 3× as long without adding info to a contractor.

5. **Lubų karnizas (sumontavimas + dažymas) — m.** None of P2-P5 has a "lubų karnizas" line. Karnizas only appears as part of nišų / molding / dekoro accent items, project-specific. Recommend: gate on user flag `karnizas: true`, default off.

Bonus over-coverage suspect: **"Hidroizoliacija drėgnose patalpose (grindys + sienos drėgmės zonoje)"** as our verbose aprasymas. rangovas writes simply `Hidroizoliacijos įrengimas`. Cosmetic but matters for credibility.

---

## 5. Notable convention differences

**Material/labor split.** rangovas always splits: every line has both darbų € and medžiagų € populated where applicable. Some lines are labor-only (medžiagų = 0) — Rotband, dažymas (with material in same row), kampų montavimas, skylių gręžimas. Rule observable: **rangovas never creates a separate "medžiaga" pozicija**. Materials live inside the work line. Our pipeline does the opposite — separate medžiagų lines with kiekis in kg / l. Recommend a `medziagos_kiekis_per_unit` field on each pozicija and render as a 4th column rather than separate row.

**Q-level coefficients.** rangovas does not vary by Q-level explicitly. Same line "Sienų lubų glaistymas/dažymas" used at €13/m² (P2, naujos statybos), €15/m² (P3, premium with Benjamin Moore), €13/m² (P4), €14/m² (P5). The Q-level adjustment (0.8/1.0/1.2 kg/m² in our coeff) does NOT match rangovas's invoice — he only varies the price, not the kiekis. The only kiekis multiplier he uses is on Rotband: it's a separate line item that activates when walls need extra prep. **Recommendation:** drop Q-level kg/m² variation in the medžiaga calculation; it's an over-engineered abstraction. Replace with `Rotband m²` switch (binary per wall type).

**Grindjuostės waste / formula.** rangovas's grindjuostės = 23-30 m for ~30-50 m² flooring, ratio ~0.6-0.8 m/m². Never adds 10% waste in displayed kiekis. P5 line 45 = `23.07 m` for `36.99 m² PVC` = 0.62 m/m². P1 had 93.8 m for 180 m² = 0.52 m/m². Our 176.56 m for 180 m² = 0.98 m/m² is 2× too high (P1 finding confirmed). The bug: we sum per-room `perimetras − Σdurys` and shared interior walls get counted twice. Need global unique-segment list.

**"vnt" instead of "m²" for zone-based work.** Pattern across all 4: hidroizoliacija, nuolydis dušo kabinoje, dėžutės, latakai, trapai, palangės — all itemized in vnt. Reflects how the contractor charges (per zone visit / per fixture). Our m² outputs are correct internally but should also produce vnt-based pozicijos for these.

**Skyriaus naming with proper Lithuanian diacritics.** rangovas: `Sienų lubų glaistymas dažymas`, `Plytelių klijavimas`, `Gipso kartono montavimas`, `Statybvietės išlaidos`, `Grindų durų montavimas`, `Vėdinimas/ kondicionavimas/šildymas`. We use `Glaistymas dazymas`, `GKP montavimas`, `Plyteles`, `Hidroizoliacija`, `Pridetiniai elementai`. The mojibake makes us look amateur.

**Skyrius merger pattern.** P3 has only one skyrius (everything in `Sienų lubų glaistymas dažymas`). P4 merges GKP into glaistymas. So the GKP skyrius is OPTIONAL for paint-only or paint-heavy jobs. Recommend: `Gipso kartono montavimas` skyrius only emitted when GKP-related kiekis > threshold (e.g., GKP_lubu > 5 m² OR GKP_pertvaros > 0 OR GKP nišos > 2 m).

**Pridetiniai elementai is not a rangovas skyrius.** rangovas uses `Papildomi darbai ir medžiagos` (P1) and `Statybvietės išlaidos` (P2/P4/P5). The English-mojibake `Pridetiniai elementai` is anti-LT.

---

## 6. Concrete code change recommendations

For each missing item, exact extension to `_build_pozicijos_from_rooms` in `vision_call.py`. Each follows existing pattern: aggregate over rooms, threshold check, append pozicija.

```python
# After existing nišos / GKP sections, before plytelės:

# 1. Nišų glaistymas dažymas (paired with montavimas)
total_nisu_m = sum(r.get("nisu_metrai") or 0 for r in rooms)
if total_nisu_m > 0:
    pozicijos.append({
        "skyrius": "Sienų lubų glaistymas dažymas",
        "aprasymas": "Nišų iš GKP paslėptam led apšvietimui glaistymas dažymas",
        "vnt": "m", "kiekis": round(total_nisu_m, 2),
    })

# 2. Angokraščių apdirbimas GKP (sum across rooms)
def _angok_m(r):
    langai = r.get("langai_count") or 0
    pasleptos = r.get("pasleptu_duru_count") or 0
    H_l, W_l = 1.5, 1.2  # standard window
    H_d, W_d = 2.1, 0.9  # standard door
    return langai * (2*H_l + W_l) + pasleptos * (2*H_d + W_d)
total_angok = sum(_angok_m(r) for r in rooms)
if total_angok > 0.5:
    pozicijos.append({
        "skyrius": "Gipso kartono montavimas",
        "aprasymas": "Angokraščių apdirbimas GKP",
        "vnt": "m", "kiekis": round(total_angok, 2),
    })

# 3. Sienų lyginimas Rotband (per-room sienu_konstrukcija flag, default 50% of muras/betonas walls)
def _rotband(r):
    konst = r.get("sienu_konstrukcija", "gkp")
    if konst in ("muras", "betonas"):
        return (r.get("sienu_dazomas_plotas_m2") or 0) * 0.5
    return 0
total_rotband = sum(_rotband(r) for r in rooms)
if total_rotband > 1:
    pozicijos.append({
        "skyrius": "Sienų lubų glaistymas dažymas",
        "aprasymas": 'Sienų lyginimas sausu gipsiniu tinku "Rotband"',
        "vnt": "m²", "kiekis": round(total_rotband, 2),
    })

# 4. Skylių gręžimas plytelėse (wet-room fixture-based)
def _skylu(r):
    if r.get("paskirtis") not in ("vonia", "wc", "san", "skalbykla"):
        return 0
    klozetai = r.get("klozetai") or (1 if r["paskirtis"] in ("vonia","wc","san") else 0)
    praustuvai = r.get("praustuvai") or (1 if r["paskirtis"] in ("vonia","san") else 0)
    dusai = r.get("dusai") or (1 if r["paskirtis"] in ("vonia","san") else 0)
    return klozetai*4 + praustuvai*6 + dusai*8 + 5  # +5 for misc
total_skylu = sum(_skylu(r) for r in rooms)
if total_skylu > 0:
    pozicijos.append({
        "skyrius": "Plytelių klijavimas",
        "aprasymas": "Skylių gręžimas plytelėse",
        "vnt": "vnt", "kiekis": int(total_skylu),
    })

# 5. Kampų silikonavimas (vonios + dušai)
def _silikonas(r):
    if r.get("paskirtis") not in ("vonia","wc","san","skalbykla","katiline"):
        return 0
    perim = r.get("perimetras_m") or 0
    H = r.get("lubu_aukstis_m") or 2.7
    plyteliu_iki = r.get("plyteliu_iki_m") or H
    return perim + perim + (4 * plyteliu_iki if r.get("dušas") else 0)  # grindys + lubų pjūvis + dušas
total_silik = sum(_silikonas(r) for r in rooms)
if total_silik > 0.5:
    pozicijos.append({
        "skyrius": "Plytelių klijavimas",
        "aprasymas": "Kampų silikonavimas",
        "vnt": "m", "kiekis": round(total_silik, 2),
    })

# 6. Plytelių 45° pjovimas (outer tile corners)
def _45deg(r):
    if not r.get("plyteles_sienos") or not r.get("plyteliu_iki_m"):
        return 0
    return (r.get("isoriniai_kampai_plyteliu") or 2) * r["plyteliu_iki_m"]
total_45 = sum(_45deg(r) for r in rooms)
if total_45 > 0.5:
    pozicijos.append({
        "skyrius": "Plytelių klijavimas",
        "aprasymas": "Plytelių supjovimas 45° kampu",
        "vnt": "m", "kiekis": round(total_45, 2),
    })

# 7. Nuolydžio formavimas dušo kabinoje
total_nuolydzio = sum(1 for r in rooms if r.get("dušas") and (r.get("trapas") == "linear" or r.get("dušas_be_padėklo")))
if total_nuolydzio > 0:
    pozicijos.append({
        "skyrius": "Plytelių klijavimas",
        "aprasymas": "Nuolydžio formavimas dušo kabinoje",
        "vnt": "vnt", "kiekis": total_nuolydzio,
    })

# 8. Hidroizoliacija — emit AS vnt (drėgnos zonos count); keep m² as expandable detail
n_drēgnos = sum(1 for r in rooms if (r.get("paskirtis") in ("vonia","wc","san","skalbykla","katiline")))
if n_drēgnos > 0:
    pozicijos.append({
        "skyrius": "Plytelių klijavimas",   # NOTE: merged into plytelės, like rangovas
        "aprasymas": "Hidroizoliacijos įrengimas",
        "vnt": "vnt", "kiekis": n_drēgnos,
        "_detail_m2": round(total_hidro_m2, 2),  # for expandable UI
    })

# 9. Šiukšlių išvežimas (always emit at end)
bendras_plotas = sum(r.get("plotas_m2") or 0 for r in rooms)
if bendras_plotas > 0:
    siuksles_m3 = max(1, round(bendras_plotas * 0.06, 0))
    pozicijos.append({
        "skyrius": "Statybvietės išlaidos",
        "aprasymas": "Šiukšlių išvežimas",
        "vnt": "m³", "kiekis": int(siuksles_m3),
    })

# 10. Durų angų paruošimas beapvadinėms durims
def _bevok(r):
    pasleptos = r.get("pasleptu_duru_count") or 0
    H, W = 2.1, 0.9
    return pasleptos * (2*H + W)
total_bevok = sum(_bevok(r) for r in rooms)
if total_bevok > 0.5:
    pozicijos.append({
        "skyrius": "Sienų lubų glaistymas dažymas",
        "aprasymas": "Durų angų paruošimas beapvadinėms durims",
        "vnt": "m", "kiekis": round(total_bevok, 2),
    })

# 11. Dėžučių iš GKP WC mechanizmams (per WC su potinkiniu klozetu)
n_dezuciu = sum(1 for r in rooms if r.get("paskirtis") in ("vonia","wc","san") and (r.get("klozetas_potinkinis") or True))
if n_dezuciu > 0:
    pozicijos.append({
        "skyrius": "Gipso kartono montavimas",
        "aprasymas": "Dėžučių iš GKP formavimas tualetų mechanizmams paslėpti",
        "vnt": "vnt", "kiekis": n_dezuciu,
    })
```

**Skyriaus rename + diacritics fix** (single sweep):
```python
_SKYRIUS_LT = {
    "Glaistymas dazymas":   "Sienų lubų glaistymas dažymas",
    "GKP montavimas":       "Gipso kartono montavimas",
    "Plyteles":             "Plytelių klijavimas",
    "Hidroizoliacija":      "Plytelių klijavimas",   # rangovas merges
    "Pridetiniai elementai":"Papildomi darbai ir medžiagos",
}
```

**Collapse material lines** (drop separate rows for glaisto-kg, grunto-l, dažų-l). Move kiekis into `medziagos_kiekis` field on the parent darbo line; render in UI as 4-column table (vnt | kiekis | darbai € | medžiagos €) like rangovas's PDF.

**Drop Q-level kg/m² variation** in glaisto medžiaga calc; replace with binary per-wall `Rotband: yes/no`.

**Fix grindjuostės double-count** (P1 finding, applies universally) — use unique segment list, not per-room sum.

**Threshold-gate skyriai** — don't emit GKP skyrius if no GKP work; don't emit Statybvietės if bendras_plotas < 30 m².

---

## Bottom line

Cross-project, P1's diagnosis holds: 12-15 standard LT-samatininkas line items are missing from our pipeline. Of these, the 10 listed in §3 appear in 3 of 4 P2-P5 projects (and in P1) — they are NOT P1-specific noise. Each has a deterministic formula from primitives we already extract or trivially can.

Less obvious finding: our material/labor split into separate pozicijos is non-standard. rangovas always inlines materials. Our 4-row paint stack (glaistas + glaistas-kg + gruntas + grunto-l + dažai + dažai-l) maps to rangovas's 1 row. **Fixing this single architectural change cuts our line count by ~40% and immediately makes the sąmata read like an LT contractor wrote it.**

Three highest-ROI changes, ranked:

1. Add the 10 missing universal pozicijos in §3 and §6 — each is 5-10 lines of Python.
2. Collapse material rows into inline `medziagos_kiekis` field; restructure UI table to 4 columns like rangovo's PDF.
3. Apply skyriaus rename map + drop the `Pridetiniai elementai` umbrella (split into Statybvietės / Grindų / Papildomi).

After these three, we'd jump from 16 pozicijos to ~25-28 per project, matching rangovo's typical 28-49 line range for vidaus apdaila scope. Closes the embarrassment gap identified in P1 audit — every contractor who actually itemizes properly would no longer find our output amateur.
