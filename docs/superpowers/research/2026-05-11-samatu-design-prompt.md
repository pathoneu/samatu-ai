# Sąmatų AI landing page — claude.ai/design prompt (Chairman verdict, polished v2)

Generated via 3-round /consultcouncil + 5-advisor /llm-council with peer review, 2026-05-11.

Chairman's verdict incorporates the following peer-validated fixes from R2:
- **Math error fixed.** Original rows summed to 18,303 €, not 20,545 € (Contrarian's catch, verified by 3 reviewers). Numbers below are recomputed and internally consistent.
- **"RICS NRM2 + DIN" trust chip dropped.** Foreign acronyms mean nothing to a LT samatininkas (Outsider's catch). Replaced with concrete LT-only signals.
- **"MVP", "ankstyva prieiga" startup-jargon scrubbed** — replaced with rangoviška copy (Outsider).
- **`tel:` + WhatsApp added to CTA + footer** — LT B2B closes on phone (Reviewer 3, 4).
- **Mobile scroll-pin removed** — 300vh scroll-pin is hostile on mobile (Reviewer 3). Mobile gets scroll-triggered crossfade.
- **Framework declaration explicit**: React + Tailwind only, no framer-motion, native IntersectionObserver (Executor).
- **"Honesty band"** — landing names what's beta vs shipped, since real accuracy ≠ "per minutes" magic (Reviewer 5).
- **GDPR/data-handling note** for uploaded PDFs added (Reviewer 5).
- **Forbidden list expanded** with concrete LLM failure modes (aurora blobs, faux-localhost browser chrome, marquee logos, greyed "trusted by" bars, emoji bullets).
- **"LT STR §1" citation removed** — STR docs are numbered (1.04.04), no §1 (Reviewer 3).

---

```
<prompt>
Sukurk vieno puslapio responsive landing page produktui „Sąmatų AI" — Lietuvos statybos kainų skaičiavimo web aplikacijai. Naudok React + TypeScript viename `App.tsx` faile su inline Tailwind klasėmis. **JOKIŲ išorinių bibliotekų** (no framer-motion, no GSAP, no lottie-react, no react-spring). Animacijoms naudok native `IntersectionObserver` + `requestAnimationFrame` + CSS `transition`/`@keyframes`. JOKIŲ stock photo. Visa vartotojui matoma copy turi būti **lietuvių kalba**.

═══════════════════════════════════════════════════════════════════════
PRODUKTO ESMĖ
═══════════════════════════════════════════════════════════════════════

„Sąmatų AI" leidžia LT statybos rangovui ar samatininkui įkelti PDF brėžinius ir greitai gauti darbo sąmatos pagrindą EUR su 21% PVM. AI ištraukia kambarius, plotus, perimetrus, duris, langus iš brėžinio ir paverčia juos darbų pozicijomis pagal LT statybų praktiką.

NAUDOTOJAS: praktiškas statybos rangovas / samatininkas, vidutinio amžiaus, dirba objekte, dažnai žiūri telefone. NE tech buyer. Per 30 sekundžių turi suprasti tris dalykus: (1) ką tai daro, (2) kokią problemą sprendžia, (3) kaip su Sąmatų AI komanda susisiekti (telefonu, ne web forma — LT B2B realybė).

SCOPE: 10 statybos tipų (vidaus apdaila, fasadai, stogai, mūro darbai, betonavimas, žemės darbai, pastoliai, MEP, kelių statyba, griovimas) ir 6 brėžinių tipai (aukšto planas, pjūvis, fasadas, sienų išklotinė, lubų planas, eksplikacija). Dizainas privalo tai aiškiai parodyti — NE vidaus-apdailos-only įrankis.

STADIJA: produktas dar testuojamas. Nėra klientų, todėl JOKIŲ fake testimonial'ų, JOKIŲ „Trusted by 10,000+" eilučių. Naudok skaidrią „kviečiame rangovus į testavimą" komunikaciją.

═══════════════════════════════════════════════════════════════════════
PUSLAPIO STRUKTŪRA — 6 PAGRINDINĖS SEKCIJOS (+ NAV + FOOTER = 8 BLOKAI)
═══════════════════════════════════════════════════════════════════════

▸ NAV (sticky, subtle paper-blur)
   - Logo „Sąmatų AI" + sublabel „Statybų sąmatos iš brėžinių"
   - Anchors: „Kaip veikia" · „Darbų tipai" · „Tikslumas"
   - Šalia anchor'ų: telefono ikona + „+370 6XX XXXXX" (placeholder; click → `tel:` link)
   - Primary CTA: „Išbandyti su savo brėžiniu"
   - Mobile: logo + telefono ikona + CTA (jokio hamburger)

▸ 1. HERO — PDF → KIEKIAI → EUR TRANSFORMACIJA

   DESKTOP (≥1024px): scroll-driven 3-state morph viename viewport'e.
   Ne 300vh sticky pin (mobile-hostile). Vietoj: vienas viewport, scroll-progress 0-100% triggers 3 state'us per scroll-jacking-FREE IntersectionObserver thresholds [0.3, 0.6, 0.9]. Jei lankytojas neslenka, hero po 1.5s pats pereina state A → B → C vieną kartą (NE infinite loop, NE setInterval).

   MOBILE (<1024px): static fold, 3 maži skirtingi viewport'ai vienas po kito (scroll vertical). Jokio sticky. Jokio scroll-jacking. Tiesiog 3 fold'ai stacked.

   State A — PDF kortelė
     - Pavadinimas „Aukšto_planas.pdf" (faux file label)
     - Plonas mėlynas grid background + 3-4 kambariai kaip stačiakampiai
     - Subtle SVG matavimo linijos atsiranda per `stroke-dasharray`/`stroke-dashoffset` (600ms cubic-bezier(0.16, 1, 0.3, 1))
     - Status chip: „Analizuojama…" + 8px pulsing dot

   State B — Kiekiai išryškinami
     - Kambariai gauna mėlyną overlay (18% opacity, fade-in 320ms)
     - Floating chips šalia: „Svetainė 50.5 m²" „Miegamasis 23.9 m²" „Vonia 6.8 m²"
     - Plonas connector line PDF → kiekių lentelei dešinėj

   State C — EUR sąmata
     - Kiekių lentelė užsipildo (rows stagger 80ms apart)
     - EUR counter desinėj tick'ina 0 → galutinis skaičius per 800ms ease-out
     - Eksport chip: „Eksportuoti Excel/PDF"

   HERO COPY (kairėj desktop, virš vizualo mobile):
     H1 (56-64px desktop, 38-44px tablet, 30-36px mobile):
        „Iš PDF brėžinio —
        į sąmatos pagrindą."
     Subhead (17-19px desktop, 16px mobile):
        „Sąmatų AI ištraukia kambarius, plotus, perimetrus, angas iš tavo PDF ir paruošia LT rinkai pritaikytą sąmatos pagrindą su 21% PVM. Pataisai, ko reikia, ir eksportuoji."
     Primary CTA: „Išbandyti su savo brėžiniu"
     Secondary CTA (text link): „Pažiūrėti, kaip atrodo rezultatas ↓"
     Microcopy po CTA:
        „Brėžinys lieka tavo kompiuteryje — neperduodamas tretiesiems. Pirmas bandymas — be įsipareigojimų."
     Trust chips (3 pill'ai po headline — NEDAUGIAU):
        „PDF brėžiniai" · „EUR su 21% PVM" · „Pritaikyta LT statybų praktikai"

   ⚠ KRITIŠKAS: NE-darbai šitam hero:
   - JOKIO infinite scroll-pin loop
   - JOKIO setInterval/setTimeout-driven loop
   - JOKIO real DropZone (claude.ai/design negali įgyvendinti realaus PDF upload pipeline'o; tai static mockup, ne working tool)
   - JOKIO „per minutes" ar „per sekundes" promise — realus accuracy yra ~50% pagal vidinį testavimą; ribok kalbą iki „greitai paruošia pagrindą", NE „gauni sąmatą per minutes"

▸ 2. MULTI-TYPE GRID — „NE TIK APDAILA"

   Eyebrow (uppercase, 11px, --ink-muted, tracking 0.08em): „Ne tik vidaus apdaila"
   H2 (36-44px desktop, 28-32px mobile): „Vienas įrankis dešimčiai statybos darbų"
   Intro (17-18px): „Sąmatų AI supranta skirtingus brėžinius ir matavimo logiką — nuo kambario apdailos iki žemės darbų."

   LAYOUT: 5×2 grid desktop, 2×5 tablet, 1×10 mobile. JOKIO horizontal scroll — desktop'e nepastebimas, mobile'e gimmicky.

   🔴 SVARBU: TIK „Vidaus apdaila" tile yra AKTYVUS (full color, --ink tekstas, mėlyna ikona, hover lift). Kiti 9 tile'ai yra **NETRUKUS** state:
     - Tile background: --paper (truputį tamsesnė nei aktyvaus --paper-soft)
     - Tekstas: --ink-muted (vietoj --ink)
     - Ikona: --ink-muted (vietoj --accent)
     - Border: --rule (ne --accent-light)
     - Opacity: 0.7 (subtle, kad atsiskirtų be mirimo)
     - Viršutiniame dešiniame kampe pill chip:
       Tekstas: „NETRUKUS"
       BG: --warning su 14% opacity overlay (švelni gintarinė)
       Tekstas color: --warning
       Padding: 4px 10px; border-radius: 999px; font-size: 11px;
       Font-weight: 600; letter-spacing: 0.04em
     - JOKIO hover lift'o (nepromise'ina funkcionalumo, kurio dar nėra)
     - Tile'ai vis tiek paspaudžiami (NE `pointer-events: none`) — gali nuvesti į modal'ą ar email gavimo formą, bet tai vizualiai aiškiai pažymėta kaip "ateis vėliau"

   10 tile'ų:
     1. ✅ **Vidaus apdaila** (aktyvus) — „grindys, sienos, lubos, angokraščiai"
     2. 🟡 Fasadai — „ETICS plotai, angos, anchor'ai" — NETRUKUS
     3. 🟡 Stogai — „šlaitai, dangos, kraigai, latakai" — NETRUKUS
     4. 🟡 Mūro darbai — „blokai, plytos, sienų ilgiai" — NETRUKUS
     5. 🟡 Betonavimas — „pamatai, perdangos, tūriai" — NETRUKUS
     6. 🟡 Žemės darbai — „kasimas, užpylimas, planiravimas" — NETRUKUS
     7. 🟡 Pastoliai — „fasado plotai, aukščiai" — NETRUKUS
     8. 🟡 MEP — „elektra, santechnika, HVAC" — NETRUKUS
     9. 🟡 Kelių statyba — „sluoksniai, bortai, dangos" — NETRUKUS
     10. 🟡 Griovimas — „ardomi plotai, tūriai, išvežimas" — NETRUKUS

   STAGGER ENTRANCE: 60-90ms tarp tile'ų pasirodymo (cubic-bezier(0.16, 1, 0.3, 1)).

   🔴 NEKURTI atskiros „Palaiko brėžinių tipus" sekcijos su chip'ais (aukšto planas, pjūvis, fasadas, sienų išklotinė, lubų planas, eksplikacija). Tai TECHNINĖ detalė, ne marketing'inė; rangovas to nesupras / nepamatys vertės. Brėžinių tipų logika yra produkte, NE landing page'e.

▸ 3. HOW IT WORKS — 3 ŽINGSNIAI

   H2: „Kaip tai veikia"
   Visual: 3 dideli numeruoti žingsniai timeline'e (horizontal desktop, vertical mobile). Mėlynas thin progress line tarp žingsnių, scroll-triggered fill (3s ease).

   ① „Įkeli PDF brėžinius"
     „Aukšto planus, pjūvius, fasadus ar eksplikacijas. CAD'o nereikia."
   ② „AI ištraukia kiekius"
     „Sistema randa kambarius, plotus, perimetrus, duris, langus, aukščius."
   ③ „Pataisai ir eksportuoji"
     „Patikrini eilutes, pridedi savo įkainius, eksportuoji į Excel ar PDF su 21% PVM."

   Kiekvienas žingsnis turi mažą pseudo-UI vinjetę (NE generic icon — konkretus widget'as).

▸ 4. ESTIMATE PREVIEW — RANGOVIŠKAS PROOF

   H2: „Štai, ką gauni"
   Subcopy: „Kiekvieną eilutę pats patikrini, pataisai ar pridedi savo įkainius."

   Lentelė (desktop) / cards stack (mobile). Skaičiai PRIVALOMAI **IBM Plex Mono** font (engineering rigor signal). Tabular numerics, dešinė-aligned.

   Columns: „Darbas" · „Kiekis" · „Vnt." · „Kaina" · „Suma"

   Rows (skaičiai SUSKAIČIUOTI ir teisingi — nemainyti):
     ┌─────────────────────────────────┬────────┬─────┬──────┬──────────┐
     │ Sienų lyginimas Q2 (Rotband)    │ 138.7  │ m²  │ 11 € │ 1 526 €  │
     │ Sienų glaistymas-dažymas (2x)   │ 386.2  │ m²  │ 14 € │ 5 407 €  │
     │ Grindjuostės su montavimu       │ 93.8   │ m   │ 5 €  │   469 €  │
     │ Angokraščių apdaila             │ 94.0   │ m   │ 12 € │ 1 128 €  │
     │ Lubų glaistymas-dažymas         │ 148.6  │ m² │ 11 €  │ 1 635 €  │
     │ Grindų plytelės (klijavimas)    │ 28.4   │ m²  │ 24 € │   682 €  │
     │ Vidaus durų montavimas          │ 12     │ vnt │ 85 € │ 1 020 €  │
     └─────────────────────────────────┴────────┴─────┴──────┴──────────┘

   Summary (dešinėj desktop, apačioj mobile):
     Tarpinė suma:  11 867 €
     PVM 21%:        2 492 €
     ─────────────────────
     Viso su PVM:   14 359 €

   ⚠ Po lentelės: viena eilutė mažu šriftu, --ink-muted:
   „Įkainiai pavyzdiniai. Tu pats nustatai savo darbo įkainius — Sąmatų AI tik paruošia kiekius."

   ANIMATION: rows stagger fade-in 80ms apart kai sekcija pasiekia 60% viewport'o. Summary counters tick'ina (0 → 11867; 0 → 2492; 0 → 14359) per 800ms ease-out, simultaneously.

▸ 5. HONESTY BAND + TRUST (be fake testimonial'ų)

   H2: „Ką jau galima daryti, ką tobuliname"
   Subcopy: „Sąmatų AI dar testavimo stadijoje. Štai realus paveikslas."

   Dvi greta esančios kortelės (desktop) / stacked (mobile):

   KORTELĖ A — žalio kraštinio kontūro, „Jau veikia" header:
     - „Vidaus apdailos kiekiai iš PDF"
     - „Patalpų eksplikacijos atpažinimas"
     - „LT samatininkų konvencijos (sienų lyginimas, angokraščiai, grindjuostės)"
     - „21% PVM ir EUR formatas"
     - „Eksportas į Excel ir PDF"

   KORTELĖ B — gintarinė (--warning) kraštinė, „Dar tobuliname" header:
     - „Tikslumas ne visada 100% — testuojam ant realių LT brėžinių"
     - „Fasadai, stogai, MEP — kuriame pagal vidaus apdailos pavyzdį"
     - „Visi kiekiai pereina per žmogaus akį prieš eksportą"

   Po šitos sekcijos — 4 kortelių trust grid (2×2 desktop, 1×4 mobile), be fake testimonial'ų:
     ① „LT rinkos konvencijos" — „EUR, 21% PVM, įprasta darbų struktūra LT statybose."
     ② „Matavimo logika" — „Remiamasi LT samatininkų praktika ir tarptautiniais matavimo principais."
     ③ „Patikrina žmogus" — „AI paruošia kiekius, tu patvirtini kiekvieną eilutę prieš sąmatos pateikimą."
     ④ „Privatumas" — „Brėžinys analizei naudojamas tik tavo užklausos metu. Nesidaliname su trečiosiomis šalimis."

▸ 6. FINAL CTA — KONTAKTAS PER TELEFONĄ + WAITLIST

   H2: „Norite išbandyti su savo brėžiniu?"
   Subcopy: „Susisiekite, pasidalinkim Sąmatų AI prieiga ir aptarkim, kaip pritaikyti jūsų darbams."

   DU lygiagretūs CTA blokai (side-by-side desktop, stacked mobile):

   BLOKAS A — Skambinti (primary, --accent BG):
     Didelis telefono ikonos + tekstas:
        „Skambinkim"
        „+370 6XX XXXXX"
     (Click → `tel:+3706XXXXXXX` link)
     Microcopy: „Atsiliepiame darbo dienomis 9-18"

   BLOKAS B — WhatsApp/El. paštas (secondary, --paper-soft BG):
     WhatsApp ikona + tekstas:
        „Rašykim"
        „WhatsApp arba el. paštu"
     Buttons stacked:
        - „WhatsApp" → `https://wa.me/3706XXXXXXX`
        - „El. paštas" → `mailto:info@samatu-ai.lt`

   Po blokais — mini-form (waitlist'ui, ne kaip pagrindinis CTA):
     - Input: „El. paštas" (placeholder)
     - Input: „Įmonė ar vardas" (optional)
     - Mažas button: „Pridėti į sąrašą"
     - Microcopy: „Naujienos apie naujus statybos tipus. Be spam."

▸ FOOTER
   Logo + tagline „Statybų sąmatos iš PDF brėžinių."
   Trys stulpeliai (desktop, stacked mobile):
     Stulpelis 1 — Kontaktai: telefonas (`tel:` link), WhatsApp (`wa.me`), email (`mailto:`).
     Stulpelis 2 — Anchors: Kaip veikia · Darbų tipai · Tikslumas.
     Stulpelis 3 — „Privatumas ir duomenys" link (placeholder anchor).
   Mini legal: „© 2026 Sąmatų AI. Produktas dar testavimo stadijoje."

═══════════════════════════════════════════════════════════════════════
BRAND TOKENS (CSS custom properties — privaloma naudoti)
═══════════════════════════════════════════════════════════════════════

--paper:        #f6f5f2     /* pagrindinis background */
--paper-soft:   #fafaf8     /* kortelių background */
--card:         #fffdf8     /* svarbesnių kortelių background */
--ink:          #1f2937     /* pagrindinis tekstas */
--ink-soft:     #4b5563     /* antrinis tekstas */
--ink-muted:    #687385     /* microcopy, captions */
--rule:         #e5e1d8     /* borders */
--accent:       #2a6fb5     /* brand blue */
--accent-hover: #1e5a99
--accent-light: #dceaf7     /* hero overlays */
--success:      #16a34a     /* „Jau veikia" kortelės kraštinė */
--warning:      #d97706     /* „Dar tobuliname" kraštinė */
--shadow:       rgba(31,41,55,0.08)

Hero gradient blob:
  linear-gradient(220deg, #f6f5f2 0%, #dceaf7 45%, rgba(42,111,181,0.45) 100%)
  Subtle 18s rotate + scale transform loop.
  `prefers-reduced-motion: reduce` → freeze (no animation).

═══════════════════════════════════════════════════════════════════════
TYPOGRAPHY
═══════════════════════════════════════════════════════════════════════

UI sans-serif: **Inter**
Numbers/data only: **IBM Plex Mono** (engineering rigor signal — tik skaičiams, EUR, m², m, vnt.)

Pakraunamas šitaip (NE @import — render-blocking 4G):
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" onload="this.onload=null;this.rel='stylesheet'" />
```

Tu skydeli/heading sizes:
H1: 56-64px desktop, 38-44px tablet, 30-36px mobile (line-height 1.05, tracking -0.02em, weight 700)
H2: 36-44px desktop, 28-32px mobile (line-height 1.1, tracking -0.015em, weight 700)
H3: 22-24px (weight 600)
Body: 17-19px desktop, 16px mobile (line-height 1.55-1.65)
Mono: 14-16px (weight 500), tabular-nums

═══════════════════════════════════════════════════════════════════════
SPACING + LAYOUT
═══════════════════════════════════════════════════════════════════════

Section padding: 96-120px desktop top/bottom, 56-72px mobile
Container max-width: 1180-1240px
Border radius: 18-24px kortelėms, 999px pill chip'ams
Box shadow: 0 4px 14px rgba(31,41,55,0.06)

═══════════════════════════════════════════════════════════════════════
ANIMATIONS — NATIVE TIK
═══════════════════════════════════════════════════════════════════════

JOKIŲ bibliotekų: framer-motion, GSAP, lottie ir t.t. — JOKIŲ.
Tik native CSS + IntersectionObserver + requestAnimationFrame.

Easing:
- Entrance:  cubic-bezier(0.16, 1, 0.3, 1)
- Exit:      cubic-bezier(0.7, 0, 0.84, 0)

Durations:
- micro (hover, chip): 100-180ms
- card entrance: 320-480ms
- hero state morph: 600-900ms
- counter tick: 800ms ease-out
- gradient blob: 12-18s loop

Scroll-triggered (IntersectionObserver, rootMargin "-15%"):
- Sekcijos fade-in + 24px y-offset
- Kortelės stagger entrance (60-90ms tarp kortelių)
- Counters animuojasi kai sekcija pasiekia 60% viewport
- SVG measurement lines draw via stroke-dashoffset

Hover (desktop only via @media (hover: hover)):
- Card lift 4px translateY
- Border shift į --accent
- Icon scale 1.04 arba rotate 6°
- Mobile: NE hover; tap states only

prefers-reduced-motion: reduce
- Disable gradient blob loop
- Replace state morphs with cross-fade only (no transforms)
- Counters appear at final value
- Hero stays static at State C

═══════════════════════════════════════════════════════════════════════
MOBILE RESPONSIVE
═══════════════════════════════════════════════════════════════════════

Breakpoints: Mobile <640, Tablet 640-1024, Desktop >1024

Mobile rules:
- Hero: 3 fold'ai stacked vertically (NE 300vh scroll-pin — destroys scroll momentum)
- Multi-type grid: 1×10 stacked (NE horizontal scroll)
- Estimate table: vertical cards stack with sticky summary bar bottom
- Animation amplitude reduced (smaller transforms, shorter durations)
- Nav: logo + telefono ikona + CTA (jokio hamburger)
- All numbers IBM Plex Mono stays — readable
- Min tap target 44×44px (iOS HIG)

═══════════════════════════════════════════════════════════════════════
KO ABSOLIUČIAI NEDARYTI
═══════════════════════════════════════════════════════════════════════

❌ Dark theme (paletė yra light)
❌ Fake testimonials su išgalvotais vardais ar logo „Trusted by X+"
❌ Greyed-out client logo bar („as seen in" / „naudoja")
❌ Marquee/auto-scrolling logo strips
❌ Faux-localhost browser chrome `localhost:3000` screenshot mockup
❌ Aurora/gradient mesh blobs (overplayed; subtle linear gradient OK)
❌ Glassmorphism (frosted glass overlays)
❌ Lottie animations, decorative bouncing
❌ Generic stock photos (orange-helmet contractors, blueprints)
❌ Emoji bullets in feature lists
❌ 3D abstract cubes ar generic AI illustrations
❌ Anglų kalbos pagrindinė copy (UI must be LT)
❌ Generic SaaS „Fast / Accurate / Easy" 3-card grid
❌ Cyberpunk gradients / neon
❌ Parallax background images
❌ Auto-playing setInterval loops kaip pagrindinė hero animacija
❌ Horizontal scroll multi-type (undiscoverable desktop)
❌ Sticky 300vh scroll-pin sekcijos mobile'e
❌ Bibliotekos: framer-motion, GSAP, lottie-react, react-spring
❌ `@import` Google Fonts (render-blocking) — naudoti preload pattern
❌ Šalia „Sertifikuota" lygmens žodžiai — naudok „pritaikyta", „remiasi"
❌ MVP, „ankstyva prieiga", „beta", „startup" startup'inė terminologija — rangovas to nesupranta
❌ Promise „per minutes" / „per sekundes" — real accuracy ~50% pagal vidinį testavimą; ribok kalbą
❌ Web-form-only kontaktas be telefono — LT B2B realybė reikalauja telefoninio kontakto
❌ External fetch'ai į DOM (CORS issues + sandbox restrictions)

═══════════════════════════════════════════════════════════════════════
KOKYBĖS BARAS
═══════════════════════════════════════════════════════════════════════

Po 30 sekundžių rangovas privalo suprasti:
1. Ką tai daro: PDF → kiekiai → sąmatos pagrindas EUR.
2. Kad palaikomi 10 statybos tipų, ne tik apdaila.
3. Kaip susisiekti (telefonas matomas iškart).

Po 90 sekundžių jis privalo suprasti:
4. Kad produktas dar testuojamas, NE pilnas marketingo melas.
5. Kad žmogus tvirtina kiekvieną eilutę — AI ne juodoji dėžė.
6. Kad jo brėžinys lieka privatus.

Sukurk pilną landing page'ą su 6 sekcijomis + nav + footer, copy lietuviškai, native animacijas (no framer-motion), light theme paletei, IBM Plex Mono skaičiams, scroll-triggered transitions, `tel:` + WhatsApp links, ir griežtą forbidden list compliance. Generuok production-quality kodą vienu shot'u.
</prompt>
```

---

## Council scoreboard (R2 peer review)

| Reviewer | Strongest | Blind spot | What ALL missed |
|----------|-----------|------------|------------------|
| 1 | **C** (math verified 18,303) | B (rendering frame ignores wrong math) | Funnel scope mismatch — claude.ai/design is mockup tool, not product |
| 2 | **C** (math + section count) | E (DropZone impossible in static artifact) | Codebase reality: Pipeline 1 = 49% accuracy; "per minutes" promises more than ships |
| 3 | **C** | E (scope explosion) | Mobile-first contradiction (300vh scroll-pin hostile); no `tel:`/WhatsApp; "LT STR §1" fabricated citation |
| 4 | **C** | E (live DB on pre-revenue page) | No `tel:`/WhatsApp; Google Fonts @import render-blocking 4G; legal risk in NRM2/STR chip |
| 5 | **C** | D (try-it page impossible in static) | No "kas veikia / kas ruošiama" honesty band; no GDPR/data-handling note; "per minutes" promise vs real accuracy |

**Unanimous: C strongest** (Contrarian caught verifiable math error).
**4/5: E biggest blind spot** (scope explosion vs static artifact).

**Major changes in v2 prompt:**
1. Numbers RECOMPUTED and consistent (11,867 → 14,359 €).
2. "RICS NRM2 + DIN" dropped, no false citation.
3. "MVP", "ankstyva prieiga", "per minutes" — scrubbed.
4. `tel:` + WhatsApp + email in CTA + footer.
5. Scroll-pin removed on mobile; native IntersectionObserver only.
6. Framework declaration explicit (no framer-motion).
7. Honesty band added ("Jau veikia / Dar tobuliname").
8. GDPR / data-handling note in privacy trust card + microcopy.
9. Forbidden list expanded with concrete LLM failure patterns.
10. Font loading via preload (no @import).

Prompt'as išsaugotas `docs/superpowers/research/2026-05-11-samatu-design-prompt.md`. Paste ready.