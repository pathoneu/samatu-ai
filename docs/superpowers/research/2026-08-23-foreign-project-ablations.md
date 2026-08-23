# Foreign-project ablations — how the pipeline behaves on drawings we have never seen (2026-08-23)

**Why:** every accuracy figure Pathon has ever reported comes from 4 projects (2 of them the launch contractor's own), and every production run so far used the best of them (Beržų, 3.10%). There is **no out-of-sample interior PDF anywhere** — not on disk, not in the production DB (checked 2026-08-22). The contractor is on vacation without his files. So instead of guessing how a foreign project behaves, we manufactured the ways one differs from Beržų while keeping Beržų's contractor-verified truth: every run is a measurement against real numbers.

**Tooling:** `scripts/build_berzas_ablations.py`; registry slugs `berzas_bundle`, `berzas_no_eksplikacija`, `berzas_no_isklotines`, `berzas_flat150` (flag `ablation_of: berzas` — excluded from the corpus average, scored one at a time with `venv/bin/python eval_harness.py --project <slug> --vision`, ~€2.50 each). PDFs are untracked like every client-named fixture.

## Scoreboard

| Variant | Simulates | Headline MAE | Notes |
|---|---|---|---|
| Clean Beržų | reference | **3.10%** | corpus extract |
| `bundle` — Beržų's 17 sheets appended behind 37 architectural sheets of another building | what a contractor actually uploads | **34.67% → 5.13%** | foreign eksplikacija joined by nr → `eksplikacija_guard` fix (commit 53fd20b) |
| `no_isklotines` — wall elevations removed | plans without išklotinės | **5.63%** | finish reader falls to the apdailos plan only |
| `flat150` — every page rasterised at 150 DPI, no text layer | scanned / iLovePDF re-export | **11.69% → 1.51%** | text-blind reader locators → Pass-1 classification fallback (same commit) |
| `no_eksplikacija` — room table removed from ALL nine plan sheets | plan with no room schedule | **15.37%** | areas become round `wall_dim_calc` guesses; room identities drift; confidence correctly medium/low |

All local runs had `WALL_ELEVATION_EXTRACT` unset — **the same as production**. The benchmark extract was built with it on (23 elevations); stripping them and rescoring leaves 3.098% / 7.625% byte-identical, so the lane is invisible to the scored metrics (it feeds wall tile, which is `incomplete`-confidence and excluded). Ablation numbers therefore reflect the production pipeline.

## Finding 1 — a room table that isn't ours (bundle)

Pass-1 found all 11 rooms with correct names. The eksplikacija reader returned the **first** table it saw — page 8, SA-02's schedule for a different building — and the merge (2026-07-29 nr-first join, which fixed duplicate-name collapsing and had no name check) attached its areas by number: "111 Tėvų vonia" ← "111 LAUKO TERASA 66.47 m²", tagged `plotas_saltinis=eksplikacija`. A real contractor bundle carries the architectural part's schedule for the *same* building, so this is the expected upload shape.

**Fix** (`backend/extractor/eksplikacija_guard.py`): name agreement over nr-matched rows (LT-normalised tokens, wet-room synonym class, containment). `< 50%` over `≥ 3` matches → reject → re-read the table from the pages the rooms were read from ±2 (pypdf subset, page numbers mapped back) → accept only if *that* table agrees → else keep Vision areas + LT warning. Row-level contradiction guard for single colliding numbers. Re-run: reject p8 at 5/11, accept p39 at 11/11, all rooms correct. Residual ~2 pts over clean = Pass-1 reading inside a 53-page context (the 20-page soft cap was exceeded — the new preflight warns before the spend).

## Finding 2 — readers that go blind on a scan (flat150)

Areas, heights, LED and floor were exact (Vision read the table from the image), but wall paint was −31.6%: the apdailos and door-type readers locate their pages by scanning the **text layer**, found nothing, and returned `skipped` silently. Pass-1 had classified p10 `finish_schedule` and p11–17 `wall_elevation` correctly from the images all along. Locators now fall back to that classification when the text scan is empty (the pattern `sanitary_fixture_reader` already used); text hits still win, so text-layer projects are byte-identical. Re-run: 1.51%.

## Finding 3 — the room table is the load-bearing input (no_eksplikacija)

With no schedule anywhere, areas come from `wall_dim_calc` and are round integers (7.0, 52.0, 20.0): the model is estimating, not measuring. Per-room errors −63%…+87%; total floor +8%. Room identities drift with it (104 Darbo kambarys → "Vonia (svečių)", which also flips its finishes). Confidence came back medium/low, so the honest review queue flags them — this is the product working as designed, not a pipeline bug. The deterministic answer (area from dimension chains on the plan) is the Čiurlių-class problem and remains open.

**Methodology lesson:** the first no-eksplikacija build removed the table from p2 only and scored 6.5% — Beržų repeats the table on all nine plan sheets and the reader found the next copy. An ablation is only valid once the signal is verified gone from *every* page; `plotas_saltinis=eksplikacija` with exact truth values after an ablation means the ablation failed.

## What a foreign project will do

- Room table + wall elevations present (even inside a big bundle): **3–6%**.
- No wall elevations: **~6%**.
- Scanned / flattened: **within jitter of clean** (was 12% before this fix).
- No room table at all: **~15%**, with the doubtful rooms visibly flagged.

Spend: 7 paid runs (4 planned + 3 re-runs: one invalid ablation, two fix validations), ≈ €17.50.
