# The family template — hold-out measurement, 2026-09-04

The council's own €0 falsification of week 2, run before any UI work:

> **The template hypothesis can be falsified for €0**: hold one of the six
> sąmatas out, build the family template from five, measure how many held-out
> rows it covers. That settles A-vs-C before a line of product code.
> — `2026-09-04-council-transcript-contractor-trust.md`, blind spot 2

`sernu` — the real holdout — has a parsed sąmata but **no cached extract**, so
nothing can be rendered for it. Instead each of the five corpus sąmatas takes
its turn: the template is built from the other four, the held-out project is
rendered through it, and the result is scored by `row_scorecard`, the same
instrument the headline number uses. `sernu` was never read.

Reproduce (zero API spend, cached extracts only):

```
venv/bin/python scripts/samata_template_holdout.py
venv/bin/python scripts/samata_template_holdout.py --json
```

## The table

| project | his rows | template **offers** | **filled** | **±10 %** | ±10 % with suggestions | plain app list |
|---|---:|---:|---:|---:|---:|---:|
| objektas_a | 53 | **86,8 %** | 5,7 % | 0,0 % | 37,7 % | 37,7 % |
| objektas_b | 113 | **53,1 %** | 4,4 % | 0,9 % | 9,9 % | 9,9 % |
| objektas_c | 37 | **73,0 %** | 5,4 % | 2,8 % | 22,2 % | 22,2 % |
| objektas_d | 50 | **80,0 %** | 6,0 % | 8,0 % | 36,0 % | 36,0 % |
| **mean (n=4)** | | **73,2 %** | **5,4 %** | **2,9 %** | **26,5 %** | **26,5 %** |
| romainiai | 15 | 73,3 % | 26,7 % | 6,7 % | 13,3 % | 13,3 % |

*romainiai* sits outside the mean for the reason `ground_truth/registry.yaml`
already gives (`scope_mismatch`) — the same exclusion the headline MAE and the
row scorecard apply, kept identical so one project cannot be in one number and
out of another.

**offers** — his rows whose FAMILY the template contains at all. Decided by the
template alone; no reading, no quantity.
**filled** — of his rows, the ones the render actually put a number into. Gated
by `samata_template.is_fillable`: verified (he pressed „Teisinga", typed it, or
locked it) or ledgered (the row carries its own `contributions`/`roll_up`).
**±10 %** — what ships, scored by `row_scorecard`. A blank cell can never be
within ±10 %, so this number is bounded by `filled`.
**±10 % with suggestions** — the same sheet with the greyed `_siulomas_kiekis`
promoted into the quantity. **Not a shippable number.** It is the ceiling the
sheet would reach if every cell we can compute were trustworthy.

## The honest reading

**1. The template buys COVERAGE, and that is what he complained about.**
73,2 % of his billed rows now have a line in our output under his own heading
and his own wording — against a plain app list where 38–58 % of his rows had no
counterpart at all (`2026-09-04-row-scorecard-baseline.md`). On the project we
know best it is 86,8 %. That is the whole thesis of week 2, and it holds
out-of-sample: every one of those numbers is from a template that never saw the
project it was scored on.

**2. It costs nothing in precision. Zero, exactly.** The suggestion column
equals the plain-app-list column on all five projects, to the decimal. That is
not a coincidence and it is not luck — it is the consequence of the itemisation
rule below, and it is the strongest result here: **rendering through his
template is a strict improvement.** The rows we could already reproduce we still
reproduce; the rows he bills and we never mentioned now at least exist, blank,
with a typable cell.

**3. What ships today is 2,9 %, and that is the design working, not failing.**
The council's third blind spot: *at a 14–27 % hit rate, dropping our numbers
into HIS labelled rows makes wrong numbers more billable, not less.* So an
unverified number does not fill a cell. On a freshly-read project almost nothing
is verified and only 5–7 rows per project carry a ledger, so **5,4 %** of his
rows get a number and the rest are blank or greyed. The gap between 2,9 % and
26,5 % is not an accuracy gap — it is **the entire value of week 3**. Every room
he confirms and every family that gains a contribution ledger converts a greyed
suggestion into a filled cell, and the ceiling is already paid for.

That reframes the week-4 target. „≥ 60 % of his rows present under his labels"
is met by the skeleton (73,2 %). „≥ 40 % within ±10 %" is **not** an extraction
problem any more: the numbers exist and score 26,5 %; they are withheld because
nobody has looked at them. Verification throughput is the binding constraint.

**4. The one thing the template initially made worse — and the fix.**
The first implementation gave each family ONE summed row. That cost 11 rows and
3,6 pp across objektas_a and objektas_b, every one of them a family HE bills on
several lines:

| his row | his qty | plain list | one summed row | why it broke |
|---|---:|---:|---:|---|
| GKP ant lubų, dvigubas karkasas (2,8 m) | 102,78 | 93,42 ✓ | 154,97 ✗ | our two height tiers summed into one cell |
| GKP ant lubų, dvigubas karkasas (3,4 m) | 62,82 | 61,55 ✓ | — | „granularity — he bills 2 rows, we emit 1" |
| Dušo maišytuvo potinkinė dalis | 2,0 | 2,0 ✓ | 4,0 ✗ | concealed + exposed parts summed |
| Dušo maišytuvo virštinkinė dalis | 2,0 | 2,0 ✓ | — | same |

It is also the wrong ANSWER, not merely the wrong score: he cannot split
154,97 m² back into the 2,8 m and 3,4 m carcasses, and those are different work
at different rates — while he can always add two of our lines together.

The rule now is **his own evidence**: a family he has billed on more than one
line in at least one sąmata (`n_rows > seen_in`) is *itemised*, and the render
gives it one row per matching app row — his label, plus the detail that tells
the lines apart:

```
Gipso kartono montavimas
  GKP monatavimas ant lubų, įrengiant dvigubą karkasą (standartinis aukštis)   93,42 m²
  GKP monatavimas ant lubų, įrengiant dvigubą karkasą (virš 3 m aukščio)       61,55 m²
```

An average („he *usually* splits it") was tried first, at ≥ 1,5 rows per sąmata,
and missed every family in this corpus — he splits GKP ceilings in one project
of three, because the split follows the DRAWING (two ceiling heights, three tile
formats), not a habit. The second condition is ours: we only itemise when we
actually computed more than one line, so a family he splits and we do not still
lands on one row. 12–21 of the ~90 template families are itemised.

This is why the precision cost is exactly zero: `score_rows` sums OUR side when
he bills one row and pairs greedily when he bills several, so itemising
reproduces the plain list's scoring in both cases. **Merging is what loses.**

**5. The residual — what the template still does not offer (26,8 %).**
Coverage is worst on objektas_b (53,1 %), which is also the project with 19
unmapped families and 57 missing rows in the baseline. Its misses are the
one-project-only families the scorecard baseline already catalogued: MEP
(ventilation diffusers by model, recuperator, AC runs, switchboard, cabling,
alarm), finish carpentry from a walk-through (moldings, sills, door-leaf
painting, a handle swap, widening an opening), garage and stairwell work our
room model skips, bespoke items, and catch-alls („Montavimo darbai", „Smulkūs
papildomi darbai"). Almost none can be *read* off a drawing.

They are also, by construction, the families a five-sąmata template cannot
learn: seen once, they are „kartais" if they are in the template at all, and
seen zero times they are absent. **The residual shrinks with his sąmata count,
not with our reader** — every sąmata he uploads is more skeleton. That is the
argument for making „upload a sąmata" a first-class action, not a one-off
import.

## Caveats, stated plainly

- **The template is held out; the CONCEPT TABLE is not.** The 60 mappings in
  `scripts/reconcile_samata_lines.CONCEPTS` were hand-written against this
  corpus, so the mapping has seen every project it scores. That inflates the
  ±10 % columns (not `offers`, which the template alone decides) and is exactly
  why `sernu` stays reserved for the week-4 claim.
- **One contractor.** `registry.yaml` warns all six sąmatas are one person. The
  section-key rule (his headings drift in the tail, never the head) and the
  itemisation rule are statements about HIM. A second contractor is still the
  missing evidence, unchanged since the council said so.
- **Four projects, 253 rows.** objektas_a (86,8 %) and objektas_b (53,1 %)
  bracket a wide range; the mean is not a tight estimate.
- **`filled` will move without any of this changing.** It reads the project's
  saved verification state, and every cached extract here has none. On a project
  the contractor has walked through it is a different number — which is the
  point, and the thing to measure at the week-2 session.

## What this settles

The council's A-vs-C question. **A first was right**, and the measurement says
so more sharply than the argument did: the template is a strict improvement —
+73,2 pp of coverage at zero precision cost — while the correction product (C)
is what converts the 26,5 % ceiling into shippable cells. They are not
alternatives; A builds the sheet, C fills it. Build A, then C, in that order,
which is the sequence the plan already has.

Implementation: `backend/extractor/samata_template.py`, `backend/api/samata_templates.py`,
`scripts/samata_template_holdout.py`. Headline MAE 7,82 % and the row scorecard
26,5 % are unchanged by all of it.
