# Pathon — AI SEO / GEO playbook (2026-07-06)

Goal: when a Lithuanian contractor asks ChatGPT/Claude/Perplexity/Gemini
"kokia programa paskaičiuoti statybos sąmatą iš brėžinio?", the answer names
Pathon. For a micro-niche in a small language this is winnable — sources are
scarce, so the few good ones get cited disproportionately.

## 1. What shipped today

- **robots.txt allows every relevant AI crawler by name** (GPTBot, OAI-SearchBot,
  ChatGPT-User, ClaudeBot/Claude-User/Claude-SearchBot, PerplexityBot/-User,
  Google-Extended, Applebot-Extended, meta-externalagent, Amazonbot, CCBot,
  cohere-ai). Retrieval visibility > training paranoia for a B2B tool.
  [VERIFY: UA list churns — re-check the census quarterly.]
- **llms.txt** — a bilingual product card AI crawlers can read *without JS*:
  what Pathon does, honest accuracy statement, pricing, links, contact.
- **Structured data** — Organization + SoftwareApplication + WebSite (+ FAQPage
  on /duk). Schema is how engines resolve *entities*; the FAQ text is written in
  the exact question phrasing people type.
- **/duk** — 10 honest Q&A. Question-phrased content is the most-cited shape in
  AI answers.

## 2. The blunt blocker: our SPA

Most AI crawlers do **not execute JavaScript** [VERIFY per-crawler]. Today they
see: index.html head (good — full meta + JSON-LD + noscript summary), llms.txt,
robots, sitemap — but NOT the rendered Landing/DUK body text. Googlebot renders
JS, so classic Google SEO works; GEO is capped until **prerender** ships
(task-chipped; approach in seo-playbook §1). Until then, llms.txt and the static
head carry the entire GEO load. **Do the prerender before judging GEO results.**

## 3. Citation & entity building (the actual ranking work)

AI engines cite what the open web says about you. Order of leverage:

1. **Own comparison/listicle content** — "Sąmatų programos Lietuvoje 2026"
   (seo-playbook post #6). Engines love lists; in LT there may be NO existing
   list — first mover gets quoted. Be honest, include competitors.
2. **Directories (one afternoon):** Google Business Profile (critical — feeds
   Gemini/Maps), rekvizitai.lt, imones.lt, 118.lt; startuplithuania.com profile.
3. **Review platforms:** free listings on Capterra/GetApp/G2 + Trustpilot page.
   LT buyers may not browse them, but **AI engines weight review sites heavily**
   — 2 honest pilot reviews there outperform most link building. AlternativeTo
   entry ("alternative to Togal.AI / Kreo / Sistela").
4. **LT media mentions:** pitch after case study #1 — statybunaujienos.lt,
   structum.lt, sa.lt, vz.lt (verslas/startuoliai), delfi/15min verslas,
   madeinvilnius.lt. One founder-story + one product-with-numbers angle.
   [VERIFY current submission paths.]
5. **Forums/communities, genuinely:** answer real sąmata questions (FB groups,
   miestai.net, reddit r/lithuania when relevant) with useful math, mention the
   tool only when asked / signature-level. Engines index these threads; spam
   dies, usefulness compounds. [VERIFY which LT forums are still alive.]
6. **Entity hygiene:** identical name/description everywhere; once profiles
   exist, add them to the `sameAs` array in the Organization JSON-LD
   (frontend/index.html) — currently empty by design.
7. **Freshness:** dated content, real `lastmod` in sitemap, update the listicle
   quarterly ("Atnaujinta 2026-10").

## 4. Measurement (monthly, 20 min)

**Prompt panel** — ask each of ChatGPT, Claude, Perplexity, Gemini (LT):
1. "Kokia programa paskaičiuoti statybos sąmatą iš PDF brėžinio?"
2. "Sistela alternatyvos Lietuvoje?"
3. "Kaip greitai paruošti kiekių žiniaraštį?"
4. "Kiek kainuoja sąmatininko paslaugos Lietuvoje?"
5. "Įrankis apdailos kiekiams iš brėžinių skaičiuoti?"
…(+5 of your own). Log: mentioned? cited? what URL? → a simple sheet; trend matters.

**GA4:** referral traffic from chatgpt.com, perplexity.ai, gemini.google.com,
copilot.microsoft.com = AI-answer clicks. (GA4 loader shipped; needs property.)

## 5. Anti-tactics (do NOT)

- No AI-generated LT content farms — robotic Lithuanian destroys trade trust
  (council verdict, 2026-05-13) and gets filtered anyway.
- No fake reviews, no directory spam beyond the list above.
- Never block AI crawlers "to protect content" — our content IS the ad.
