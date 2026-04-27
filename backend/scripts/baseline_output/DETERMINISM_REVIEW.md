# Phase 6.5.2 — Determinism Stress Test Results

Captured: 2026-04-27 09:34:22
Setup: 3 runs per project. Vision is non-deterministic;
this characterizes run-to-run variance per metric.

## Per-metric variance

| Project | Metric | Min | Mean | Max | CV% |
|---------|--------|-----|------|-----|-----|
| P2 | rooms | 5.00 | 6.67 | 8.00 | 22.9% |
| P2 | bendras_plotas_m2 | 95.50 | 97.50 | 98.50 | 1.8% |
| P2 | dazymo_total | 273.44 | 311.75 | 348.35 | 12.0% |
| P2 | kampai_total | 168.87 | 206.37 | 226.61 | 15.8% |
| P2 | plyteles_sienos_total | 1.56 | 17.12 | 47.52 | 153.8% |
| P2 | plyteles_grindys_total | 3.80 | 7.77 | 12.00 | 52.9% |
| P2 | pozicijos_count | 20.00 | 21.00 | 23.00 | 8.2% |
| P3 | rooms | 20.00 | 20.33 | 21.00 | 2.8% |
| P3 | bendras_plotas_m2 | 267.71 | 267.71 | 267.71 | 0.0% |
| P3 | dazymo_total | 751.68 | 775.06 | 812.15 | 4.2% |
| P3 | kampai_total | 423.00 | 431.77 | 445.00 | 2.7% |
| P3 | plyteles_sienos_total | 176.64 | 196.63 | 208.89 | 8.9% |
| P3 | plyteles_grindys_total | 71.45 | 79.90 | 86.87 | 9.8% |
| P3 | pozicijos_count | 38.00 | 44.67 | 51.00 | 14.6% |

## Verdict

Threshold: CV >10% indicates a metric where averaging/voting may help.

⚠ **6 metrics flagged**:
- P2 rooms: CV 22.9% (values: [8.0, 7.0, 5.0])
- P2 dazymo_total: CV 12.0% (values: [313.46, 348.35, 273.44])
- P2 kampai_total: CV 15.8% (values: [223.63, 226.61, 168.87])
- P2 plyteles_sienos_total: CV 153.8% (values: [47.52, 1.56, 2.28])
- P2 plyteles_grindys_total: CV 52.9% (values: [12.0, 7.5, 3.8])
- P3 pozicijos_count: CV 14.6% (values: [45.0, 51.0, 38.0])
## Interpretation — eksplikacija matters

The variance pattern correlates with **eksplikacija lentelės presence**:

| Project | Has eksplikacija text? | Headline metric variance |
|---------|------------------------|--------------------------|
| P2 | ❌ No | rooms CV 22.9%, plytelės CV 153.8% |
| P3 | ✅ Yes | rooms CV 2.8%, dažymas CV 4.2% |

When the brėžinys has a textual eksplikacija lentelė, Vision reads room names + areas + finish codes deterministically. When it doesn't, Vision infers rooms from wall dimensions alone — a much more interpretive task with higher variance.

## Production response (committed in same PR)

`extractor/vision_call.py` now emits a `WARN`/`INFO` warning when `eksplikacija_source_page` is null:

> "Šis projektas neturi rastos eksplikacijos lentelės. Rezultatai išvesti iš brėžinio matmenų ir gali svyruoti tarp paleidimų (±10–20% kambarių skaičiui, daugiau plytelių zonoms). Rekomenduojama peržiūrėti rankiniu būdu arba paleisti 2–3 kartus."

UI can render this as a banner. User decides whether to manually review, run 2-3× and average, or accept the single-run output.

## Future work

If non-eksplikacija projects become a common scenario:
1. **Auto-retry strategy** — when `eksplikacija_source_page is None`, run extract_interior 3× and return median per metric. 3× cost on those projects only.
2. **Voting on rooms list** — match rooms across runs by paskirtis + plotas (within 10%) and require ≥2/3 agreement.
3. **Structured pre-pass** — short Vision call (low effort, low res) just to identify "is there an eksplikacija lentelė?" — if yes, proceed with single call; if no, trigger 3× strategy.
