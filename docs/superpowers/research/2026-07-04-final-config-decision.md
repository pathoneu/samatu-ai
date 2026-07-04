# Final Analysis-Config Decision (2026-07-04)

All 11 experiment runs complete. Full matrix (headline MAE / all-scored MAE per project; averages on equal 4-project sets where marked 4/4):

| Config | Beržų | Bacvevičiaus | Čiurlių | Lazūnai | Avg headline | Avg all-scored | Cost (4 proj) |
|---|---|---|---|---|---|---|---|
| Opus 4.8 raster (prod today) | 12.3 / 16.2 | 34.2 / 29.1 | 41.7 / 42.8 | 16.3 / 34.1 | 26.1% | 30.5% | €4.93 |
| Fable 5 raster | 13.0 / 15.2 | 25.0 / 35.3 | 23.2 / 33.5 | 17.7 / 28.8 | 19.7% | 28.2% | €16.18 |
| Mixed vote 2F+1O | 5.0 / 11.3 | 35.5 / 42.4 | 18.9 / 33.9 | 13.5 / 29.7 | 18.2% | 29.3% | €16.37 |
| **Opus 4.8 + native PDF** | **5.5 / 11.7** | 33.5 / 29.2 | **15.1 / 31.7** | **10.7 / 35.1** | **16.2%** | **26.9%** | **€4.71** |
| Fable + native (Beržų only) | 11.6 / 12.4 | — | — | — | (1 proj) | | €3.57 |
| Fable + agentic zoom (2 proj) | 12.5 / 14.6* | 22.3 / 48.6 | — | — | | | €11.57 |

*Beržų agentic = no-op (zoom skipped, all rooms eksplikacija-covered) → doubles as a determinism sample: Fable raster 13.0 vs 12.5 across independent runs ⇒ run-to-run variance ≈ 0.5pp.

**Text-layer richness (median chars/page on plan pages):** Beржų 1550, Lazūnai 1349, Čiurlių 82, Bacvevičiaus 0. Native-PDF gain tracks text presence almost perfectly, and even 82 chars/page (sparse labels+dims) produced the largest single gain (41.7→15.1). Cost of native = raster cost (Bacvevičiaus: €2.80 vs €2.81) — the text channel is nearly free.

## Decision

**Production config: Opus 4.8 + native-PDF pass-1, always on.**
- Best average accuracy of every config tested (16.2% headline / 26.9% all-scored) — beats pure Fable (19.7%) and mixed voting (18.2%).
- Cheapest (€1.18/project avg — 3.4× cheaper than Fable-based configs; same cost as today's prod).
- No routing complexity: on text-free PDFs native degrades gracefully to raster-equivalent at equal cost.
- Fable stays available per-reader via env overrides; **Fable + agentic zoom** is the designated **escalation path for text-free hard documents** (Bacvevičiaus: 22.3 vs Opus-native 33.5 headline) — but NOT default yet: its all-scored regression on that project (35.3→48.6) needs investigation before it's trusted beyond headline quantities.
- Mixed voting shelved: its Beržų win (5.0 vs 5.5) is within run noise of Opus+native at 4× the price.

## Pre-flip gate (cheap)
Determinism repeat: 2× Opus+native on Beржų+Lazūnai (~€2.5) — confirm the 5.5/10.7 results reproduce within ~1pp before locking the default.

## Follow-ups queued
1. Investigate agentic-zoom all-scored regression on Bacvevičiaus (zoom re-reads may hurt category metrics while helping headline).
2. Text-free escalation router (median chars/page < ~20 → offer/auto-run Fable+agentic re-analysis) — after (1).
3. Missing readers (rozetės, šviestuvai, difūzoriai) — exemplar-based per the counting-ceiling evidence.
4. Fable refusal-fallback config whenever Fable is used in production paths.

## Economics note (feeds W3 pricing)
Trustworthy per-project analysis cost at the chosen config: **€0.51–€2.80, avg ≈ €1.18** (65-page worst case €2.80). At any single-project price ≥ €5 the 40% margin target is comfortably met.
