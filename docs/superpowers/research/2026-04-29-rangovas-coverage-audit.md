# Rangovas Coverage Audit: Gap Analysis (2026-04-29)

**Scope**: 5 projects (P1, P2, P3, P4, P5) | ~242 line items | LT residential interiors  
**Baseline**: Deterministic generator in `vision_call.py:_build_pozicijos_from_rooms()`  
**Finding**: Our generator produces **63 fixed aprasymai** vs Rangovas's **189 unique categories**.

---

## 1. TOP 10 MISSING CATEGORIES TABLE

| # | Rangovas Aprašymas | Típ. Kiekis | Freq (5 proj) | Should Add? | Reason |
|---|---|---|---|---|---|
| 1 | Dažymo kampų montavimas | 307.8 m | 5/5 (100%) | **Y** | Universal in all projects; our "glaistymo kampai" misses assembly labor |
| 2 | Sienų lyginimas sausu gipsiniu tinku "Rotband" | 87.1 m² | 5/5 (100%) | **Y** | Pre-glaistymas material; we have it in code but as "storos netolygumai" (different framing) |
| 3 | Kampų silikonavimas (plytelės) | 63.3 m | 4/5 (80%) | **Y** | Silicone trim work; wet rooms; separate from "silikonavimas sanitarinės įrangos" |
| 4 | Nišų LED paslėptam apšvietimui glaistymas | 29.3 m | 4/5 (80%) | **Y** | Recessed lighting niche finishing; LED-specific, not generic nišos |
| 5 | Nuolydžio formavimas dušo zonoje | 1.2 vnt | 4/5 (80%) | **Y** | Shower slope detail; standalone, not grouped with tile work |
| 6 | GKP montavimas (standartinis) | 76.0 m² | 3/5 (60%) | **Y** | Standard height ceiling boarding; splits from "virš 3m" clearly |
| 7 | Nišų formavimas iš GKP (paslėptam apšvietimui) | 27.5 b/m | 3/5 (60%) | **Y** | Framing niche structure; precedes the finishing (row 4) |
| 8 | Plytelių supjovimas 45° kampu (epoksidu) | 45.7 m | 1/5 (20%) | **Y** | Premium tile corner epoxy finish; P1 (prestige). ~2% frequency but high unit cost |
| 9 | Sienų/lubų glaistymas/dažymas (combined) | 333.3 m² | 3/5 (60%) | **Y** | Aggregated labor line (vs split per coat); Rangovas uses both split & combined patterns |
| 10 | Džiovyklės montavimas | 1.0 vnt | 2/5 (40%) | **N** | Laundry-specific appliance; low freq, not LT residential baseline |

---

## 2. PRIORITY ADDITIONS (Ranked by Frequency × Impact)

### **Priority 1: DAŽYMO KAMPŲ MONTAVIMAS** (5/5 projects)
- **Impact**: 1,539 m aggregate across portfolio  
- **Missing mechanism**: We emit "glaistymo kampai vidiniai/išoriniai" (materials only); Rangovas separates **assembly labor** as distinct line  
- **Action**: Add `"Dažymo kampų montavimas"` (m, 1 per project ≈ 1.0×total_kampai_m) to SK_GD skyrius, positioned after "glaistymo kampai" lines  

### **Priority 2: SIENŲ LYGINIMAS ROTBAND** (5/5 projects)
- **Impact**: 435.5 m² total  
- **Missing mechanism**: We emit this in code (line 669–675) BUT describe as "storos sienų netolygumai". Rangovas uses exact material brand + dry plaster qualifier  
- **Action**: Harmonize aprašymas wording to match Rangovas: `"Sienų lyginimas sausu gipsiniu tinku \"Rotband\""`  

### **Priority 3: KAMPŲ SILIKONAVIMAS (Plytelės)** (4/5 projects)
- **Impact**: 253.2 m total  
- **Missing mechanism**: We emit generic "Silikonavimas tarp plytelių zonos ir sanitarinės įrangos". Rangovas separates **corner sealing** (kampų silikonavimas) from sanitaryware sealing  
- **Action**: Add separate line `"Kampų silikonavimas"` (m, ~0.5×wet_perim) to SK_PL, after tile grid work but before sanitary sealing  

---

## 3. OVERALL COVERAGE ASSESSMENT

**Quantitative**:  
- Deterministic coverage: **63 / 189 = 33%** of Rangovas's unique lines  
- Frequency-weighted coverage: **~78% of line items** (Top 3 skyrius heavily covered; tail thin)  

**Systematic gaps** (not random outliers):

1. **Separation of labor from material** — We bundle, Rangovas itemizes:
   - "Dažymo kampai" → material only; "Dažymo kampų montavimas" → separate labor
   - "Grindjuostės" → we combine; Rangovas: sumontavimas + dažymas atskirai  
   - Impact: ~15 line-item pairs missing labor separation

2. **Branded/specific materials** — We generalize:
   - "Rotband" → generic "pradinis glaistas"
   - LT market expects brand specificity (Rotband, Knauf Fügen, Ceresit CX10 etc.)  
   - Impact: ~8 lines; medium accuracy risk in cost modeling

3. **Appliance-grade plumbing** — We use defaults:
   - Džiovyklės, skalbimo mašinos, boilers → Rangovas itemizes per location  
   - Our baseline (n_skalbykla heuristic) matches ~60% of projects  
   - Impact: ~4 lines, low freq but high cost per item

4. **Finishing detail specification** — We miss nuance:
   - LED nišos glaistymas (vs generic nišos)  
   - Epoxy tile corners (vs standard grout)  
   - Sanitaryware coupling (gyvatukas/tenas) as separate line  
   - Impact: ~12 lines; 40–60% freq

**Conclusion**: At **~78% frequency-weighted coverage**, we handle typical LT residential interiors **adequately for MVP**. However, **systematic gaps in labor itemization** (15+ lines) create a **credibility and cost-modeling risk** for prestige projects (P1-level). To reach **85%+ confidence** for pro contractors, prioritize the 3 labor-separation items above; rest can wait for Phase 2.

---

## Recommendations

1. **Immediate (Sprint)**: Add dažymo kampų montavimas + kampų silikonavimas (2 lines, high ROI)  
2. **Follow-up**: Harmonize Rotband wording; audit appliance defaults  
3. **Post-MVP**: Refactor "materials-only" lines to offer optional labor splits via UI toggle  
