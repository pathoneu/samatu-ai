# Landing page iteration handoff — 2026-05-11

Tęsiam rytoj. Šis failas — kur sustojom + ką pasiruošta paste'inti į claude.ai/design.

## Kur esam

**Pradinis prompt'as** (jau atnaujintas, paste'intas anksčiau, jau sugeneravo v1 svetainę):
`docs/superpowers/research/2026-05-11-samatu-design-prompt.md`

**Pakeitimai, jau įrašyti į prompt'o failą** (pasiekiama, jei generuosi iš naujo):
- §2 multi-type grid: tik **Vidaus apdaila** aktyvi, kiti 9 tile'ai gauna **NETRUKUS** pill + greyed state (opacity 0.65, `--ink-muted` tekstas)
- Ištrintas reikalavimas dėl "Palaiko brėžinių tipus" sekcijos (nekurti chip'ų ruožo su brėžinių tipais)

**Likę po-pirmojo-generavimo feedback'ai** (DAR neperkelti į prompt'o failą — gyvena kaip iteration žinutės, kurias paste'inam atskirai į claude.ai/design):

## Iteration prompt #1 — 4 turinio fix'ai

Paste'inti į claude.ai/design ant esamo generated page'o:

```
Padaryk 4 pataisymus:

1. „Vienas įrankis dešimčiai statybos darbų" grid
   Tik Vidaus apdaila lieka aktyvi (full color, mėlyna ikona, hover lift).
   Likusios 9 (Fasadai, Stogai, Mūro darbai, Betonavimas, Žemės darbai,
   Pastoliai, MEP, Kelių statyba, Griovimas) — disabled state:
   - Opacity 0.65, tekstas ir ikona --ink-muted, border --rule
   - Viršutiniame dešiniame kampe pill: „NETRUKUS"
     (font-size 11px, font-weight 600, letter-spacing 0.04em,
     padding 4px 10px, border-radius 999px,
     švelnus gintarinis bg ~14% opacity, tekstas --warning)
   - Be hover lift

2. Ištrink visą „Palaiko brėžinių tipus" sekciją
   Tas chip'ų ruožas po 10-tile grid'u (aukšto planas / pjūvis /
   fasadas / sienų išklotinė / lubų planas / eksplikacija) —
   ištrink visiškai. Per technikiška.

3. „Dar tobuliname" kortelės copy — perrašyti
   Pakeisk į ramų roadmap'ą be defensive framing'o:

   DAR TOBULINAME
   • Fasadai, stogai, MEP — ruošiame artimiausiai versijai
   • Daugiabučių modernizavimas — su APVA/BETA formatu
   • Excel/PDF eksportas pritaikytas F2/F3 formoms

   Visiškai pašalink:
   - „Tikslumas ne visada 100% — testuojam ant realių LT brėžinių"
   - „Fasadai, stogai, MEP — kuriame pagal vidaus apdailos pavyzdį"

4. Patikrink kad „JAU VEIKIA" kortelė ir 4 trust kortelės žemiau
   lieka nepakeistos.
```

## Iteration prompt #2 — motion + uniqueness (Kreo inspiration)

Po pirmojo iteration'o, paste'inam šitą, kad svetainė taptų mažiau generic, su daugiau animacijų:

```
Make this site less generic, more distinct. Keep the current copy
and structure. Keep the light palette (#f6f5f2 paper, #2a6fb5 blue,
warm ink). What we're changing is feel — more motion, more craft,
more "wait, this is different."

Research first, then design

Open and study kreo.net for ~5 minutes. Specifically look at:
1. How their hero drawing/blueprint animates (the AI marking up
   a drawing in real time)
2. How they transition between sections — scroll-driven, not just
   fade-in
3. Their micro-interactions on cards and numbers
4. How they make a B2B construction tool feel premium without
   going corporate-bland

Do NOT copy Kreo. Don't go dark. Don't use their teal/purple
gradients. Don't replicate their exact layouts. Their job is to
show you what "modern construction SaaS with personality" looks
like — yours is to do our own version in our warm light palette.

What to add (concrete moments, not vague "more animations")

1. Hero centerpiece — the magic moment.
   Replace whatever's in the hero right now with a scroll-anchored
   animation: a stylized LT construction drawing (room plan with
   langai/durys) renders, then AI cursors sweep across it, dropping
   markers on walls/openings, then quantity numbers fly out to a
   side panel (m², vnt., l). Loop subtly. ~8s cycle. This is THE
   hero — invest in it.
   Don't use a video file — build it with CSS keyframes + SVG
   strokeDasharray. Real animation, not embedded YouTube.

2. Scroll-driven section transitions. As the user scrolls between
   sections, let elements slide/scale/rotate in differently per
   section (not the same fade-up everywhere). Use IntersectionObserver
   thresholds at 0.2, 0.5, 0.8 for layered reveals.

3. Cursor-aware hero. Subtle parallax — background blueprint shifts
   6-10px following mouse, foreground stays put. Mobile: tilt-based
   via DeviceOrientation if granted, otherwise static.

4. Number counters that count. When the trust/metrics section enters
   viewport, numbers roll from 0 to target (eg. „90% greičiau",
   „21% PVM"). 800ms ease-out-expo.

5. One signature texture. Add a very faint paper grain SVG overlay
   across the whole page (4% opacity). Makes it feel handcrafted,
   not Figma-template.

6. Bold typographic moment. One section break (between hero and
   grid) gets an oversized statement — eg. „Brėžinys → kiekiai per
   60 sekundžių" — set in 100-120px display weight, with the arrow →
   animating left to right on scroll.

7. Drawing-types reveal. When „Vienas įrankis dešimčiai statybos
   darbų" grid enters viewport, the 10 tiles cascade in with a 50ms
   stagger AND each NETRUKUS pill bounces in 200ms after its tile.

What NOT to do
- No giant background gradient blurs
- No 3D isometric illustrations
- No video backgrounds
- No floating glassmorphic cards
- No emoji as decoration
- Don't darken the palette. Keep #f6f5f2 paper.

Constraints
- All animations must respect prefers-reduced-motion
- Mobile: drop parallax + cursor-tracking, keep counter + stagger
  + scroll reveals
- Total animation budget: page must hit interactive < 2.5s on a
  slow 4G profile
- Don't break: the NETRUKUS pills on 9 grid tiles, the deleted
  „palaiko brėžinių tipus" section, the rewritten „Dar tobuliname"
  copy. Those stay as-is.

Build it. Surprise me.
```

## Workflow rytoj

1. Atsidaryk claude.ai/design tą patį projektą su jau sugeneruota svetaine
2. Paste'ink iteration #1 — pasitikrink ar 4 fix'ai pritaikyti
3. Paste'ink iteration #2 — gauk motion-rich versiją
4. Jei dar kažkas neveiks ar atrodys kreivai — patalpink screenshot'us, iteruosim toliau
5. Kai svetainė bus OK — perkeliam į tikrą codebase'ą (frontend/src/, route per React Router) ARBA exportinam kaip static landing su atskira deploy URL'a (sprendžiam tada)

## Atviri klausimai dar nesvarstyti

- Ar landing'as gyvens su app'u tame pačiame domain'e (`samatu.ai/`) ar ant atskiro (`samatu.ai/about` redirect'as iš `/` jei neauth'intas)?
- CTA target'as — Calendly? Mailto? WhatsApp? Visi trys? (V2 prompt'e jau yra tel: link'as, bet WhatsApp dar nepridėtas)
- Payment wall'as kada — prieš ar po šito landing'o iteracijos?

## Bonus: ką dar verta pridėti iteracijoje #3 (jei #2 nepakanka)

- **Social proof, even if it's a single quote** — vienas rangovo citatos blokas su nuotrauka. Be jo bet kuris B2B SaaS site atrodo kaip vacuum'as.
- **Demo video / Loom** — 60-90s screen recording kaip pereini per realų PDF. Tai ką niekas nepamato animacijoje, mato realiame ekrane.
- **Pricing block** — net jei tik „Beta — nemokama", aiškumas dėl kainos = trust signal.
