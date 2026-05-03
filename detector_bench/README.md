# Symbol-Detection Bake-Off

Empirical comparison of 6 symbol-counting pipelines on 3 real Lithuanian
project PDFs.

## ⚠️ Caveat — read first

**Ground truth in this run is AI-seeded, not human-confirmed.** Every "accuracy"
number below is *relative to Claude Sonnet's first-pass count*, not relative to
the actual correct count. Use these numbers for **relative comparison between
pipelines**, not as absolute quality measurements.

To upgrade to real ground truth: run `venv/bin/python -m detector_bench.build_ground_truth`
(interactive, ~1 hour) then re-run `benchmark.py`.

## How to reproduce

```bash
cd /Users/ignasgaldikas/samatu-ai
# (one-time) set up an unverified seed via AI:
venv/bin/python -m detector_bench.auto_seed_ground_truth
# OR (preferred) confirm by hand:
venv/bin/python -m detector_bench.build_ground_truth   # ~1h with user

# then:
venv/bin/python -m detector_bench.benchmark            # ~30-60 min, costs ~$5
```

## Pipelines tested

1. **p1_baseline_vision** — Claude Sonnet direct ("count outlets")
2. **p2_text_driven** — pdfplumber keyword search (regex on extracted text)
3. **p3_template_match** — cv2.matchTemplate from auto-extracted legend glyphs
4. **p4_hybrid** — text positions as anchors + template confirmation
5. **p5_grounding_dino** — GroundingDINO via Replicate API (open-vocabulary)
6. **p6_claude_tool_orch** — Claude Sonnet 4.6 orchestrating a deterministic count tool

## Test set

| PDF | Pages | Drafting style | Notes |
|---|---|---|---|
| `projektas_1_breziniai.pdf` | 65 (A3) | text-heavy callouts | PDF24/Ghostscript export, all raster |
| `projektas_3_breziniai.pdf` | 45 (A3 rot 270°) | clean symbol-driven | dedicated SUTARTINIAI ŽENKLAI on pp 23-24 |
| `Visi techniniai 01.28.pdf` | 17 (A3) | mixed | iLovePDF re-export |

Per-page ground truth at `ground_truth/<label>.yaml` (6 pages: 2 per PDF).

## Results

See `results/<date>-bakeoff.md` for the latest run.

## Findings (run 2026-05-03 09:01)

### Aggregate ranking

| Pipeline | Mean accuracy | Total runtime | Cost (6 pages) | Errors |
|---|---|---|---|---|
| `p1_baseline_vision` | **49.3%** | 171s | $0.60 | 1 |
| `p2_text_driven` | 41.8% | 45s | $0.00 | 0 |
| `p3_template_match` | 24.5% | 84s | $0.00 | 2 |
| `p6_claude_tool_orch` | 23.3% | 392s | $1.20 | 3 |
| `p4_hybrid` | 16.7% | 50s | $0.00 | 0 |
| `p5_grounding_dino` | 16.7%* | 18s | $0.30 | 60 |

*Pipeline 5 ran out of Replicate credit after first call (60 / 72 calls returned 402 Insufficient Credit). Its 16.7% is meaningless until billing is restored.

### Per-PDF breakdown

| | P1 (text-heavy callouts) | P3 (clean symbol-driven) | VT (mixed) |
|---|---|---|---|
| `p1_baseline_vision` | **77.4%** | 40.9% | 58.7% |
| `p2_text_driven` | 28.1% | **41.8%** | 50.6% |
| `p3_template_match` | 0.0% | 26.3% | 35.1% |
| `p4_hybrid` | 0.0% | 5.0% | 66.7%† |
| `p5_grounding_dino` | 0.0% | 5.0% | 66.7%† |
| `p6_claude_tool_orch` | 11.1% | 24.7% | 26.7% |

†VT's 66.7% is a statistical artifact — VT page 7 has 5/6 truth values = 0, so detectors that returned 0 score 100% for free on those entries.

### What actually worked / didn't

- **Claude Vision direct wins overall (49.3%)** — surprising; the simplest pipeline beats every fancier path. Likely partly biased by ground truth being AI-seeded (see caveat below).
- **Pipeline 2 text-driven is the only zero-cost option that's competitive** (41.8%). On P1 page 8 it hit `kistukinis_lizdas: 41/41 = 100%` — text annotations alone are sufficient for that drafting style.
- **Pipeline 3 template-match is broken on P1** (0% — over-counts by 100×, e.g. `1772 dvigubas_jungtukas` where truth is 5). Root cause: legend crops from P1 page 8 captured tiny ~30 px symbols that match anywhere on the busy drawing. Better cropping or color-aware matching would help, but template match is fundamentally fragile here.
- **Pipeline 4 hybrid completely broke** — 0 text anchors found because pdfplumber `extract_words()` tokenization differs from `extract_text()`. Bug in the hybrid implementation; not the approach's fault.
- **Pipeline 6 Claude tool-orch ran cheap CV under expensive Claude orchestration** ($1.20 — 2× the baseline cost) but inherited Pipeline 3's fragility. Worst cost-effectiveness.

### Critical caveat

**Ground truth is AI-seeded, not human-confirmed.** Every "accuracy" number above measures _agreement with Claude Sonnet's first-pass count_, not absolute correctness. This biases Pipeline 1's score upward (it IS Claude). Real human ground truth could shift rankings significantly — for instance, if Claude under-counted on P3 page 23's busy electrical layout, all pipelines that disagreed (Pipeline 3 returning 173 for `iš.1`) might actually be CLOSER to truth than the seed.

Until human-confirmed ground truth lands, treat this report as **relative pipeline disagreement analysis**, not absolute quality measurement.

## Recommendation

### What to ship if forced to pick today

**Primary detector: `p1_baseline_vision`** — Claude Sonnet 4.6 reading the rendered page directly, asking "count {symbol_code}". 49.3% mean accuracy, $0.10/page, ~3s/symbol. Pair with **provenance disclosure** in the UI (`"AI estimated — verify before use"`) and a **one-click correction tool** (the existing polygon editor adapted for point-counting).

**Don't ship as primary, keep for fallback:** `p2_text_driven` for projects with strong text annotations. Run it cheaply alongside Pipeline 1 and surface disagreements as flags ("AI Vision says 47, text mentions 33 — please verify").

### What to kill / not invest in further

- **`p3_template_match`** — 24.5% with 100× false positive rates on busy drawings. The fundamental approach is fragile; multi-scale rotation match on tiny symbols at 200 DPI is too noisy.
- **`p4_hybrid`** — implementation broken; even when fixed the text-anchor approach is constrained to text-annotated PDFs and underperforms Pipeline 2 alone there.
- **`p6_claude_tool_orch`** — most expensive (392s runtime, $1.20), worse accuracy than Pipeline 1. The orchestration overhead doesn't pay off when the underlying tool (Pipeline 3) is unreliable.

### What to test next (in priority order)

1. **Real human ground truth.** Without it, this benchmark is circular (Claude scoring Claude). The 1-hour interactive flow at `build_ground_truth.py` exists; users haven't run it. Highest information gain per hour of work in the entire project right now.

2. **Pipeline 5 GroundingDINO retest** — Replicate credit ran out after first call. With $5-10 of credit, get the 60 missing data points. Open-vocabulary models are designed for "find all instances of [text description]" — if it works on construction drawings, it could leapfrog Pipeline 1.

3. **YOLOv8 fine-tuned on labeled symbols** — out of scope for this bake-off (need labeled training data we don't have), but the natural next step if Pipelines 1 and 5 plateau under 70%.

4. **Hybrid pipeline 1 + 2** — instead of running just Pipeline 1, run BOTH and surface disagreements as user-verification prompts. Keeps cost similar but adds a free precision signal.

### Bottom line

**No pipeline reaches the 70-80% accuracy bar that would let symbol counting "just work."** This validates your earlier instinct that AI symbol counting is genuinely hard, especially on Lithuanian construction PDFs with diverse drafting conventions. The honest path forward is shipping a 50%-accurate AI count + a fast manual-correction tool, not chasing a perfect detector.

The interactive viewer everyone (us, Togal, Kreo, Bluebeam) builds isn't a luxury — it's load-bearing. **Build the count-correction UI well, accept that AI gives you 50%, and let the user finish the job in 30 seconds instead of 30 minutes.**
