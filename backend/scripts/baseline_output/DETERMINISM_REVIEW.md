# Phase 6.5.2 — Determinism Stress Test Results

Captured: 2026-04-27 10:02:35
Setup: 3 runs per project. Vision is non-deterministic;
this characterizes run-to-run variance per metric.

## Per-metric variance

| Project | Metric | Min | Mean | Max | CV% |
|---------|--------|-----|------|-----|-----|
| P2 | rooms | 7.00 | 7.33 | 8.00 | 7.9% |
| P2 | bendras_plotas_m2 | 92.50 | 94.50 | 95.50 | 1.8% |
| P2 | dazymo_total | 305.98 | 310.68 | 317.93 | 2.1% |
| P2 | kampai_total | 165.48 | 206.53 | 227.66 | 17.2% |
| P2 | plyteles_sienos_total | 2.28 | 25.23 | 39.00 | 79.3% |
| P2 | plyteles_grindys_total | 3.80 | 8.60 | 12.00 | 49.7% |
| P2 | pozicijos_count | 20.00 | 22.67 | 24.00 | 10.2% |

## Verdict

Threshold: CV >10% indicates a metric where averaging/voting may help.

⚠ **4 metrics flagged**:
- P2 kampai_total: CV 17.2% (values: [165.48, 227.66, 226.46])
- P2 plyteles_sienos_total: CV 79.3% (values: [39.0, 2.28, 34.4])
- P2 plyteles_grindys_total: CV 49.7% (values: [10.0, 3.8, 12.0])
- P2 pozicijos_count: CV 10.2% (values: [24.0, 20.0, 24.0])