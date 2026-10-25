# Ground Truth v2 — per-page-per-field schema

The v1 format (e.g. `a_laida_roof.yaml`) records a SINGLE value per field
plus the roofer's sąmata. That hides where each number came from and
makes inter-page consistency uncheckable. v2 records the value AND the
page it came from for every input field, so the eval harness can
measure: (a) end-to-end pipeline accuracy AND (b) per-page extraction
accuracy AND (c) inter-page agreement (which pages disagree, by how
much).

## Required top-level keys

```yaml
project_id: <slug>
source_pdf: <relative-path-from-repo-root>
roof_type: <dvislaitis|keturslaitis|vienslaitis|mansardinis|plokscias>

# Final ground-truth values used for strategy input (the answer):
roof_input:
  axis_to_axis_length_m: 25.34
  axis_to_axis_width_m: 7.12
  eaves_overhang_from_axis_m: 0.0
  wall_thickness_m: 0.30
  slope_angles_deg: [30]
  chimney_count: 1
  rooflight_count: 0
  windows_count: 0

# Per-page extraction labels (what the system SHOULD read from each page).
# A field absent from a page entry means "not visible on that page" —
# system should not extract it from there.
pages:
  - page_num: 46
    page_class: floor_plan
    fields:
      axis_to_axis_length_m: 25.59
      axis_to_axis_width_m: 7.12
      sub_dimensions_m:
        axis_to_axis_width_m: [4.10, 3.02]   # sub-segments that sum to overall

  - page_num: 48
    page_class: stogo_planas
    fields:
      roof_type: dvislaitis
      axis_to_axis_length_m: 25.34      # matches floor plan within tolerance
      axis_to_axis_width_m: 4.61        # PARTIAL — half-rafter detail; system MUST drop
      chimney_count: 1
      visible_slope_angles_deg: [35]    # WRONG — pjūvis says 30; system MUST prefer pjūvis

  - page_num: 49
    page_class: section
    fields:
      slope_angles_deg: [30]
      ridge_height_m: 8.45
      eaves_height_m: 3.20
      wall_thickness_m: 0.30
      soflitas_depth_m: 0.50

# Roofer's manual sąmata for end-to-end comparison
roofer_samata:
  source: <where-this-came-from>
  pvm_included: false
  line_items:
    - position: stogas
      qty: 231
      unit: m2
      eur_per_unit: 20.00
      sum_eur: 4620.00
    # ... etc
  total_eur_no_vat: 20458.00
```

## Notes

- All linear values in metres; angles in degrees; counts as integers.
- `page_class` values match `extractor.page_classifier.PageType` enum values exactly.
- `sub_dimensions_m` is OPTIONAL per page; only filled if the drawing
  shows sub-segment labels next to an overall axis dimension.
- `visible_slope_angles_deg` on stogo_planas pages records WHAT THE
  DRAWING LABELS (even if wrong); the actual slope used in computation
  goes in the section page's `slope_angles_deg`.
- `eaves_height_m` on SECTION pages: height of eaves (drip line) above
  ground/datum, in metres. Used by dvislaitis sienos formula to compute
  the gable wall area; missing this zeros out a major line item.
- `soflitas_depth_m` on SECTION pages: depth of the horizontal soffit
  panel under the eaves overhang (outer wall face → drip edge), in
  metres. Used by dvislaitis sienos formula (perimeter × soflitas × 2)
  to compute the soffit panel area.
- `sum_eur` on `roofer_samata.line_items`: total € for this line item
  (= `qty` × `eur_per_unit`). Required — used by the eval harness to
  cross-check against the roofer's quoted `total_eur_no_vat`.
- Fields absent from a page entry mean "not visible on this page; system
  should not extract from there." If the system DOES extract it, that's
  a false-positive recall and the eval reports it.

## `answers.json` — the person's answers (interior eval, v4 re-base 2026-10-25)

`ground_truth/<slug>/answers.json` holds what a person would type when the app asks. Phase 3b
removed every model and default number from the sąmata rows: where the drawing's text writes no
ceiling height the wall rows are blank and the app asks one question („Kokio aukščio lubos?"). A
blank row is not a wrong row, so `eval_harness.py` applies this file **before the rows are built**,
in the plain and the `--replay-geometry` passes, and prints per project how many answers it
supplied and which rows are STILL blank („Asmens atsakymai ir tikri trūkumai"). `--no-answers`
reproduces the instrument as it was before. A project without the file is scored exactly as before.
It is applied only under `--recompute` (the frozen pass has no tail to apply it to).

```json
{
  "slug": "objektas_x",
  "lubu_aukstis_m": 2.8,
  "lubu_auksciai": {"102": 3.2},
  "saltiniai": [{"m": 2.8, "kur": "sąmatos eilutė nr. 1"}],
  "_pastabos": ["anything recorded and NOT applied"]
}
```

- `lubu_aukstis_m` — one number for every room whose height the drawing did not give; null = no answer.
- `lubu_auksciai` — optional, per room number; wins over the project value.
- `saltiniai` — where each number is stated (for the human reader).

How it is applied: the same edit the Prielaidos panel posts to `/api/recompute-quantities` —
`api.recompute_quantities._apply_assumption_edits(rooms, {"lubu_auksciai": {nr: m}})` (room height,
source `user_override`) and `_overrides.lubu_auksciai[nr]` — to every room whose height is not
`DRAWING` class by `row_provenance.height_class`. Values outside 1,5–8 m are ignored (the panel's
own range).

Rules for what may go in (the file is generated by `scripts/eval_answers_from_truth.py`):

- Only what the truth files state: the contractor's row labels in `contractor_samata_parsed.json`
  (a height written in a label) and `truth.json` › `notes_for_evaluator` / `gt_totals` sources.
- **Never** from `ai_extract.json` (the frozen model extract — the guess being removed), and never
  from `truth.json` › `gt_dimensions` (its heights are Vision-derived; `notes_for_evaluator` says so).
- Never a number that is itself a row of his sąmata (a Rotband share, a rubbish volume, a fixture
  count): feeding it back makes the row a copy of the answer key, not a measurement.
- Heights above 3 m are recorded in `_pastabos` only; which rooms are high is not stated.
