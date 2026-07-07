# Gap analysis — Beržų g. 24 (Berzas)
Date: 2026-05-27
Truth: `samata-truth.pdf` (Rangovas A / Rangovas A) + `contractor-notes-verbatim.md`
App output: `app-output-baseline.json` (run on 2026-05-26 baseline, before any fixes)

## Headline reality check

| Metric | App | Truth | Δ |
|---|---|---|---|
| **Paint total (walls + ceilings combined)** | 587,71 m² | 584,81 m² | **+0.5%** ✅ |
| Walls only | 407,25 m² | 460,71 m² | -11.6% |
| Ceilings only (GKP) | 180,46 m² | 165,60 m² | +9.0% |
| LED nišos | 56,6 m (24,8 post-fix) | 42,3 m | +33% / -41% post-fix |
| Floor total | 165,61 m² | 165,61 m² | ✅ |
| Aggregate (all quantities combined) | 1316,63 | 1194,78 | +10,2% |

**Counterintuitive finding:** The total paint area is essentially correct. The problem is *how it's split into line items*, not the math. Contractor combines walls + ceilings into one "Sienų,lubų glaistymas/dažymas iki 3m" line (371,4 m²) + "virš 3m" (213,41 m²). We split by surface type instead.

## Per-line-item gap (samata-truth.pdf, 41 items)

### 🟥 BIG BUGS — wrong number (Vision misread OR Python miscalc)

| Item | Truth | App | Δ | Notes |
|---|---|---|---|---|
| 15 Sienų lyginimas Rotband | 138,69 m² | 277,33 m² | **+100%** | App applies Rotband to all walls. Contractor only to walls needing leveling. **Highest impact fix — pure Python bug.** |
| 23 LED nišų glaistymas/dažymas | 42,3 m | 56,6 m (24,8 post-kiekis-fix) | -41% post-fix | Vision missed niches in 4 rooms (Tambūras, Koridorius, Darbo, Garažas). Needs prompt strengthening + re-run. |
| 19 Dažymo kampų montavimas | 493,35 m | 355,44 m | **-28%** | Contractor's 493,35 = pusiniai 110,28 + durų angos 39,2 + angų kampai 67,2 + statūs 33,85 + ??? (~243m unaccounted). App misses some corner categories. |
| 13/14 Angokraščiai | 89,39 m | 116,86 m | **+31%** | App over-counts. Likely includes external doors / garage. |
| 9 Difūzoriai (montavimas) | 15 vnt | 4 vnt | **-73%** | Vision counted 4 of 15. Big detection gap on lubų plane. |
| 22 Difūzoriai (apdirbimas) | 21 vnt | 4 vnt | **-81%** | Same problem; truth is even higher than item 9. |
| 1 GKP lubų 2,8m | 102,78 m² | 79,38 m² | -23% | Vision missed some lower ceilings. |
| 2 GKP lubų 3,4m | 62,82 m² | 50,54 m² | -19% | High-ceiling area underestimated (Svetainė only). |
| 10/20 Šviestuvai | 38 vnt | 48 vnt | **+26%** | App over-counts. Probably includes wall lights or pendant lights. |
| 35 Grindjuosčių supjovimas | 22,72 m | 10 vnt | -56% | App returned vnt (slenksniai), truth is m (grindjuosčių supjovimas). Wrong unit category. |
| 34 Kampų silikonavimas | 50,14 m | 29,96 m | -40% | Two app lines summed: tarp plytelių zonos 17,12 + plytelių vidinių kampų 12,84. Truth implies more silicone joints. |
| 29 Lentynėlės dušo kabinoje | 5 vnt | 2 vnt | -60% | App = number of bathrooms (2). Truth = total shelves (5). |
| 53 Šiukšlių išvežimas | 12 m³ | 9,9 m³ | -17% | Auto-formula under-estimates waste volume. |

### 🟨 MISSING — app doesn't track this category at all (16 items)

| Item | Truth | Category |
|---|---|---|
| 4 GKP dėžučių (žeminimo) | 11,16 m | GKP soffit drops for ceiling-mounted services |
| 5 Nišos pertvarose | 9,11 m | Niches in partition walls (not LED) |
| 6 Pertvarų storinimas miegamajame LED | 6,24 m² | Thickened bedroom partition for LED |
| 7 Pertvaros sutvirtinimas WC | 2 vnt | WC framing reinforcement |
| 8 GKP klijavimas katilinėje | 9,64 m² | Skim GKP on boiler room walls |
| 11/21 Magnetinė TRACK apšvietimas | 20,06 m | Track lighting — neither installed nor finished |
| 12 Dėžutė ortakiams garaže | 1 vnt | Garage vent box |
| 16/17 Aggregated paint (iki/virš 3m) | 371,4 / 213,41 m² | Combined wall+ceiling — *aggregation gap, not extraction* |
| 24 Plyt. miegamojo vonioje 120×60 | 28,8 m² | Per-bathroom × per-format tile breakdown |
| 25 Plyt. 120×120 ant sienų+grindų | 55,62 m² | Same — format-aware |
| 26 Plyt. grindys 90×90 | 16,99 m² | Same |
| 27 Didžiaformatės | 4,48 m² | Same |
| 28 Didžiaformatės nišų angokr. | 8,7 m² | Niche reveal tiles |
| 50 Skalbimo mašinos montavimas | 1 vnt | Trivial: app missed |

### 🟩 GOOD MATCHES (within ±10%)

- Nuolydžio formavimas: 2 vs 2 ✅
- Hidroizoliacija: 2 vs 2 ✅
- WC rėmo montavimas: 2 vs 2 ✅
- Klozetai: 2 vs 2 ✅
- Gyvatukai: 2 vs 2 ✅
- Latakai: 2 vs 2 ✅
- Skylių gręžimas plytelėse: 53 vs 56 (-5%) ✅
- Plytelių 45° supjovimas: 11,2 vs 9,7 (+15%) ✅
- Total paint (walls+ceilings combined): +0,5% ✅

## Per-room tile breakdown gap (the hidden bug)

Contractor's per-room numbers (from notes):

| Room | Floor tiles | Wall tiles | App matches? |
|---|---|---|---|
| Miegamojo vonia (111) | 7,83 m² | 28,8 m² (120×60) | App said room 111 is 100% paint=0 — likely treated as fully tiled which is correct, but the **format breakdown is missing** (we don't know it's 120×60) |
| Bendra vonia (107) | 6,52 m² | 32,73 m² | Same — paint=0 means tile, but format unknown |
| Tambūras (101) | 8,54 m² | — | **BUG**: App said Tambūras paint=0 with no tile area. Likely the wall paint zone is missing. |
| Katilinė/Skalbykla (106) | 6,89 m² | — | App: paint=6,84 (matches floor), no tile zone declared |
| Garažas (105) | 10,1 m² | — | App: paint=0, no tile zone. Garage gets floor tiles. |

App total floor tiles: 14,04 + 17,85 = 31,89 m². Truth: 7,83 + 6,52 + 8,54 + 6,89 + 10,1 = 39,88 m². Under by ~8 m².

## Electrical / counts

| Item | Truth | App | Note |
|---|---|---|---|
| Rozetės + jungtukai (combined) | 113 | 80 (62+18) | -29% — Vision missed 33 devices |
| Termoreguliatoriai | 8 vnt | 0 | Not tracked at all |
| Lubinių šviestuvų | 38 (priglaistomi) | 48 | +26% — likely includes pendants |
| Magnetinė TRACK | 20,06 m | 0 | Not tracked |
| Difūzoriai | 15-21 | 4 | -73 to -81% |

## Pricing/format observations

Contractor's pozicijos structure that we should match (per ankstesni user notes):
1. **Sienų + lubų glaistymas/dažymas** — combined into one item per height tier (iki 3m, virš 3m)
2. **LED nišų formavimas** + **LED nišų glaistymas/dažymas** — two phases of same niche work
3. **Plytelės pagal formatą** (120×60, 120×120, 90×90, didžiaformatės) — NOT pagal "vonios/kitos"
4. **Dažymo kampai** — one mega-line combining all corner work (493,35 m total)
5. **Šiukšlių išvežimas** under "Statybvietės išlaidos" header (not "Pridėtiniai elementai")

## Top 3 highest-impact fixes (ranked by money + simplicity)

### #1 — Rotband Python bug (Item 15)
- Truth: 138,69 m², App: 277,33 m², gap: **+100%** = ~970 € over-quoted
- **Fix:** Python `_calc_rotband_m2()` or wherever Rotband qty comes from — currently applies to all sienų plotas. Should be a configurable subset (default ~40%, or detect block/concrete walls).
- **Complexity:** ~1 hour. Pure Python math change. No Vision re-run.

### #2 — Pozicijos aggregation refactor
- Truth: separate "iki 3m" and "virš 3m" combined wall+ceiling lines
- **Fix:** `extractor/universal_rules.py` (or wherever line items are built) — restructure output to match contractor's grouping. Drop separate ceiling lines, merge with wall paint.
- **Complexity:** ~2-4 hours. Output schema change. No Vision re-run. Cascades into all UI.

### #3 — Vision prompt strengthening for ceiling plan (LED nišos, difūzoriai, šviestuvai per room)
- Truth: LED 42,3 m / Difuzoriai 15 vnt / Šviestuvai 38 vnt
- App: LED 24,8 m (post-fix) / Difuzoriai 4 / Šviestuvai 48
- **Fix:** Update `prompt.py` ceiling_plan section to enumerate per-room niche extraction + clarify what counts as "priglaistomas šviestuvas" vs "pakabinamas".
- **Complexity:** ~1 day prompt iteration + $1-2 re-run. Highest accuracy ceiling but most expensive to validate.

## Fixes applied (2026-05-27 session)

Šie deterministic Python fix'ai jau taikyti `extractor/vision_call.py` ir `extractor/prompt.py`. Veikia ant ESAMO Vision output'o — Vision re-run nereikalingas.

| Fix | Before | After | Truth | Result |
|---|---|---|---|---|
| Niche kiekis × ilgis_m bug | 56,6 m | 24,8 m | 42,3 m | partial (still -41%, Vision missed rooms) |
| Rotband 100% → 50% default | 277,33 m² | 138,665 m² | 138,69 m² | ✅ -0,0% |
| Lentynėlės 1→2 per vonia | 2 vnt | 4 vnt | 5 vnt | partial (-20%) |
| Šiukšlės 0,06 → 0,075/m² | 9,9 m³ | 12,4 m³ | 12 m³ | ✅ +3% |
| Skalbimo mašinos montavimas | MISS | 1 vnt | 1 vnt | ✅ |

**Aggregate impact for this fixture:** Rotband alone saves ~970 € over-quote. Other fixes are smaller in money but improve customer trust (fewer "obvious mistakes").

## What still requires work

### Needs Vision re-run + prompt iteration (~$1-2 per run)
- **Difūzoriai detection** — 4 vs 15. Vision misses lubų plane symbols. Prompt needs to enumerate per-room.
- **LED nišos missing rooms** — Tambūras, Koridorius, Darbo, Garažas have visible red lines on p6 not extracted.
- **Šviestuvai count too high** — 48 vs 38. Need to distinguish priglaistomi vs pakabinami.

### Needs aggregation refactor (no Vision call, ~half-day work)
- Combine "Sienų + Lubų glaistymas/dažymas" into single line per height tier (iki 3m, virš 3m). Currently 5+ separate line items.
- Combine "LED nišų glaistymas" + "LED nišų dažymas" into one (user note: "Sutraukti į vieną").

### Needs new categories (medium scope)
- Per-room tile breakdown by format (120×60, 120×120, 90×90, didžiaformatės) — read from sienų išklotinės.
- TRACK lighting (magnetinė) — detect on lubų plane or read from spec.
- Termoreguliatoriai — count from electrical plan.
- GKP details: nišų pertvarose (9,11m), pertvarų storinimas (6,24 m²), dėžučių žeminimo (11,16 m).

### Per-room tile zone correction (HARD — needs sienų išklotinės reading)
- Tambūras: floor tiles 8,54 m² (currently missed)
- Katilinė/Skalbykla: floor tiles 6,89 m² (currently shown as floor paint)
- Garažas: floor tiles 10,1 m² (currently missed)

## Saved artifacts for this fixture

- `project.pdf` — original Beržų g. 24 PDF (17 pages, 5,5 MB)
- `samata-truth.pdf` — rangovas's contractor-validated samata (53 line items)
- `app-output-baseline.json` — app output before any fixes (2026-05-26 baseline)
- `contractor-notes-verbatim.md` — rangovas's hand-typed per-room calculation notes
- `gap-analysis.md` — this file
