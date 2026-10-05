# Blind batch protocol

> 2026-10-05 · audit testing-eval-1 and testing-eval-12 · harness: `eval_harness.py --blind-once`

**Why.** No project in the eval is unseen. objektas_g/h were blind for one run on 2026-09-05 and
every round since has been diagnosed and fixed against them; the row scorecard's holdout project has
no extract, so it holds nothing out. Every number `eval_harness.py` prints is therefore in-sample, and
nothing says how the engine does on a drawing nobody developed against. A blind batch is the only
instrument for that, and it stays one only while nobody looks inside it.

**Blind means** that no person and no agent has opened the project's drawing, its Vision read, its
sąmata, or any per-row or per-metric output of it. Agents read the working tree freely, so a file
inside the repository is not blind, whatever it is called.

## 1. Get a batch

- Two or three interior projects, each a drawing PDF plus the contractor's sąmata with quantities for
  the same scope. Ideally from a **second contractor**: every truth today is one contractor's
  convention, so a batch from him measures new drawings, not new conventions.
- One person, the founder, receives the files and handles them. He gives each project a codename
  (`objektas_i`, `objektas_j`, …; never a client, street, designer or contractor name, and the
  denylist applies) and does not discuss what is inside with whoever develops the engine.

## 2. Seal it (once per project: a paid run, founder approval)

Outside the repository, in `$SAMATU_BLIND_DIR/<codename>/` (default `~/pathon-blind/<codename>/`):

- `project.pdf`: the drawing. Scoring works without it, but then the tail's €0 text-layer lanes do
  not run; the log records this as `pdf_lanes`.
- `contractor_samata_parsed.json`: `{"line_items": [{"nr", "name", "unit", "quantity"}, …]}`,
  parsed by the founder by hand. `scripts/parse_all_samatas.py` cannot be used as it stands: it is
  driven by the registry and writes into `ground_truth/`, inside the repository. Whoever parses the
  sąmata does not work on the engine that round.
- `ai_extract.json`: the sealed read, one production extraction written without being looked at:

  ```bash
  cd backend && ../venv/bin/python -c "import json,sys; from extractor.vision_call import extract_interior; from extractor.universal_rules import default_paint_prefs; json.dump(extract_interior(open(sys.argv[1],'rb').read(), rules_override=default_paint_prefs()), open(sys.argv[2],'w'), ensure_ascii=False)" "$SAMATU_BLIND_DIR/objektas_i/project.pdf" "$SAMATU_BLIND_DIR/objektas_i/ai_extract.json" >/dev/null 2>&1
  ```

  Re-seal (a new paid run, the same way) only when the paid pipeline changes (prompts, readers,
  model), before the next release candidate is scored, and never because a blind number moved. The
  log shows each read's hash, so a re-seal is visible.
- The registry entry is tracked and holds a codename only, with no paths and no truth:

  ```yaml
  - slug: objektas_i
    name: "Objektas I"
    blind: true
    contractor: "Rangovas B"
    added: "2026-10-xx"
  ```

  The normal eval (`--totals-only`, `--rows`, both gates) skips it and prints how many blind projects
  exist. `--project`, `--rescore` and `--debug-project` refuse it.

## 3. Score it, exactly once per release candidate

Commit the release candidate (clean tree), then, before it is pushed:

```bash
venv/bin/python eval_harness.py --blind-once
```

It runs today's engine on each sealed read (zero API) and prints ONE line: the batch's billed-lines
MAE and the share of his rows within ±10 %. It appends ONE line to `ground_truth/blind_log.jsonl`
with the commit, a code fingerprint, the per-project aggregates and each sealed read's hash. It
prints no per-row, per-family or per-project figure. It refuses a dirty tree, code that is already in
the log (so the commit that adds the log line cannot be scored again), a missing file, and a slug
that is not a codename. Commit the log line on its own (`eval: blind score for <sha>`).

## 4. Rules

- Never open the blind folder, never run another mode on a blind slug, never print its rows.
- Never change anything *because* the blind number moved. Diagnose a blind regression by reproducing
  it on the in-sample corpus; read the blind number again only at the next release candidate.
- The eval only measures. No factor, default or rule comes from a blind sąmata, as from any sąmata.
- **Burned:** if anyone sees inside, whether by accident or to diagnose, the project is in-sample
  from that day. Move its files into `ground_truth/<codename>/` like the rest, replace `blind: true`
  with `blind_until: <date>` and a one-line reason, and find a replacement.
- **Retire** the batch after about ten scorings or three months, whichever comes first. Every look
  leaks a little, and a number watched across many release candidates becomes one more thing tuned on.
- `ground_truth/blind_log.jsonl` is append-only. Never edit or delete a line.

## 5. What the number is

It uses the same two definitions as the in-sample headline (`docs/DEVELOPING.md`, Measure accuracy):
his billed lines compared Σ-vs-Σ per family, and his rows within ±10 %. Two caveats remain. Each
project has one sealed Vision read, so reading variance is not measured. A batch from the same
contractor says nothing about a second contractor's conventions.
