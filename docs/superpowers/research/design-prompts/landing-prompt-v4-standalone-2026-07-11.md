# Pathon landing — standalone design prompt v4 (2026-07-11)

Paste everything below the line into any designer AI. Self-contained — no
codebase access needed. Goal: a genuinely new direction to compare against the
current landing, so it deliberately avoids prescribing palette, typefaces, or
layout. The AI owns the visual language; we own the truth about the product.

---

You are the design lead a small studio trusts with its reputation. Design a
complete marketing landing page for **Pathon**. The brief is unusual: you get
full creative authority over the visual language — palette, typography,
layout, motion, texture, art direction are all yours. What you don't get to
change is the truth about the product, the audience, and the positioning laws
below. Read everything first. Then commit to one bold concept and execute it
with precision.

## The ambition

Make a page that a skeptical visitor screenshots and sends to a colleague with
the message "žiūrėk, kaip gerai padaryta" ("look how well this is made"). Not
"nice for an AI tool." Not "clean." Memorable — a page with a point of view
that could not have been generated for any other product. Before you design
anything, write one sentence: **"This page is a ___."** (an instrument panel? a
site survey? a folded drawing coming to life? a bill of quantities as
typography? — yours to invent). Every choice after that sentence must serve it.
If a section doesn't serve the concept, redesign the section, not the concept.

## The product (this is all true — design from it, don't invent features)

Pathon is a Lithuanian B2B SaaS for construction contractors. The user uploads
a construction project PDF (interior design drawings: floor plans, wall
developments, ceiling plans, room schedules). Pathon reads the drawings,
identifies rooms and elements, and computes work quantities using the same
formulas a professional Lithuanian estimator uses — paintable wall area,
plaster, drywall sheets, flooring, baseboards, LED coves, waterproofing. It
assembles a kiekių žiniaraštis (bill of quantities) and a sąmata (estimate).
The user reviews, enters their own prices, and exports Excel (with live
formulas) or a Lithuanian-format estimate PDF. 21% PVM handled, reverse charge
for renovation projects.

The honest, differentiating detail — make it visible in the design:

- **Every quantity carries a confidence mark**: green = read directly from the
  drawing; yellow = computed with an assumption; red = a default was used,
  check it. The system tells you exactly which few lines to review — e.g.
  "check 3 lines out of 46" — instead of asking for blind trust.
- **Assumptions are editable and everything recalculates live** — change a
  ceiling height and every affected line updates instantly.
- The product UI is a PDF plan viewer with colored, clickable room zones over
  the actual drawing, next to a quantities table. Product mockups on the page
  must depict THIS (plan + zones + table with confidence dots), not an invented
  analytics dashboard. Use invented, neutral demo data (rooms like "Svetainė
  18,4 m²", "Vonia 5,2 m²") — never real client names, addresses, or totals.

True numbers you may use: reading a project takes ~10–15 minutes; doing the
same takeoff by hand takes from several hours to a couple of days; first
project is free for a company; pricing is €12 one-off per project, €49/mo Pro
(10 projects), €149/mo Studio (35 projects), prices ex-VAT. Do not invent
customer counts, testimonials, or accuracy percentages.

## The audience (design for this person, not for other designers)

Lithuanian construction company owners and self-employed contractors. They do
their own quantity takeoffs in the evening after a day on site. They are
practical, price-aware, allergic to hype, and burned by software that
overpromises. Trust is won with precision, honesty about limits, and evidence —
never with startup theatre. The creative tension you must resolve: the page has
to be visually arresting enough to be unforgettable AND credible enough that a
builder in Kaunas thinks "these people understand my work." A page that wins
awards but smells like a toy fails. A page that is credible but forgettable
also fails. Solve both.

## Copy — free to rewrite, laws locked

You may restructure sections and write all copy fresh. Write it in natural
Lithuanian (the founder will polish it — draft quality is fine; no lorem
ipsum, no English placeholders). These positioning laws are non-negotiable:

1. **The value is TIME.** The user does this work themselves; Pathon turns
   hours-to-days of manual measuring and calculating into minutes plus a short
   review. Never claim or imply they currently pay someone else for estimates
   (no "estimators cost €X" framing).
2. **Outcome-led, never accessory-led.** Pathon is the tool, not a plugin for
   some other tool. Exports (Excel, PDF) are features, never the headline.
   Never frame as "works with / feeds / compatible with X."
3. **Honesty is the brand.** The confidence system exists because AI reading
   of drawings isn't perfect — the product says "check these 3 lines before
   you quote." Copy that promises perfection breaks the product's own promise.
   Confidence, not arrogance.
4. Tone: konkretus, ramus, be pompastikos — the voice of a precise colleague,
   not a pitch deck. Numbers over adjectives.

Content the page must cover, in whatever structure serves your concept:
what it does + for whom (immediately clear in the hero), how it works (upload →
reading → review → priced estimate), the trust/confidence system, live
recalculation of assumptions, exports, pricing (the four tiers above, first
project free as the risk-free entry), and one final call to action. A short
FAQ is optional. Navigation: login ("Prisijungti") and a primary CTA
("Išbandyti nemokamai") must exist; the rest is yours.

## Creative mandate

- Choose a palette and typography with intent and be able to say why they
  belong to THIS product; do not default to the first "safe SaaS" scheme that
  comes to mind. Distinctive type pairing over ubiquitous defaults.
- Give the page **one signature moment** — a hero, interaction, or scroll
  sequence nobody has seen before, drawn from the product's own world:
  drawings, measurement, line-work, dimensions, the moment a plan becomes
  numbers. One extraordinary moment beats ten scattered effects.
- The construction-drawing world is your material library: plans, hatching,
  dimension lines, title blocks, stamps, grid paper, laser levels, folded
  sheets. Use it as a designer, not as literal clip-art.
- Structure must encode meaning: if you number sections, the numbering means
  something; if you use a grid, the grid comes from somewhere. No decoration
  that answers "why?" with "it looked nice."
- Both a light and a dark direction are acceptable — pick the one your concept
  demands, don't hedge with both.

**Blacklist — instant rejection:** warm-cream page with a serif display and
terracotta accent (that's the current site — this must be a NEW direction);
purple-blue gradient hero on white; near-black with one acid-green accent;
Inter/Roboto/Space Grotesk as the display face; emoji as section markers; three
identical rounded feature cards in a row; generic "AI brain / robot / sparkles"
imagery; invented dashboards that don't match the real product UI described
above; testimonial cards with stock-photo faces; centered-everything layouts
with no tension.

## Craft bar (non-negotiable)

- Fully responsive — the concept must survive a 390 px phone, not just look
  good at 1440 px. Wide elements scroll within themselves; the page never
  scrolls horizontally.
- Motion is welcome (scroll choreography, a living hero, micro-interactions)
  but must be CSS/SVG-cheap, purposeful, and fully degraded under
  `prefers-reduced-motion` (static composition must still be beautiful).
- Real hierarchy: a type scale, consistent spacing rhythm, deliberate alignment.
  Tabular numerals wherever numbers align — this is a product about numbers.
- Accessibility floor: readable contrast for all body text, visible focus
  states, alt text on meaningful imagery.
- The logo is an existing asset: the word "Pathon" plus a simple monogram-P
  mark. Treat it plainly and don't redesign it; recolor to fit your palette.
- Build it as one self-contained HTML/CSS/JS page (system-safe font fallbacks,
  no broken external dependencies) so our engineers can port it to React
  faithfully. Every section fully designed — no "and so on" placeholders.

## Deliverable

1. The one-sentence concept ("This page is a ___") plus a 5-line rationale:
   palette-why, type-why, signature-moment-why.
2. The complete landing page, every section designed, desktop and mobile.
3. A note on anything you intentionally left for the engineers (e.g. exact
   easing values), so nothing is lost in the port.

Surprise us. The safest version of this page already exists — we built it.
