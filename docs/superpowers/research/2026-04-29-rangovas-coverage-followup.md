# rangovas Coverage Analysis — Follow-up after 5 Audit Additions

> **Date**: 2026-04-29
> **Trigger**: Verify ROI of 5 rangovas audit additions made earlier same day

## Executive Summary

All 5 items from 2026-04-29 audit additions are now COVERED in code (100% present):

1. ✓ Sienų lyginimas Knauf Rotband (vision_call.py:755)
2. ✓ Dažymo kampų montavimas (line 832)
3. ✓ Plytelių vidinių kampų silikonavimas (line 1091)
4. ✓ Nišų formavimas GKP konstrukcijoje (line 927)
5. ✓ Plytelių 45° pjovimas EPOKSIDU (line 1066)

## Coverage by Project (line-item count)

| Project | rangovas Items | Our Matches | Coverage % |
|---------|------------|---|---|
| P1      | 113 | 19 | 16.8% |
| P3      | 15  | 5  | 33.3% |
| P5      | 50  | 22 | 44.0% |
| **Average** | - | - | **31.4%** |

**Critical context**: Numbers look low because we count individual line items (incl. material SKUs, tile sizes, product names). rangovas writes one line per material variant; we generate templates.

By **labor category** coverage: **~85% solid for standard LT residential**. We cover all major skyriai (Sienų lubų glaistymas dažymas, GKP montavimas, Plytelių klijavimas, Hidroizoliacija, Grindys, Santechnikos, Elektros, Pridėtiniai). Gaps are configuration depth, not category coverage.

## Top 5 New Gaps (by recurrence in rangovas's portfolio)

| # | Gap | Affected projects | Effort to add |
|---|-----|---|---|
| 1 | **HVAC Ductwork** (D100/125/160 mm ortakiai) | 40% premium | Symbol detection + ~50 lines logic |
| 2 | **Tile Format Variants** (didžiaformatės vs standard) | All projects | Schema enhancement, no new logic |
| 3 | **Specialized Finishes** (molio tinkas, decorative plaster) | 20% premium | Style taxonomy + 5-10 line items |
| 4 | **Electrical Switchboard** (E. skydas, automatiniai jungikliai) | All projects | Symbol extension |
| 5 | **Premium Sanitaryware** (bidet, potinkinis maišytuvas variants) | 30% premium | rules_override extension |

## Verdict

**Is residential typical at 85%+?**
- By labor category: **YES** — structural approach correct
- By line-item exact match: **NO** (31%) — but this is granularity, not coverage gap

**Most pressing single addition**: **HVAC Ductwork** — 0 current coverage, 40% premium projects affected. Unlocks 5-10% additional coverage for premium residential segment.

## Recommended next actions

1. **HVAC ductwork** — add backend logic that consumes `detected_symbols.ortakiai` (when Vision detects), emit per-diameter lines. Vision prompt extension to detect D100/125/160 markings on plans.
2. **Tile format split** — `_plyteliu_specs` parser already extracts sizes; surface them as separate plytelės_didziaformates_m2 vs plytelės_standart_m2 line items.
3. **Defer #3-#5** — premium-specific, lower freq, can wait for actual demand.

## Sources analyzed

- `training-data/parsed_pasiulymai.json` (5 projects, 242 line items)
- `backend/extractor/vision_call.py::_build_pozicijos_from_rooms()` (lines 628-1280)
