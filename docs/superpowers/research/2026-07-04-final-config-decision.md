# Final Analysis-Config Decision (2026-07-04)

All 11 experiment runs complete. Full matrix (headline MAE / all-scored MAE per project; averages on equal 4-project sets where marked 4/4):

| Config | Objektas A | Objektas B | Objektas C | Objektas D | Avg headline | Avg all-scored | Cost (4 proj) |
|---|---|---|---|---|---|---|---|
| Opus 4.8 raster (prod today) | 12.3 / 16.2 | 34.2 / 29.1 | 41.7 / 42.8 | 16.3 / 34.1 | 26.1% | 30.5% | €4.93 |
| Fable 5 raster | 13.0 / 15.2 | 25.0 / 35.3 | 23.2 / 33.5 | 17.7 / 28.8 | 19.7% | 28.2% | €16.18 |
| Mixed vote 2F+1O | 5.0 / 11.3 | 35.5 / 42.4 | 18.9 / 33.9 | 13.5 / 29.7 | 18.2% | 29.3% | €16.37 |
| **Opus 4.8 + native PDF** | **5.5 / 11.7** | 33.5 / 29.2 | **15.1 / 31.7** | **10.7 / 35.1** | **16.2%** | **26.9%** | **€4.71** |
| Fable + native (Objektas A only) | 11.6 / 12.4 | — | — | — | (1 proj) | | €3.57 |
| Fable + agentic zoom (2 proj) | 12.5 / 14.6* | 22.3 / 48.6 | — | — | | | €11.57 |

*Objektas A agentic = no-op (zoom skipped, all rooms eksplikacija-covered) → doubles as a determinism sample: Fable raster 13.0 vs 12.5 across independent runs ⇒ run-to-run variance ≈ 0.5pp.

**Text-layer richness (median chars/page on plan pages):** Objektas A 1550, Objektas D 1349, Objektas C 82, Objektas B 0. Native-PDF gain tracks text presence almost perfectly, and even 82 chars/page (sparse labels+dims) produced the largest single gain (41.7→15.1).

> **Correction (2026-07-04 pre-lock-in audit):** the earlier claim here — "cost of native = raster cost (Objektas B €2.80 vs €2.81), text channel nearly free / graceful degradation on text-free PDFs" — over-read that run. The Objektas B native run **fell back to raster images via the size cap** (`_meta.experiment.native_pdf.fallback_reason: subset_exceeds_size_limit`), so it measured raster-vs-raster, NOT true native on a text-free PDF. We have **no datapoint** for true native on text-free documents, and Anthropic's internal PDF rendering (~45% of our raster pixel budget) makes it plausibly WORSE. The B-2 text-richness gate (see Lock-in conditions below) makes the question moot by design: text-free PDFs (< 10 median chars/page over selected pages) never go native.

## Decision

**Production config: Opus 4.8 + native-PDF pass-1, always on.**
- Best average accuracy of every config tested (16.2% headline / 26.9% all-scored) — beats pure Fable (19.7%) and mixed voting (18.2%).
- Cheapest (€1.18/project avg — 3.4× cheaper than Fable-based configs; same cost as today's prod).
- ~~No routing complexity: on text-free PDFs native degrades gracefully to raster-equivalent at equal cost.~~ **Corrected:** that "graceful degradation" datapoint was a size-cap fallback (see correction above), not true native. Text-free PDFs are now excluded from native mode by the B-2 gate instead of relying on unproven degradation.
- Fable stays available per-reader via env overrides; **Fable + agentic zoom** is the designated **escalation path for text-free hard documents** (Objektas B: 22.3 vs Opus-native 33.5 headline) — but NOT default yet: its all-scored regression on that project (35.3→48.6) needs investigation before it's trusted beyond headline quantities.
- Mixed voting shelved: its Objektas A win (5.0 vs 5.5) is within run noise of Opus+native at 4× the price.

## Pre-flip gate (cheap)
Determinism repeat: 2× Opus+native on Objektas A+Objektas D (~€2.5) — confirm the 5.5/10.7 results reproduce within ~1pp before locking the default.

## Follow-ups queued
1. Investigate agentic-zoom all-scored regression on Objektas B (zoom re-reads may hurt category metrics while helping headline).
2. Text-free escalation router (median chars/page < ~20 → offer/auto-run Fable+agentic re-analysis) — after (1).
3. Missing readers (rozetės, šviestuvai, difūzoriai) — exemplar-based per the counting-ceiling evidence.
4. Fable refusal-fallback config whenever Fable is used in production paths.

## Economics note (feeds W3 pricing)
Per-project analysis cost at the chosen config: **€0.51–€2.80, avg ≈ €1.18** (65-page worst case €2.80).

> **Metering caveat (audit R-4):** these figures are **Pass-1-only** metering. Sub-readers (apdailos/doors), zoom re-reads, and eksplikacija-vision calls are NOT metered in these numbers today, so the true total per-project cost is **higher** than €1.18 avg. A full cost rollup is queued and must land **before W3 pricing uses these numbers**. The "≥ €5 ⇒ 40% margin" conclusion below is therefore provisional.

At any single-project price ≥ €5 the 40% margin target is comfortably met *on Pass-1 costs alone* — re-verify against the full rollup.

## Lock-in conditions (implemented)
The pre-lock-in audit set three MUST conditions before native-PDF became the default; all three are on `viewer-rebuild`:

- **B-1 — API-reject fallback** (`a1e15fc`): a native-document round that hits `anthropic.BadRequestError` (or fails twice on the same document payload) is rebuilt as raster images and retried; the shared payload flips so remaining voting rounds also go raster. Recorded as `_meta.experiment.native_pdf.fallback_reason="api_rejected_document"`.
- **B-2 — text-richness gate** (`1171663`): median extractable chars/page over the SELECTED Pass-1 pages (pdfplumber, zero API cost) < 10 → raster images, `fallback_reason="text_free_pdf"`. `text_median_chars_page` is recorded on every native-considered run — the production segmentation metric.
- **B-3 — default ON with escape hatch** (the flip commit immediately following this doc update — grep `NATIVE_PDF_DEFAULT_ON` in `backend/extractor/vision_call.py`): native is ON unless `SAMATU_PDF_NATIVE=0/false`; `SAMATU_PDF_NATIVE=1/true` forces on. Rollback is one line: `NATIVE_PDF_DEFAULT_ON = False`. Effective mode + reason (env override vs default) is logged at every extraction start.
