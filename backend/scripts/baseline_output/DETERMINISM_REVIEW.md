# Phase 6.5.2 — Determinism Stress Test Results

Captured: 2026-04-27 11:20:36
Setup: 3 runs per project. Vision is non-deterministic;
this characterizes run-to-run variance per metric.

## Per-metric variance

| Project | Metric | Min | Mean | Max | CV% |
|---------|--------|-----|------|-----|-----|
| P1 | rooms | 15.00 | 15.00 | 15.00 | 0.0% |
| P1 | bendras_plotas_m2 | 180.00 | 180.00 | 180.00 | 0.0% |
| P1 | dazymo_total | 490.86 | 506.28 | 536.07 | 5.1% |
| P1 | kampai_total | 299.40 | 318.96 | 330.85 | 5.4% |
| P1 | plyteles_sienos_total | 117.40 | 126.72 | 133.95 | 6.7% |
| P1 | plyteles_grindys_total | 40.61 | 61.69 | 79.86 | 32.1% |
| P1 | pozicijos_count | 40.00 | 42.00 | 44.00 | 4.8% |
| P3 | rooms | 0.00 | 13.33 | 20.00 | 86.6% |
| P3 | bendras_plotas_m2 | 0.00 | 178.47 | 267.71 | 86.6% |
| P3 | dazymo_total | 0.00 | 505.47 | 770.78 | 86.6% |
| P3 | kampai_total | 0.00 | 289.23 | 442.30 | 86.7% |
| P3 | plyteles_sienos_total | 0.00 | 141.62 | 218.29 | 86.7% |
| P3 | plyteles_grindys_total | 0.00 | 57.91 | 86.87 | 86.6% |
| P3 | pozicijos_count | 0.00 | 30.33 | 50.00 | 87.9% |

## Verdict

Threshold: CV >10% indicates a metric where averaging/voting may help.

⚠ **8 metrics flagged**:
- P1 plyteles_grindys_total: CV 32.1% (values: [79.86, 40.61, 64.61])
- P3 rooms: CV 86.6% (values: [0.0, 20.0, 20.0])
- P3 bendras_plotas_m2: CV 86.6% (values: [0.0, 267.71, 267.71])
- P3 dazymo_total: CV 86.6% (values: [0.0, 770.78, 745.62])
- P3 kampai_total: CV 86.7% (values: [0.0, 425.38, 442.3])
- P3 plyteles_sienos_total: CV 86.7% (values: [0.0, 218.29, 206.56])
- P3 plyteles_grindys_total: CV 86.6% (values: [0.0, 86.87, 86.87])
- P3 pozicijos_count: CV 87.9% (values: [0.0, 41.0, 50.0])