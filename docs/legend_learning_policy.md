# Legend learning policy (D4)

## Three layers

1. **Project legend** — automatic within a project; saved at
   `data/legends/<project_id>.json` whenever the user saves/edits the
   per-project legend in `LegendEditor`.
2. **Architect legend** — opt-in only after the user verifies the same
   mapping in **≥2 projects from the same architect**. Surfaces at
   `data/legends/architect/<architect>.json`. Promotion requires
   `opt_in=true` AND `verified_in_projects` of length ≥2.
3. **Global legend** — **deliberately does not exist**. No silent
   cross-project learning that could poison future projects.

## Why this exact compromise

Council R3 split:
- ChatGPT proposed three layers (project / architect-opt-in / global).
- Gemini proposed per-project ephemeral only ("junior draftsmen change
  symbols daily").

We landed with ChatGPT's structure but Gemini's caution: architect
persistence pays back (LT residential market is ~20 active firms) but
ONLY with explicit user confirmation. Never auto-promote.

## API surface

- `POST /api/legends/{project_id}` — save/update a project legend.
- `GET  /api/legends/{project_id}` — load a project legend.
- `POST /api/legends/architect/{architect}/promote` — opt-in promotion
  (body: `{opt_in: true, verified_in_projects: [...]}`).
- `GET  /api/legends/architect/{architect}` — load an architect legend.
- ❌ `/api/legends/global` — does not exist by design.

## Enforcement

`backend/api/legends.py` rejects:
- Any `/promote` call where `opt_in != true`.
- Any `/promote` call with fewer than 2 verified projects.

Tests in `backend/tests/api/test_legends_d4.py` lock these invariants
(7 cases: schema rejection + opt-in flow + global-endpoint absence).

## Operational

- Prompt-injection helper (`backend/extractor/legend_injection.py`) reads
  the project legend and splices it into specialised Opus prompts after
  base rules. If the architect-level legend is also present (post-opt-in),
  callers can merge it before injection. Default merge precedence: project
  > architect (project always wins on conflict).
- `LegendEditor.jsx` (Week 5 follow-up) exposes the architect-level
  opt-in checkbox only when the project has been saved at least once.
