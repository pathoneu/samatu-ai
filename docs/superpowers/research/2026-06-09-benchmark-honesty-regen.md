# Making the totals benchmark honest — live regeneration of the truth-set extracts

**Date:** 2026-06-09
**Author:** automated session (Claude)
**Depends on / supersedes context in:** `docs/berzas_audit_notes.md` § "2026-06-09 PART 2 — THE BENCHMARK WAS MEASURING LOST CODE"

> ## ⛔ REGENERATION INCOMPLETE — ANTHROPIC API CREDIT EXHAUSTED MID-RUN
>
> The live run (`/tmp/regen_truth_extracts.log`, manifest
> `eval_runs/regen_sprint_1781026986.json`) **ran out of API credit** after
> $2.31. Outcome:
>
> | project | result | extract on disk now |
> |---|---|---|
> | **lazunu** | ✅ complete (3 voting rounds, $0.47) | **FRESH honest** |
> | **ciurliu** | ✅ complete (3 voting rounds, $0.52) | **FRESH honest** |
> | **berzas** | ⚠️ credit died on voting round 3; apdailos + doors passes failed → paint-degraded **artifact** | **rolled back to enriched baseline** |
> | **objektas_b** | ❌ `all_voting_runs_failed` (credit) — never written | enriched baseline (untouched) |
> | **romainiai** | ❌ `all_voting_runs_failed` (credit) — never written | enriched baseline (untouched) |
>
> So the benchmark is **partially honest**: lazunu + ciurliu now score against
> fresh production; berzas + objektas_b remain on the enriched cache. The
> degraded berzas extract was **rolled back** (not scored) because its paint
> metrics collapsed for the wrong reason (credit failure of the apdailos pass,
> not the pipeline) — keeping it would inject a fake-bad number.
>
> **To finish:** top up Anthropic credits, then re-run for the 3 remaining:
> ```bash
> venv/bin/python scripts/regenerate_truth_extracts.py --only berzas
> venv/bin/python scripts/regenerate_truth_extracts.py --only objektas_b
> venv/bin/python scripts/regenerate_truth_extracts.py --only romainiai   # MAE-excluded, optional
> venv/bin/python eval_harness.py --totals-only --detailed
> ```

---

## TL;DR

`eval_harness.py --totals-only` scored each project against a **cached, enriched**
`ground_truth/<slug>/ai_extract.json` — files built (commit `c91dd3b`) when two
now-reconstructed reader modules existed locally, PLUS offline adjacency
enrichment (`scripts/apply_adjacency.py`) PLUS hand corrections. That is **more**
than fresh production produces, so the published MAE **overstated real production
accuracy** (≈7.5× on berzas: honest ≈14.95% vs published 1.99%, per the audit's
degraded-pipeline measurement).

This session:
1. **Backed up** every cached extract (contractor-validated baseline) →
   `eval_runs/cached_baseline_backup_2026-06-09/` (git HEAD also preserves them).
2. **Fixed the eval "honest filter"** so a *fresh* extract that emits `0.0`
   against a real >0 truth is scored as the genuine −100% collapse it is (and
   loudly flagged), instead of being silently dropped — which on a non-berzas
   project would have *hidden* a collapsed headline metric.
3. **Regenerated** the cached extracts by running the CURRENT restored pipeline
   **live**, with N-pass voting ON (the production default), via
   `scripts/regenerate_truth_extracts.py` — **2 of 5 completed before the API
   credit ran out** (see the ⛔ box above).
4. **Re-ran** `--totals-only` and recorded the honest production MAE for the two
   that completed (ciurliu, lazunu); berzas + objektas_b still await a credit
   top-up.

---

## Why the benchmark was dishonest

From `docs/berzas_audit_notes.md` PART 2 (adversarially verified):

- `apdailos_reader.py` + `doors_reader.py` were never committed and were lost;
  `vision_call.py` called them inside a `try/except` that swallowed the
  `ModuleNotFoundError`. For weeks, production had **no** `sienu_apdailos_breakdown`
  (→ walls-paint fell to a legacy path that hardcodes `walls_paint=0` for
  tamburas/garažas → **−41% walls paint**) and **no** door recount (doors stuck
  at pass-1's 9–10 vs truth 14).
- Per-room ceiling zoom ran 1/11 rooms → uniform 2.82 m heights.
- The adjacency pass (`n_partition_walls`, which feeds the kampai *pusiniai* term)
  was **never in production** — it was applied OFFLINE by `scripts/apply_adjacency.py`
  and baked into the cached extracts. Production uploads got `n_partition_walls=0`
  → kampai lost ~96 m (≈20%).

All three were **reconstructed / fixed on 2026-06-09** (commits `68235d8`
restored the readers, `f26665f` put adjacency on the floor page, `8fbb31e` made
N-pass voting the default). So production *can now* reproduce most of the
enrichment — but the **cached extracts still carried hand corrections and offline
enrichment** that fresh output does not, so the benchmark kept overstating
accuracy until those cached files were regenerated.

### Three distinct accuracy regimes (don't conflate them)

| Regime | What it is | berzas headline MAE |
|---|---|---|
| **Published / enriched** | cached extract + `apply_adjacency` + hand corrections | **1.991%** (measured this session) |
| **Degraded honest** | the *broken* pipeline the audit caught (readers lost, zoom 1/11, no adjacency) | **≈14.95%** (audit PART 2) |
| **Current honest** | restored readers + N-pass voting, fresh live output | **BLOCKED on credit** (rolled back) |

The "current honest" number for **berzas** is the one that matters most — it is
**what a real user gets today** — but it requires a *complete* fresh run, which
the credit exhaustion prevented. It should land **worse than the enriched 1.99%**
(we removed the hand corrections) but **better than the degraded 14.95%** (the
readers + voting + adjacency are now genuinely in production). A partial earlier
verification (`/tmp/berzas_restore_verify.log`, full 3-round voting *with* a
working apdailos pass) put fresh berzas at **kampai −10.6%, combined paint +2.3%,
n_partition_walls 34, heights [2.8,3.0,3.4]** — strong, but not the headline-metric
MAE, and not reproducible here until credits are restored.

**ciurliu and lazunu, however, DID complete** — and they confirm the thesis (below).

---

## Scope: 5 regenerated, not "~11"

The registry (`ground_truth/registry.yaml`) has **6 projects**, of which **5 have a
cached `ai_extract.json`** to regenerate:

| slug | role | regen attempted | extract now | notes |
|---|---|---|---|---|
| berzas | MAE originator (only full `gt_dimensions`) | ⚠️ partial (credit) | enriched (rolled back) | the enrichment-dependent project; fresh run degraded by credit failure |
| objektas_b | MAE-contributing | ❌ failed (credit) | enriched (untouched) | 65-page TP, largest |
| ciurliu | MAE-contributing | ✅ complete | **FRESH honest** | 3-page A3 plans, smallest scope |
| lazunu | MAE-contributing | ✅ complete | **FRESH honest** | apartment, bundled sheets |
| romainiai | **scope_mismatch** | ❌ failed (credit) | enriched (untouched) | eval skips it *before* reading the extract; MAE-excluded regardless |
| sernu | **blocked_for_vision_extraction** | ⊘ skipped (correct) | none (n/a) | no architectural floor plan in the bundle; no `ai_extract.json` exists; Vision would produce garbage |

So the headline MAE is driven by **4 projects** (berzas, objektas_b, ciurliu,
lazunu); of those, **2 are now honest** (ciurliu, lazunu) and **2 await a credit
top-up** (berzas, objektas_b). The task brief's "~11 projects" overcounts; the
real regenerable set is 5.

`run_vision_on_truth_set.py` could **not** do this job: it filters out
`has_cached_extract: true` (only berzas carries that flag) and is designed to
*fill missing* extracts, not *refresh existing* ones. Hence the dedicated
`scripts/regenerate_truth_extracts.py`.

---

## The eval "honest filter" fix

`run_totals_only_multi` had a single rule for both AI sides:

```python
if ai_mode in ("replay", "ai_extract") and actual == 0.0 and truth > 0.5:
    not_emitted.append(label); continue   # excluded from MAE
```

That conflates two very different things:

- **`replay`** (legacy cached santrauka): a `0.0` can genuinely mean *the cached
  santrauka schema never tracked this field* — a documentation gap, fairly excluded.
- **`ai_extract`** (FRESH production): a `0.0` against a real >0 truth is a **real
  metric collapse** — production actually produced nothing where the contractor
  measured something. Silently dropping it lets a non-berzas project's collapsed
  headline metric **vanish from the honest MAE**.

**Fix** (`eval_harness.py`): the exclusion now applies **only to `replay`**. For
`ai_extract`, the `0.0`-vs-truth metric stays in `scored` (it lands as a ~−100%
fail, correctly hurting the MAE) **and** is recorded in a new `metrics_collapsed`
list, printed as a loud `🔴 COLLAPSED METRICS` footnote so it can never hide behind
the project average.

---

## Method

1. Backup (verified by sha256): `eval_runs/cached_baseline_backup_2026-06-09/<slug>/`.
2. `scripts/regenerate_truth_extracts.py` — reads the registry, regenerates every
   project with an existing extract + usable PDF (skips `blocked_for_vision_extraction`),
   `ENABLE_EXTRACTION_VOTING=1 VOTING_N=3`, smallest-PDF-first, $19 budget / $5
   per-project soft cap. Stamps `_meta._regen_provenance` onto each saved extract so
   it is recognisable as fresh-not-enriched.
3. `eval_harness.py --totals-only --detailed`.

---

## Results

### Before (enriched cached extracts + pre-fix eval)

```
slug           AI side         scored     MAE %    worst %
berzas         ai_extract           5    1.991     4.745
objektas_b   ai_extract           2    9.501    18.207
ciurliu        ai_extract           2   11.533    12.530
lazunu         ai_extract           2   10.607    14.219
romainiai      excluded_scope_mismatch
sernu          excluded_blocked
overall MAE: 6.658%  (n=11 metric observations)
```

Note even *here* objektas_b/ciurliu/lazunu only score **2** metrics each — their
truth.json tracks only combined-paint + LED. berzas is the only project with the
full 5-metric headline set.

### After (PARTIAL: ciurliu + lazunu fresh, rest enriched, fixed eval)

```
slug           AI side         scored     MAE %    worst %
berzas         ai_extract           5    1.991     4.745     ← still enriched (rolled back)
objektas_b   ai_extract           2    9.501    18.207     ← still enriched (untouched)
ciurliu        ai_extract           2   27.419    33.314     ← FRESH honest
lazunu         ai_extract           2   10.235    18.012     ← FRESH honest
romainiai      excluded_scope_mismatch
sernu          excluded_blocked
overall MAE: 9.479%  (n=11 metric observations)
```

The overall 6.658% → 9.479% jump is driven **entirely by ciurliu** flipping to
fresh. No collapse-footnote fired — neither fresh extract zeroed a headline metric.
(The overall number is a **mixed** figure — 2 honest + 2 enriched — and should not
be read as a clean "honest production MAE" until berzas + objektas_b regenerate.)

### Per-project honesty deltas (the two that completed)

| project | metric | enriched cache | fresh production | honest delta |
|---|---|---|---|---|
| **ciurliu** | Combined paint (items 16+17) | −10.54% (347.13) | **−21.52%** (304.49) | nearly 2× worse |
| | LED nišų ilgis | +12.53% (18.95) | **+33.31%** (22.45) | worse |
| | **project MAE** | **11.53%** | **27.42%** | **2.4× overstated by enrichment** |
| | room recall | 7 rooms | **6 rooms** (−1) | a lost room drives the paint shortfall |
| **lazunu** | Combined paint (items 16+17) | −14.22% (129.16) | **−18.01%** (123.45) | slightly worse |
| | LED nišų ilgis | +6.99% (11.32) | **−2.46%** (10.32) | actually *better* |
| | **project MAE** | **10.61%** | **10.24%** | enrichment barely mattered here |
| | room recall | 4 rooms | 4 rooms | unchanged |

**Reading:** ciurliu is the clean confirmation of the task's thesis — the enriched
cache made it look ~2.4× more accurate than fresh production actually is, largely
because fresh extraction loses a room (recall variance) and over-reads LED. lazunu
shows the enrichment was *not* doing much work there (no apdailos page; its
combined-paint gap is a deterministic perimeter/recall issue the cache didn't fix
either). Both contradict the published "production is ~accurate" story for the
no-eksplikacija-heavy projects.

---

## Cost

From `eval_runs/regen_sprint_1781026986.json`:

| project | status | cost | sec | rooms |
|---|---|---|---|---|
| lazunu | ok | $0.47 | 213 | 4 |
| ciurliu | ok | $0.52 | 309 | 6 |
| berzas | partial (round 3 + apdailos failed) | $1.32 | 211 | 11 (degraded) |
| romainiai | extractor_error (credit) | $0.00 | 39 | — |
| objektas_b | extractor_error (credit) | $0.00 | 164 | — |
| **total** | | **$2.31** / $19 budget | | |

(romainiai/objektas_b reached the free pdfplumber eksplikacija pass, then every
Vision call 400'd on credit, so $0 Vision for them.)

---

## Caveats & remaining gaps

- **Single-contractor benchmark.** All 6 projects are Rangovas A; factors
  reflect Rangovas A scope conventions only (see registry header).
- **romainiai stays MAE-excluded** by `scope_mismatch` (AI extracts the whole
  45-page doc, truth covers the 4.1–5.1 punktas subset). Its fresh extract exists
  on disk but does not enter the score.
- **Voting is non-deterministic.** N-pass median voting reduces run-to-run variance
  but does not eliminate it; re-running the regen can shift a metric by a few %.
- **Truth is still AI-seeded** for several metrics (see CLAUDE.md "Open / next").
  These MAE numbers measure agreement-with-contractor-confirmed-totals where they
  exist, and agreement-with-Claude-seeded-truth elsewhere.

## Rollback

```bash
for s in berzas objektas_b ciurliu lazunu romainiai; do
  cp -p eval_runs/cached_baseline_backup_2026-06-09/$s/ai_extract.json     ground_truth/$s/
  cp -p eval_runs/cached_baseline_backup_2026-06-09/$s/ai_extract_meta.json ground_truth/$s/ 2>/dev/null
done
# or: git checkout HEAD -- ground_truth/*/ai_extract.json
```
