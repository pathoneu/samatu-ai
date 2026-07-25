# Pathon landing — Google Stitch prompt v5 (2026-07-11, pure-beauty cut)

How to use: open labs.google.com/stitch → new Web project → paste EVERYTHING
below the line as the prompt (it is a DESIGN.md-style system + a generation
brief; Stitch reads the whole thing). If Stitch trims long prompts, paste the
Design System first, then the Generation Brief as the follow-up message.
Iterate section by section afterwards — never accept a generic first pass.

---

# Design System: Pathon — "The Checked Drawing"

## 0. Concept (read first — every choice serves this)

This landing page IS an architectural drawing sheet that has been through a
checker's hands. The entire page behaves like one oversized, beautifully
composed A1 sheet of drafting film: hairline construction grid, dimension
lines that measure the page's own elements, a checker's red pencil that has
circled what matters, and a full title block (kampinis spaudas) as the footer.
Not "blueprint themed" — no navy cyanotype cliché. This is pale drafting film,
graphite ink, and one red pencil. The drama comes from precision: the page
measures itself, annotates itself, checks itself — because the product
(Pathon) reads construction drawings and turns them into checked quantities.
It should feel like a drawing a master draftsman composed for the sheer
pleasure of it. If a section could exist on any SaaS site, it is wrong.

## 1. Visual Theme & Atmosphere

Gallery-airy density (3/10) with confidently asymmetric, offset composition
(variance 8/10) and fluid, instrument-like motion (6/10). The mood: the quiet
of a drafting studio at night — one sheet on the table, one red pencil beside
it. Vast negative space, hairline structure everywhere, ink that sits ON the
surface rather than floating over it. Flat and matte; depth comes from line
weight and spacing, never from glows or heavy shadows.

## 2. Color Palette & Roles

- **Drafting Film** (#F4F4F1) — page ground; cool paper-white, matte
- **Mylar** (#FBFBFA) — raised surfaces, sticky nav, pricing panels
- **Graphite Ink** (#1C1D1B) — display type, primary text, drawn linework
- **Pencil Gray** (#6E7069) — secondary text, annotations, metadata
- **Setsquare Hairline** (rgba(28,29,27,0.14)) — 1px construction grid,
  dimension lines, dividers; the page's skeleton is drawn, not implied
- **Checker's Red** (#B4342C) — THE single accent. Used exactly like a
  checker's red pencil: circling one number, underlining one claim, the
  primary CTA fill, dimension-line arrowheads, the stamp. If red appears in
  more than ~5 places per viewport, it stops being a pencil and becomes paint —
  restrain it.
- Semantic trio (**#2E7D4F** green / **#B07A18** amber / **#B4342C** red)
  appears ONLY inside product depictions as the confidence dots on quantity
  rows — never as page UI decoration.

No other hues. No gradients on type. Never pure black (#000000).

## 3. Typography Rules

- **Display: Cabinet Grotesk** (fallback: Outfit) — track-tight (-0.03em),
  weight-driven hierarchy (500/700), scale via clamp(2.6rem, 6vw, 5.2rem).
  Headlines read like drawing titles: confident, engineered, never screaming.
- **Body: Satoshi** — 1rem–1.0625rem, relaxed 1.65 leading, 65ch max, Pencil
  Gray for secondary passages.
- **Mono: JetBrains Mono** — ALL numbers on the page (quantities, prices,
  section indices, dimension values) are mono with tabular figures; this is a
  product about numbers and the mono is its voice. Also: annotation labels,
  the title-block fields, uppercase micro-labels at 11px/0.14em tracking.
- Banned: Inter, Roboto, system-ui as display, all generic serifs. No serif
  anywhere on this page.

## 4. The Hero (signature section — spend the effort here)

- Asymmetric split, NOT centered: headline block set left on the sheet with
  deliberate off-grid offset; the right/lower zone holds a large, faithful
  product frame (see §6) placed like a drawing detail pasted onto the sheet.
- **Inline image typography:** inside the 2-line Lithuanian headline, embed
  one small rounded crop of a floor-plan drawing at type height between words
  — a real visual punctuation mark, e.g. "Iš brėžinio [plan-crop] — į sąmatą."
  On mobile the crop drops below the headline.
- **The page measures itself:** thin dimension lines with arrowheads and mono
  labels annotate the hero — one measuring the headline's width, one dropping
  from the headline to the CTA, labeled with REAL product values ("41 min → 3
  eil. patikrai", "165,64 m²"). They draw themselves in on load (line grows,
  then label fades), like a draftsman pulling dimensions.
- **One checker's mark:** a slightly imperfect red ellipse draws itself around
  the single most important number in the hero stat line — the way a checker
  circles the figure that matters.
- Exactly ONE CTA: solid Checker's Red button "Išbandyti nemokamai", tactile
  1px press. No secondary "learn more". No scroll cues, no chevrons.
- Nav: "Pathon" wordmark + monogram-P left (existing asset — recolor to
  Graphite Ink, do not redesign); right side only "Prisijungti" text link and
  the red CTA. Hairline bottom border, Mylar backdrop blur when sticky.

## 5. Layout Principles

- A visible 12-column hairline construction grid lives faintly behind the
  page (Setsquare Hairline, barely-there); content locks to it like a drawing.
  Max-width 1400px, generous asymmetric margins.
- Sections are numbered like drawing sheets in mono micro-labels: "LAPAS 01 —
  KAIP VEIKIA", "LAPAS 02 — PATIKROS SISTEMA"… numbering IS the navigation
  logic.
- Zig-zag two-column rhythm with intentional imbalance (7/5, 8/4 splits);
  the "3 equal cards in a row" pattern is banned. Where a list is needed, use
  hairline border-top dividers, not card boxes.
- The footer IS a full drawing title block: a hairline-ruled table with mono
  fields — PROJEKTAS: Pathon / LAPAS: 07-07 / DATA / LAIDA: A / TIKRINO: Jūs —
  where the fields double as the sitemap links (DUK, Privatumas, Sąlygos,
  Kainos) and contact. A small red "PIRMAS PROJEKTAS — NEMOKAMAS" stamp,
  rotated ~-4°, sits beside it (decorative; the real CTA is a button above).
- min-h-[100dvh] for full-height moments, never h-screen. No element overlap
  anywhere — every annotation owns clean space.

## 6. Product truth (depict THIS, invent nothing)

Pathon (Lithuanian B2B SaaS): upload a construction project PDF → it reads the
drawings (floor plans, wall developments, ceiling plans), identifies rooms,
computes quantities with Lithuanian estimator formulas → a bill of quantities
+ estimate; user reviews flagged lines, enters own prices, exports Excel with
live formulas or a Lithuanian-format PDF. True numbers only: reading takes
~10–15 min (vs hours-to-days by hand); "patikrinti 3 eilutes iš 46" review
triage; pricing €12 vienkartinis / €49 Pro (10 proj.) / €149 Studio (35 proj.),
be PVM, first project free. Product frames must show the REAL UI: a PDF plan
with translucent colored room zones + a quantities table whose every row
carries a confidence dot (🟢 read from drawing / 🟡 assumption / 🔴 default —
rendered as dots, not emoji). Demo data is invented-neutral: "101 Svetainė
18,4 m²", "Vonia 5,2 m²". No real client names, addresses, totals. No fake
testimonials, no invented accuracy percentages, no user counts.

Copy: write fresh, natural Lithuanian throughout (draft quality fine — the
founder polishes; zero lorem, zero English placeholders). Laws: the value is
TIME (the user does takeoffs themselves; never imply they pay someone else);
Pathon is the tool, not an add-on to any other tool; never promise perfection —
the checking system is the honesty ("patikrink per minutes", not "pasitikėk
aklai"). Voice: precise colleague, numbers over adjectives, zero hype words.

Page content, in this sheet order: hero → kaip veikia (upload→skaitymas→
patikra→kainos, drawn as a dimensioned process line, not steps-in-cards) →
patikros sistema (the confidence-dot story around a product frame; the "3 iš
46" number gets the red circle treatment) → gyvas perskaičiavimas (change one
assumption, lines update) → eksportai (Excel/PDF, one quiet row) → kainos
(four tiers as a hairline-ruled price table — a table, like a drawing
schedule, NOT four cards) → final CTA → title-block footer.

## 7. Motion & Interaction

- Spring physics everywhere (stiffness 100, damping 20); zero linear easing.
- Staggered cascade reveals per section — elements arrive like a drawing being
  plotted: hairlines first, then ink, then annotations, then the red pencil.
- Perpetual micro-loops, subtle: dimension arrowheads breathe (2% scale), the
  hero red ellipse redraws every ~14s, a slow 8s shimmer crosses the product
  frame like light over drafting film. Nothing bounces, nothing spins.
- transform/opacity only; animations pause under prefers-reduced-motion with
  the fully-drawn static sheet as the fallback (it must be beautiful frozen).
- Buttons: -1px translate press; inputs (if any) label-above, red focus ring.
- Loading: skeletal shimmer matching layout, never spinners.

## 8. Responsive Rules

Single column below 768px, no exceptions, no horizontal scroll ever. Headline
clamp() scaling; inline plan-crop drops below the headline; dimension-line
annotations hide below 640px except one hero dimension; the title-block footer
re-stacks its fields vertically but keeps its ruled-table character. Touch
targets ≥44px. Section gaps clamp(3rem, 8vw, 6rem).

## 9. Anti-Patterns (NEVER)

No emojis. No Inter. No serifs. No pure black. No neon or outer glows. No
gradient text. No purple anything. No navy "blueprint" cyanotype look. No
warm-cream + terracotta (that is the CURRENT site — this must be a different
world). No centered hero. No 3-equal-cards rows. No card-boxes where a ruled
table or divider works. No overlapping text/images. No "Scroll to explore",
chevrons, or scroll cues. No AI copy clichés (jokių "atraskite", "pakelkite į
kitą lygį", "revoliucija", "seamless"). No fake round numbers, no "John Doe"/
"Acme", no testimonials. No stock photos of builders in hard hats pointing at
tablets. No robots, brains, sparkles.

---

# Generation Brief (the ask)

Generate the full desktop web landing page for Pathon exactly per the design
system above — every section from hero to title-block footer, fully composed,
real Lithuanian copy, invented-neutral demo data in the product frames. Then
generate the mobile version of the same page. Follow the sheet metaphor with
total commitment: construction grid, dimension annotations, numbered LAPAS
sections, red pencil restraint, title-block footer. The safest version of this
page already exists — we built it. Make the one only you would dare to.
