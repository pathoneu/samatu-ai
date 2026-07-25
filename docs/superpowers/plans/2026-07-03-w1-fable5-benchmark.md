# W1 — Fable 5 Analysis-Engine Upgrade, Benchmark-Gated

> **For agentic workers:** Tasks W1.1–W1.2 are implementer work (backend only). W1.3–W1.4 (smoke test + benchmark runs + verdict) are controller work — do NOT run paid API calls from a subagent.

**Goal:** Centralize model config, make cost accounting model-aware, wire a `--model` axis through the eval harness, then run Opus 4.8 vs `claude-fable-5` on the 4-project ground-truth corpus and decide the flip with numbers.

**Authoritative API facts (from the claude-api reference — do not re-derive):**
- IDs: `claude-opus-4-8` (current), `claude-fable-5` (candidate — exact, no suffix).
- Pricing per MTok: Opus 4.8 $5 in / $25 out; Fable 5 $10 in / $50 out. Cache READ = 0.1× input price. Cache WRITE = 1.25× (5-min TTL) or 2× (1-hour TTL — what vision_call_v2 uses).
- **`temperature`/`top_p`/`top_k` are REMOVED on both models — sending any returns 400.** The founder's "temperature 0" item is descoped; determinism = strict schemas + voting. Never add a temperature param.
- Fable 5: thinking always on (send NO `thinking` param; explicit `disabled` 400s), no assistant prefill, `output_config.effort` available (`low`→`max`, default high), 128K max output, same tokenizer as Opus 4.8, requires 30-day data retention (ZDR org → 400 on every request), safety classifiers may return `stop_reason: "refusal"` (HTTP 200) — check stop_reason before reading content.
- Benchmark runs use NO fallbacks (a silent Opus rescue would contaminate the comparison; a refusal is a data point). The eventual production config (post-decision) SHOULD add `betas:["server-side-fallback-2026-06-01"], fallbacks:[{"model":"claude-opus-4-8"}]` on Fable calls.

## Task W1.1 — Central model config + model-aware pricing + telemetry

**Files:** Create `backend/models_config.py` (+ `backend/tests/test_models_config.py`); Modify `backend/pricing.py` (+ its tests), `backend/db.py`, `backend/main.py`, `backend/extractor/{vision_call_v2,prompt,apdailos_reader,door_type_reader,sanitary_fixture_reader,legend_injection,page_classifier}.py`, `backend/extractor/vision/symbol_detector.py`, `backend/api/config.py`.

1. `models_config.py`: `ROLES` = {`vision_pass1`, `vision_pass2`, `doors`, `apdailos`, `sanitary`, `legend`, `page_classifier`, `symbols`, `extraction`, `chat`} → default `"claude-opus-4-8"` each. `model_for(role)` resolution: `SAMATU_MODEL_<ROLE>` env → `MODEL_OVERRIDE` env (global) → legacy envs (`VISION_MODEL` for vision roles, `EXTRACTION_MODEL` for extraction — keep backward compat) → default. Docstring records the no-temperature rule + exact IDs.
2. Replace ALL 32 `"claude-opus-4-8"` literals with `model_for(...)` calls (module-level constants become lazy or resolved at call time — call time preferred so env changes apply per-run; check each reader). `api/config.py` returns the live resolved map.
3. `pricing.py`: READ THE CURRENT FILE FIRST — verify the cache-read rate (scout suggests it may charge ~0.9× instead of the correct 0.1×; if so that's a live bug — fix it and note the correction). New shape: `RATES = {"claude-opus-4-8": {"in": 5.0, "out": 25.0}, "claude-fable-5": {"in": 10.0, "out": 50.0}}` per MTok USD; `calc_claude_cost_usd(input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0, model="claude-opus-4-8", cache_ttl="1h")` — cache read at 0.1× in-rate, cache write at 2× for "1h" / 1.25× for "5m". Unknown model → ValueError (never silently price wrong). Update all call sites to pass model + cache_write tokens where `_meta` has them.
4. `db.py`: additive `ALTER TABLE` migrations adding `model TEXT` to `extractions` and `usage_events` (follow the existing migration pattern in db.py — read how prior columns were added). `record_extraction`/`record_usage` accept + store model.
5. Anthropic client: vision-path calls get a longer timeout for Fable's minutes-long turns — per-call `client.with_options(timeout=600.0)` on the heavy vision calls (vision_call_v2, prompt.py path, symbol_detector already streams). Do NOT change the global client.
6. Ensure `_meta` includes `model` on every reader's call result (vision_call.py aggregation ~line 2258 + each reader).
7. Tests: `model_for` resolution chain (env monkeypatching); pricing math for both models incl. cache read/write and the ValueError; db migration idempotence. Run the full backend test suite; `pytest` green. Commit per logical unit (config, pricing, db, readers).

## Task W1.2 — Harness model axis + comparison report

**Files:** Modify `eval_harness.py`; Create `scripts/compare_model_runs.py`.

1. `eval_harness.py`: `--model <id>` flag → sets `MODEL_OVERRIDE` env BEFORE importing/instantiating the pipeline; run output dir/file names carry the model (e.g. `eval_runs/<model>/...`); `--vision` runs must bypass cached extracts (force fresh) when `--model` is set; capture per-project `_meta` roll-up (model, input/output/cache tokens, cost USD+EUR via new pricing, wall time) into the result JSON.
2. `scripts/compare_model_runs.py`: takes two result JSONs → markdown table: per project × key metric (truth, A, B, pct_err A, pct_err B), per-project MAE, totals (tokens, € cost, minutes), and a per-reader breakdown if `_meta` carries it. No API calls — pure report.
3. Test: a unit test with two synthetic result JSONs → stable table output. `pytest` green. Commit.

## Task W1.3 — Smoke test (CONTROLLER ONLY, ~$0.2)

One real `claude-fable-5` call through OUR client path: verifies org data-retention acceptance (no 400), the model ID, `output_config.format` json_schema compliance on a mini extraction prompt, `_meta` token capture, and stop_reason handling. Abort W1.4 if this fails and report why.

## Task W1.4 — Benchmark runs + verdict (CONTROLLER ONLY, costs real €)

- Fresh `--vision` runs on the 4 primary projects (berzas, objektas_b, ciurliu, lazunu) × both models. Sequential, watch for refusals/timeouts.
- `compare_model_runs.py` → benchmark log at `docs/superpowers/research/2026-07-03-fable5-benchmark.md` (the founder's Task 1.6 deliverable).
- **GATE: founder sees the table and decides the flip** (global / mixed per-reader / stay). Only then W1.5.

## Task W1.5 (post-gate) — Production config + validation layer v2

Flip decision applied via models_config defaults; Fable production calls get refusal fallbacks (see header); validation layer v2 (sums-of-parts, plausibility bands, low-confidence re-prompt) as its own plan.
