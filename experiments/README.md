# Experiments — investigations that didn't ship

Code in this directory was built, run on real data, and ARCHIVED because
the empirical results didn't justify production integration. Each
subdirectory or file carries a comment / README documenting:

  • What the hypothesis was
  • What was measured
  • Why it wasn't worth keeping in the production path

This directory exists so future engineers don't re-discover the same
empirical dead-ends.

## Contents

- **`door_arc_detector/`** — OpenCV door swing detection for free
  scale-factor inference. Empirical false-positive rate: 235-1381
  arcs per page (vs. <50 real doors). See its README for details.

- **`cot_perimeter_pilot.py`** — Chain-of-thought self-verification
  on per-room crops for perimeter accuracy. Same failure mode as
  per-room zoom: model picks sub-rectangles inside open-plan rooms.
  $1.74 spent confirming. The companion prompt is
  `prompts/perimeter_cot.txt.archived`.

## When to revisit

- New corpus of vector (non-raster) PDFs → door arc detection may
  become viable
- A new Vision model with materially better at-image geometry
  reasoning → CoT perimeter pilot worth re-running
- A specific contractor convention that motivates either approach

Until then: don't burn budget re-running these.
