# Door arc detector — empirically unreliable, archived

## Hypothesis

Door swing arcs on LT residential floor plans have radii equal to door
widths (700/800/900/1000 mm). Detecting these arcs via OpenCV
HoughCircles + arc-fraction filtering would yield a project-level
mm-per-pixel scale factor for free (no Vision spend).

## Empirical result (2026-06-01, on real project floor plans)

| Project | Page | Arcs detected | Median scale (mm/px) |
|---|---:|---:|---:|
| berzas | 2 | **790** | 16.20 |
| bacveviciaus | 1 | **1381** | 11.88 |
| ciurliu | 1 | **536** | 20.23 |
| lazunu | 1 | **235** | 39.13 |

A typical LT residential floor plan has fewer than 50 doors. The
detector returns 5–25× the true door count: every circular element on
the page (light fixtures, plumbing symbols, dimension callout circles,
corners at the rendered DPI) passes the arc-fraction filter.

The scale estimates are also wildly inconsistent across same-DPI
renders (11.88 to 39.13 mm/px), confirming that the median is
dominated by false positives rather than real door arcs.

## Why this is archived rather than fixed

Closing the false-positive gap would require additional filters:
1. Wall-attachment check (arcs adjacent to detected wall lines)
2. Pairing with door-rectangle detection
3. Density / clustering filter (don't accept circles in cabinet
   detail areas)
4. Per-project DPI calibration

Each filter adds complexity and per-project tuning. The empirical
evidence is that the underlying signal-to-noise is too low without
substantially more careful filtering than the original spec proposed.

## When to revisit

If the user supplies a new corpus of PDFs where:
- The drawings are vector PDF (not raster) so circles are geometrically clean
- OR the DPI rendering can be substantially increased
- OR a future spec adds wall-adjacency filtering BEFORE counting arcs

The test harness in `door_arc_detector.py` can be re-run to measure
false-positive rates on the new inputs. If they drop below ~50 per
page on a labelled floor plan, the approach becomes viable.
