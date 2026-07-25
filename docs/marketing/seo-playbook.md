# Pathon — website SEO playbook (2026-07-06)

## 1. Technical — what shipped today (code, branch viewer-rebuild)

| Item | File | Status |
|---|---|---|
| robots.txt (app routes disallowed, AI crawlers explicitly allowed, sitemap ref) | `frontend/public/robots.txt` | ✅ |
| sitemap.xml (8 public URLs, hand-maintained — add every new page!) | `frontend/public/sitemap.xml` | ✅ |
| llms.txt (bilingual product card for AI crawlers) | `frontend/public/llms.txt` | ✅ |
| Canonical + OG + Twitter + theme-color + noscript fallback | `frontend/index.html` | ✅ |
| JSON-LD: Organization + WebSite + SoftwareApplication | `frontend/index.html` | ✅ |
| JSON-LD: FAQPage (10 Q&A, single source with visible content) | `frontend/src/pages/Duk.jsx` | ✅ |
| og-image.png 1200×630 (regen: `frontend/scripts/og-shot.mjs`) | `frontend/public/og-image.png` | ✅ |
| Per-route `<title>`/meta/canonical helper | `frontend/src/lib/seo.js` | ✅ |
| /duk FAQ page + footer link + route | `frontend/src/pages/Duk.jsx` | ✅ |
| GA4 consent-gated (Consent Mode v2; no-op until `VITE_GA4_ID`) | `frontend/src/lib/analytics.js` | ✅ |
| Prerender: `npm run build:seo` → 10 public routes into `dist/<route>/index.html` | `frontend/scripts/prerender.mjs` + `prerender-driver.mjs` | ✅ 07-07 |
| 4 BoFu pages (LT copy = DRAFT, founder polish pending) | `frontend/src/pages/bofu/` + `MarketingLayout.jsx` | ✅ 07-07 |
| Legal + /duk titles/meta from layout props | `frontend/src/components/legal/LegalLayout.jsx` | ✅ 07-07 |

### Pending (chipped / next build)
1. ~~Prerender public routes~~ ✅ 2026-07-07 — opt-in `npm run build:seo`
   (default `npm run build` untouched; Render keeps using it). PROD adoption
   still open: switch the host's build command to `build:seo`, add
   `npx -y playwright@1.55.1 install chromium` to the build image (untested on
   Render/Linux), and confirm the host serves `dist/<route>/index.html` for
   extension-less URLs BEFORE the SPA fallback (`vite preview` does NOT — use
   `python3 -m http.server -d dist` to spot-check locally).
2. **4 BoFu pages** ✅ built 2026-07-07 as drafts — /samatininko-kaina,
   /kiekiai-is-brezinio, /vidaus-apdailos-samata, /apva-renovacijos-kiekiai
   (in sitemap + prerender list). Founder polish before publishing (LT copy
   rule §5); price tables in /samatininko-kaina are marked orientacinės —
   sources still wanted. Still pending: **public /kainos** (today /pricing is
   behind the auth wall — a marketing bug; pricing must be visible logged-out
   once billing goes live).
3. `setPageMeta` on Login/Register (cosmetic); hreflang only if/when EN routes exist.
4. ~~Wire `setPageMeta` into LegalLayout~~ ✅ 2026-07-07 — legal pages + /duk
   derive `<title>`/description from their `title`/`intro` props.

## 2. Keyword map [VERIFY volumes via GSC + Keyword Planner after 2 wks of ads]

**Volumes (checked 2026-07-06):** no public non-interactive tool exposes LT
volume/CPC for these terms — Ahrefs/KeywordTool.io/Ubersuggest are gated or
paid, WordStream's free tool lacks Lithuania; only SE Ranking's free checker
includes LT (seranking.com/keyword-search-volume-checker.html). Cheapest real
numbers: **Google Keyword Planner, free with the Ads account we're creating
anyway** — pull LT ranges there before launch, then verify against GSC after
2 wks of ads.

### Live SERP check (google.lt, logged-out, Kaunas IP, 2026-07-06, via Playwright)

- **"sąmatų programa"** — contested but soft. Top 5 = legacy-vendor *homepages*
  (sistela.lt #1, astera.lt #2 — also the only ad bidder seen, ses.lt,
  dimetris.lt, prosama.lt); the only dedicated landing pages for the exact term
  sit at #8–9, incl. **buildiq.lt/samatu-programa-rangovams — a live AI-sąmatų
  competitor** ("sugeneruoja sąmatą iš tekstinio aprašymo") already doing
  landing-page SEO. A modern dedicated commercial page can realistically break
  top 5.
- **"kiekių žiniaraštis"** — **wide-open first-mover gap.** Entire top 10 =
  statyboszurnalas.lt help-desk articles + ministry/utility PDF/XLS templates
  (eso.lt, zum.lrv.lt, kaunas.lt). Zero commercial pages rank. Google triggered
  an **AI Overview** on this query → prime GEO citation target. Argues for
  building BoFu-2 first.
- **"sąmatininko paslaugos"** — directory sprawl (paslaugos.lt ×2, skelbiu.lt,
  skelbimai.lt, alio.lt); the only dedicated service site is a dated http://
  one-man page (samatininkas.lt, #4). No strong owner — clear opening for the
  BoFu-1 price-anchor page, but intent is partly hire-a-human/job-seeking, so
  expect intercept conversion, not exact-fit.
- pathon.eu appeared in none of the three top-10s (expected — site is new).
  Gap-size priority: kiekių žiniaraštis > sąmatininko paslaugos > sąmatų
  programa.
- Caveats: single logged-out session; no ads shown on kw 2–3 is not proof
  nobody bids; the Kaunas IP likely inflated one geo result (paslaugos.lt
  "Kaune" at #2).


| Keyword (LT) | Intent | Target page |
|---|---|---|
| sąmatų programa / sąmatos programa | buy | `/` + ads |
| statybos sąmata (pavyzdys, excel) | mixed | BoFu-2 + blog |
| kiekių žiniaraštis (excel, pavyzdys) | high | BoFu-2 |
| sąmatininko paslaugos / kaina | steal | BoFu-1 (price-anchor page) |
| vidaus apdailos sąmata | high | BoFu-3 |
| kiekiai iš brėžinių / kiekių skaičiavimas | exact-fit | BoFu-2 |
| APVA / renovacijos sąmata | segment | BoFu-4 |
| Sistela alternatyva | compare | comparison post (careful: checkbox tone) |
| kiek dažų reikia kambariui, glaisto sąnaudos, dažymo plotas | question/TOFU | calculators (§4) |

## 3. BoFu pages — build order + outline (800–1500 LT words each, one CTA: registruotis/demo)

1. **/samatininko-kaina** — "Sąmatininko paslaugos: kiek kainuoja 2026 ir kada
   apsimoka skaičiuoti pačiam". Sections: rinkos kainos €200–500 (šaltiniai),
   kada verta pirkti žmogų, kada įrankį; savikainos lentelė; honest "ko įrankis
   nepadaro". Schema: Article + FAQ. *This page sells by naming the price the
   buyer already pays.*
2. **/kiekiai-is-brezinio** — "Kiekiai iš PDF brėžinio per kelias minutes" —
   outcome page mirroring the hero; PDF→XLSX visual; step-by-step su ekrano
   nuotraukomis; confidence-flag honesty section.
3. **/vidaus-apdailos-samata** — trade page. Reuse CLAUDE.md §1 formulas as
   authority content (dažomas plotas, angokraščiai, glaistas pagal Q, GKP) —
   *no competitor has this depth in LT*. Schema: Article + HowTo.
4. **/apva-renovacijos-kiekiai** — "APVA renovacijos KŽ per dieną": reverse-VAT
   note, investicijų plano formatas, kiekių žiniaraščio pavyzdys.

## 4. Content calendar (8 posts max, weeks 5–12; topics locked only after demos)

Draft titles (replace with real demo objections as they come):
1. "Kiek iš tiesų kainuoja sąmata Lietuvoje 2026 (ir kodėl)"
2. "10 klaidų, kurias sąmatininkai daro skaičiuodami apdailą" (iš CLAUDE.md §8 — unikalus turinys)
3. "Kiekių žiniaraštis: pavyzdys + nemokamas šablonas" (lead magnet .xlsx)
4. "Kiek dažų reikia? Formulė, kurią naudoja profesionalai" (+ skaičiuoklė)
5. "Q1–Q4 glaistymo lygiai: ką jie reiškia jūsų sąmatai"
6. "Sąmatų programos Lietuvoje 2026 — sąrašas ir palyginimas" (listicle — AI engines cite lists; be honest, include Sistela)
7. "Atvirkštinis PVM statybose: kada ir kaip" 
8. Case study #1 su skaičiais (pilot customer)

**Calculator pages (high-leverage later):** interactive "dažų skaičiuoklė",
"glaisto skaičiuoklė", "GKP lapų skaičiuoklė" — the formulas already exist in
`universal_rules.py`; a thin public UI over them is a permanent link/citation
magnet and the most AI-quotable asset we can build.

## 5. Ops

- GSC: verify domain → submit sitemap → weekly query report (which real queries
  show impressions → feed keyword map).
- Every public page ships with: one `<h1>`, title ≤60 chars, description 140–160,
  internal links to/from at least 2 other pages, lastmod bump in sitemap.
- LT copy rule: Claude drafts → **founder polishes** → publish. Never skip.
