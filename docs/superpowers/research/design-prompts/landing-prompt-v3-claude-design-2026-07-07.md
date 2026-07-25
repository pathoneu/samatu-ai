# Pathon landing — Claude Design prompt v3 (2026-07-07, codebase-aware)

Paste everything below the line into claude.ai/design (repo connected — it reads
the codebase directly, no attachments needed; optionally attach the startup-
template screenshot you like as an extra visual reference).

---

Redesign the marketing landing page for **Pathon** — a Lithuanian B2B SaaS that
reads construction PDF drawings and produces verified quantity schedules
(sąmatos). Buyers: Lithuanian construction company owners and contractors —
practical, skeptical people who currently pay €200–500 per project for this
work. The current landing looks "AI-generated"; deliver a page that feels
engineered, like a precision instrument — closer to a survey tool than a
startup toy.

**Read these in the codebase FIRST (they are the source of truth):**
- `frontend/src/pages/Landing.jsx` — the current landing you are replacing
  (structure, copy quality, framer-motion usage). Improve on it, don't clone it.
- `frontend/src/components/layout/Logo.jsx` — the Pathon wordmark + monogram-P.
  **Keep this logo treatment exactly — it is founder-approved.**
- `frontend/src/index.css` + `frontend/tailwind.config.js` — current design
  tokens (graphite `#15181E` ground, orange `#F76B1C` accent, Sora / Hanken
  Grotesk / JetBrains Mono). This is the starting point for palette variant A.
- `frontend/src/i18n/lt.json` (`landing.*` keys) — the real Lithuanian copy.
  Reuse and sharpen it; do not write lorem or invent English placeholders.
- `frontend/src/pages/InteriorProject.jsx`, `frontend/src/components/project/AssumptionsPanel.jsx`,
  the PlanViewer components — the REAL product UI. The landing's product frames
  must faithfully mirror these screens (dark quantities table with confidence
  chips, Prielaidos panel with per-room heights and painted/bare toggles, the
  PDF viewer with colored room-zone overlays), not an invented dashboard.
- `frontend/src/pages/Duk.jsx` + `frontend/src/components/legal/LegalLayout.jsx` —
  the inner pages that must inherit your new design via a simple template.
- IGNORE the older cream/terracotta artifacts in the repo root
  (`landing-prompt-*-2026-05-12.md`, `rebuild-hero.jpeg`) — superseded, except
  the wordmark visible in them.
- PRIVACY: do not lift any real project names, addresses or prices from repo
  fixtures into the design — invent neutral demo data (rooms like "Svetainė
  18,4 m²", generic totals).

**Layout skeleton (reference: modern dark startup template):**
- Minimal top nav: Pathon wordmark left; center links Galimybės · Kaip veikia ·
  DUK · Kainos; right "Prisijungti" + primary button "Išbandyti nemokamai".
- Oversized centered 2-line hero headline, tight leading; one short muted
  subline; two side-by-side CTAs (primary filled + outline "Žiūrėti demo").
- Below the fold: a large product screen in a rounded, edge-lit frame, rising
  slightly on scroll.
- Generous negative space; restrained, product-led; subtle diagonal hairline
  motifs are welcome, decoration-for-its-own-sake is not.

**Hero background — the signature element (make this exceptional):**
A faint architectural floor plan being *scanned*, as if by a measuring
instrument. Behind the headline: barely-visible blueprint line-work of a floor
plan (thin strokes, ≤8–10% opacity). Every ~10s a slow scan beam sweeps across
it; where it passes, room polygons briefly fill with translucent accent color
and small monospaced labels fade in ("12.4 m²", "H = 2.70", "+1 vnt."),
dimension ticks draw themselves, a thin crosshair pauses on a door symbol with
a count chip. Metrology, not sci-fi — no Matrix rain, no glow-for-glow's-sake.
Pure CSS/SVG (no video), cheap transforms only, `prefers-reduced-motion`
fallback = static plan with zones pre-filled. The background must never compete
with the headline.

**Hero copy (Lithuanian, use exactly — do NOT put the word "AI" in the headline):**
- Headline: **"Užmeskite PDF brėžinį — kiekiai per kelias minutes."**
- Subline: "Tas pats sąmatos darbas, kurį dabar perkate už €200–500 už projektą.
  Kiekiai suskaičiuoti ir pažymėti patikrai — kainas suvedate patys."
- CTAs: "Išbandyti nemokamai" (primary — pirmas projektas įmonei nemokamas) ·
  "Žiūrėti demo".

**Scroll story (each section scroll-revealed, staggered, restrained):**
1. **Product frame** — the quantities view mirrored from `InteriorProject.jsx`,
   edge-lit, slight parallax.
2. **Kaip veikia — "Nuo PDF iki sąmatos — trys žingsniai":** 01 Įkelkite projekto
   PDF · 02 Peržiūrėkite pažymėtas vietas · 03 Eksportuokite sąmatą (Excel/PDF).
   Monospaced indices, thin dimension-line connectors.
3. **Ką perskaito:** grid — aukštų planai, sienų išklotinės, lubų planai, grindų
   planai, eksplikacijos, elektros/santechnikos planai → chips of extracted
   quantities: dažomas plotas, angokraščiai, GKP lapai, grindjuostės, plytelių
   zonos, LED nišos. Numbers always monospace with units (m², m³, vnt.).
4. **Pasitikėjimo sistema (our biggest differentiator — treat as a feature, not
   fine print):** the three confidence badges — žalia "nuskaityta iš brėžinio",
   geltona "apskaičiuota su prielaida", raudona "numatytoji reikšmė" — plus a
   "Tikrinti pirmiausia" worklist mock. Copy line:
   **"Nesakome „pasitikėk". Sakome „patikrink per 5 minutes"."**
5. **Gyvas perskaičiavimas:** edit a prielaida (lubų aukštis 2.70 → 3.20) and
   the quantities flip instantly — small animated number-morph demo, mirroring
   the real AssumptionsPanel.
6. **Eksportas:** two document mockups — Excel su gyvomis formulėmis ir
   LOKALINĖ SĄMATA PDF su 21% PVM eilute ir parašų bloku.
7. **Kam skirta:** 3 cards — Statybos įmonės savininkas ("pasiūlymas per vakarą,
   ne per savaitę") · Apdailos brigada ("kiekiai be sąmatininko") · NT
   vystytojas ("greita projekto patikra"). One pain line each, no fluff.
8. **Kainos teaser:** Nemokamas bandomasis (1 projektas) · €12 vienkartinis ·
   Pro €49/mėn · Studio €149/mėn — minimal cards, "be paslėptų mokesčių".
9. **Final CTA band** + compact footer (DUK, Privatumas, Slapukai, Sąlygos,
   solutions@pathon.eu) — keep the existing footer links/routes.

**Color — produce THREE complete palette variants of the SAME design** (show at
least the hero + one content section in each):
- **A · Instrument graphite (evolution):** refine the current tokens from
  `index.css` — near-black graphite, warm light ink, safety-orange accent.
- **B · Blueprint:** deep drafting navy/ink ground, paper-white line-work, one
  signal accent (cyan or engineer's yellow) — technical-drawing heritage.
- **C · Your call:** one direction you believe in (light "paper & ink studio"
  or dark bronze/amber — surprise me), still professional for construction B2B.
In every variant the three confidence colors (žalia/geltona/raudona) must stay
instantly distinguishable and consistent.

**Typography:** a characterful technical display face (NOT Inter/Roboto/Arial
as display; Sora is the incumbent — beat it or keep it deliberately) + clean
body + **monospace for every number, unit and price** — the brand signature.
Fonts MUST support Lithuanian diacritics (ąčęėįšųūž) — verify visually.

**Hard bans:** purple/blue gradient heroes; glassmorphism blobs; emoji as
icons; stock 3D/isometric illustrations; invented testimonials, client logos or
star ratings (we have none — do not fabricate proof); made-up stats like "99%
tikslumas" (the trust story is the verification workflow, not a fake number);
lorem ipsum; English placeholder copy; rounded-cards-everywhere sameness; the
word "AI" anywhere in the hero.

**Motion rules:** one orchestrated hero moment (the scan) + quiet scroll
reveals (fade/rise ≤24px, 150–250ms stagger); tactile but small hover states;
everything respects `prefers-reduced-motion`; no scroll-jacking.

**Implementation target:** React 18 + Vite + **JSX (no TypeScript)** + Tailwind;
framer-motion is available and already used in `Landing.jsx`. Componentized
sections that could drop into `frontend/src/pages/` conventions. Lithuanian
copy may be hardcoded in this design pass (the app's i18n wiring comes later).

**Deliverables:** desktop + mobile of the full landing in all 3 palettes, plus
a simple inner-page template (same nav/footer, article-style content column)
that `Duk.jsx` and the legal pages can inherit.
