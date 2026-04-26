# Accuracy Gate — kada priimame naują pipeline

User'io direktyva (2026-04-26): **"main thing is accuracy, design and everything comes after."**

Naujas `extractor/` pipeline priimamas **TIK** jei jis išlaiko šitą gate'ą P1–P5 testavime. Priešingu atveju — refactor'as nutraukiamas, V8 lieka gyvas.

## V8 dabartinė būklė (THE BAR)

Iš Phase 0.2 matavimo (žr. `V8_BASELINE.md`):

| P# | V8 status | V8 numeriai (jei dirba) |
|----|-----------|-------------------------|
| P1 | ✅ dirba | 13 rooms, 205.55 m², 446.6 m² dažymo, 87.2 m² plytelės |
| P2 | ❌ 0 rooms | — |
| P3 | ✅ dirba | 18 rooms, 240.05 m², 734.6 m² dažymo, 65.1 m² plytelės |
| P4 | 💥 crash (SIGABRT) | 0 rooms (saved before crash) |
| P5 | ❌ 0 rooms | — |

V8 dirba 2/5 projektuose, abu su eksplikacija text lentelėmis.

## Gate criteria — naujas pipeline turi:

### P1, P3 (V8 dirba — high bar)

Vienam projektui:
- **Rooms count**: per `±20%` V8 reikšmės (toleruojam 10–15 rooms vs V8 13; 14–22 vs V8 18)
- **Bendras plotas m²**: per `±10%` V8 reikšmės
- **Dažymo plotas m²**: per `±15%` V8 reikšmės
- **Plytelės sienos m²**: per `±25%` V8 reikšmės (didesnė toleracija nes priklauso nuo wall-development brėžinių interpretacijos)

Tolerancijos plačios todėl, kad Vision yra non-deterministic — A vs A run skirtumas gali būti 5–10%. Borderline rezultatai → run 3× ir imti medianą.

### P2, P5 (V8 returns 0 — strict improvement zone)

V8 nerado patalpų. Bet kas geresnio nei 0 yra **WIN**:
- ≥1 patalpos aptiktos = ✅
- 0 patalpos = neutralu (no regression, but also no win)

### P4 (V8 crashes — architectural improvement zone)

V8 lūžta su SIGABRT. Naujas pipeline:
- Neturi crash'inti (✅ minimal bar)
- Idealu: aptikti kambarius (V8 saved 0 prieš crash, tad ≥1 = win)

## Final Decision Rules

Po Phase 3 (`extractor/` validation):

| Outcome | Acceptance |
|---------|-----------|
| **PASS** — naujas pipeline atitinka kriterijus visiems P1, P3 IR neregress'uoja P2, P4, P5 (tj. ≥0 rooms, no crash) | Tęsiam Phase 4 (frontend switch) ir Phase 5 (full deletion) |
| **CONDITIONAL PASS** — naujas pipeline atitinka P1, P3 BET nepagerina P2/P4/P5 (vis dar 0 rooms) | Tęsiam — refactor'as duoda code simplicity be regress'o. V8 fragilumas pašalinamas. |
| **PARTIAL FAIL** — naujas pipeline regress'uoja P1 ARBA P3 (žemiau tolerancijos) bet smarkiai pagerina P2/P5 | STOP. Diskusija su user'iu: ar verta? P1/P3 yra ground-truthed projektai. |
| **FAIL** — naujas pipeline regress'uoja P1 IR P3 | ABORT. Switch to fallback mode (Phase 5 fallback): trinam tik orphans (V9 pipeline_v9.py, V5 endpoint, dead imports). V8 lieka. |

## Why these tolerances?

- **±20% rooms**: Vision negali tiksliai atskirti "atviros erdvės" nuo dviejų patalpų visada. ±2 patalpos ant 13 yra normaly.
- **±10% bendras plotas**: kambarinio ploto skaičiavimas iš mm matmenų yra deterministinis kai matmenys aiškūs. ±10% leidžia interpretacines klaidas.
- **±15% dažymo**: priklauso nuo plytelinės juostos aukščio interpretacijos (vonia: 2.0m default, bet gali būti 2.4m).
- **±25% plytelės**: labiausiai brėžinio-interpretacinis metric — kuri siena turi plyteles, iki kokio aukščio. Plačiausia toleracija.

Tolerancijos GALI būti sugriežtintos po Phase 3 jei matome, kad Vision yra stabilesnis nei tikėjomės.

## Operativiniai pastoviniai

- Borderline rezultatai (per kraštą) → 3 run'ai, imam medianą.
- Visi runs SAME PDF input'as (largest variant per project — per `find_breziniai_pdf` script logic).
- rangovo `_pasiulymas.pdf` ground truth įveda manual'iai į `V8_BASELINE.md` lentelę vėliau (Phase 1 review). Tai naudojama orientyrui, ne automatic gate'ui.
