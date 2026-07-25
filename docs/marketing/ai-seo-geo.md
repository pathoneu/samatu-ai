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
  **Census verified 2026-07-06 against official vendor docs** (list churns —
  re-check ~2026-10):
  – All tokens current except `cohere-ai`, which was never officially
    documented by Cohere (unconfirmed per darkvisitors.com/agents/cohere-ai;
    kept, harmless).
  – What gates what — TRAINING: GPTBot (developers.openai.com/api/docs/bots),
    ClaudeBot (support.claude.com article 8896518, 2026-04-07),
    meta-externalagent, CCBot, Amazonbot (mixed), Applebot-Extended (a token,
    not a crawler — plain **Applebot**, allowed via our `User-agent: *`,
    carries Siri/Apple-Intelligence visibility). RETRIEVAL: OAI-SearchBot
    (blocking it removes you from ChatGPT search answers), Claude-SearchBot,
    PerplexityBot (docs.perplexity.ai/guides/bots — explicitly not training).
    USER-FETCH: ChatGPT-User, Claude-User, Perplexity-User (these may ignore
    robots.txt anyway; explicit Allow just removes ambiguity).
  – Google-Extended nuance: it gates Gemini-app grounding + future model
    training only; **AI Overviews / AI Mode use regular Googlebot**, and it is
    not a ranking signal (developers.google.com/search/docs/crawling-indexing/google-common-crawlers,
    updated 2026-04-23).
  – Copilot has no dedicated AI UA — it rides the ordinary Bingbot index
    (bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0); covered
    by our `User-agent: *`.
  – **Added 2026-07-06** (officially documented, retrieval/user-fetch
    relevant): meta-externalfetcher + meta-webindexer (Meta AI answers —
    developers.facebook.com/docs/sharing/webmasters/web-crawlers),
    MistralAI-User + MistralAI-Index (docs.mistral.ai/robots), DuckAssistBot
    (duckduckgo.com/duckduckgo-help-pages/results/duckassistbot/),
    Amzn-SearchBot + Amzn-User (developer.amazon.com/amazonbot — both
    explicitly exclude genAI training; spellings re-verified first-hand).
  – **Deliberately NOT added:** xAI/Grok (no official crawler doc; observed
    Grok retrieval traffic spoofs browser UAs, so a robots entry can't target
    it) and Bytespider (training-only, documented robots.txt ignorer).
- **llms.txt** — a bilingual product card: what Pathon does, honest accuracy
  statement, pricing, links, contact. **Adoption reality (verified 2026-07-06):
  no major answer engine consumes llms.txt.** Google calls it "purely
  speculative — none of the AI systems use it" (John Mueller, 2026-06-02,
  https://www.searchenginejournal.com/google-says-llms-txt-is-purely-speculative-for-now/577576/);
  Ahrefs' 137K-domain log study found 97% of published llms.txt files receive
  zero requests, and the top fetchers are coding agents (Claude Code, Cursor),
  not search crawlers (2026-06-15, https://ahrefs.com/blog/llmstxt-study/).
  No OpenAI/Anthropic/Perplexity/Microsoft consumption commitment exists
  (Perplexity's crawler docs cover robots.txt only,
  https://docs.perplexity.ai/docs/resources/perplexity-crawlers). Keep the file
  — zero cost, small lottery-ticket upside — but it is NOT a GEO channel;
  prerendered HTML is what engines actually read.
- **Structured data** — Organization + SoftwareApplication + WebSite (+ FAQPage
  on /duk). Schema is how engines resolve *entities*; the FAQ text is written in
  the exact question phrasing people type.
- **/duk** — 10 honest Q&A. Question-phrased content is the most-cited shape in
  AI answers.

## 2. The blunt blocker: our SPA

Most AI crawlers do **not execute JavaScript** — verified per-crawler
2026-07-06: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, PerplexityBot and
meta-externalagent all fetch .js files but never execute them (Vercel's
500M-fetch study, 2024-12-17, vercel.com/blog/the-rise-of-the-ai-crawler;
reaffirmed as of June 2026 by getpassionfruit.com/blog/javascript-rendering-and-ai-crawlers-can-llms-read-your-spa).
Today they see: index.html head (good — full meta + JSON-LD + noscript
summary), llms.txt, robots, sitemap — but NOT the rendered Landing/DUK body
text. The two exceptions render like browsers: **Googlebot** (evergreen
Chromium — developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics,
updated 2026-03-04 — so classic Google SEO *and* AI Overviews/Gemini grounding
see rendered content) and **Applebot** (support.apple.com/en-us/119829). GEO
on every other engine is capped until **prerender** ships
(task-chipped; approach in seo-playbook §1). Until then, the static head
(meta + JSON-LD + noscript summary) carries the entire GEO load — llms.txt
does not (engines don't fetch it; see §1). **Do the prerender before judging
GEO results.**

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
   **Submission paths (all 8 verified alive, contacts checked 2026-07-06):**
   – statybunaujienos.lt (published same-day 2026-07-06): vyr. redaktorė Genė
     Drungilienė, gene.drungiliene@statybunaujienos.lt, +370 640 20 132
     (statybunaujienos.lt kontaktai page).
   – 15min verslas — easiest big-media pitch, public journalist directory:
     verslo redaktorė Jurgita Šimelevičienė, j.simeleviciene@15min.lt
     (15min.lt/kontaktai). "Organizacijų pranešimai" section = the paid PR
     channel; pitching journalists directly is free editorial.
   – vz.lt: personal emails are obfuscated on vz.lt/kontaktai — do NOT guess;
     call the desk: inovacijos/technologijos Akvilė Venckutė +370 5 2507 137
     (best startup target), SVV Gabija Sabaliauskaitė +370 5 2507 140, or
     info@vz.lt naming the editor.
   – delfi verslas: no public tips email found — general delfi@delfi.lt
     (delfi.lt/apie).
   – sa.lt: redakcija@sa.lt (sa.lt/kontaktai). structum.lt: info@structum.lt —
     weakest freshness signal (© 2022 footer); spot-check recent output before
     investing in a pitch.
   – madeinvilnius.lt: info@madeinvilnius.lt (madeinvilnius.lt/en/kontaktai).
   – startuplithuania.com: alive (run by Innovation Agency Lithuania; news
     2026-06-18) — startup database signup at startuplithuania.com/startup/.
     Separate org from unicorns.lt (the private association, also active) —
     register with Startup Lithuania, consider Unicorns membership separately.
5. **Forums/communities, genuinely:** answer real sąmata questions (FB groups,
   miestai.net, reddit r/lithuania when relevant) with useful math, mention the
   tool only when asked / signature-level. Engines index these threads; spam
   dies, usefulness compounds. **Aliveness check 2026-07-06:** miestai.net is
   very active (same-day posts; ~1.49M posts, 519 active users; "Projektai ir
   statybų eiga" section alone: 289K posts — miestai.net/forumas/) but its
   audience is urbanism watchers, not working rangovai; statybosforumas.lt
   ("didžiausias statybos forumas Lietuvoje") is DNS-dead; no other live LT
   construction forum found — **LT builders discuss mostly in Facebook groups**
   (verified group list in social-ads-playbook §1). r/lithuania: activity not
   verifiable this session (reddit blocked to fetchers) — check manually.
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
