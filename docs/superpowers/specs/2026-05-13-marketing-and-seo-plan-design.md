# Sąmatų AI Marketing & SEO Plan — Design Spec

**Date:** 2026-05-13
**Status:** Brainstormed + pressure-tested (LLM Council + ConsultCouncil 3-round debate).
**Supersedes:** No prior marketing spec. This replaces the working strategy implied by `landing-prompt-v2-claude-design-2026-05-12.md` (which targets landing visual identity only, not channel/SEO strategy).

---

## Why this spec exists

Sąmatų AI is a working beta in 2026-05. The product reads PDF construction drawings and extracts quantities for sąmatos. It's deployed at `samatu-ai.vercel.app`, no custom domain, no SEO scaffolding (zero meta description, no OG tags, no schema, no sitemap, no robots.txt, empty SPA shell that crawlers see as 0 words). Pre-revenue.

The founder asked for a 90-day bootstrap marketing plan that included a SEO content track + community track + a custom Claude Code SEO agent.

An LLM Council pressure-test fundamentally rejected the original 90-day "Hybrid Twin-Engine" strategy and replaced it with a 30-day validation sprint + conditional 60-day acceleration. A ConsultCouncil 3-round debate (Claude + ChatGPT + Gemini) then converged on a specific design for the SEO agent (which is preserved here as a parked artifact, activated only after the 30-day validation hits its milestones).

This spec captures both layers — what to do in the next 30 days, and what to build/deploy if the validation succeeds.

---

## Executive Summary

**The 90-day plan in one sentence:** Spend the first 30 days proving the product works on real strangers' PDFs and 3 owners will pay €49; spend the next 60 days only if that bar is hit.

**The five hardest truths from pressure-testing:**

1. **The product is unproven** (beta still misses ceiling >3m on p1 per the project memory). No marketing plan rescues an unreliable extractor.
2. **The buyer is the 3-15 employee contractor-owner**, NOT the 40-55 yr old samatininkas on the construction site. The samatininkas is the displaced *user* (will knife the tool in FB groups). The owner currently pays the samatininkas €200-500 per project to outsource.
3. **"Feeds Sistela not replaces"** was cope. The honest pitch is "skip the samatininko" or "3× your bid throughput." The Sistela round-trip claim is also empirically unverified — the integration must be tested before any positioning can rest on it.
4. **The right channels are warm intros + LinkedIn + accountant/APVA networks**, NOT FB Statybininkai for sales (use FB only for learning and reputation). LT is in a €20M phone-scam crisis (2025), so cold calls are dead.
5. **The SEO content marathon and nightly SEO agent are founder-as-engineer escapism** for a 0-DA site in Mo 1-2. Search volume on target LT keywords is likely sub-100/mo. Defer all heavy SEO content + agent infrastructure until Mo 2-3 validation milestones are hit.

---

## Phase 1 — Days 1-7: Empirical Reality Check (NO marketing)

Goal: verify the product is sellable and the positioning is honest before spending one hour on marketing.

### 1.1 Product validation test
- Pick 10 real LT construction PDFs the founder has never seen (anonymize via existing test corpus or new sources via FB Statybininkai post asking for "test brėžinį AI tool'ui").
- Run each through current beta unattended (no manual prompt tweaks).
- Score each: **success** if the produced KŽ has ≥80% correct line items with ≤2 manual corrections; **partial** if 50-80%; **fail** if <50%.
- **Pass bar:** ≥7/10 success or partial. **<7/10 → stop marketing, return to product.**

### 1.2 Sistela round-trip test
- Take 3 successful KŽ outputs from §1.1.
- Export from Sąmatų AI in the format claimed to "feed Sistela."
- Open in Sistela. Document: does the import work without manual editing? How many fields require fix-up? Does pricing/units/sections map cleanly?
- **Pass bar:** 0 manual edits per row OR <5 minutes total cleanup per import. Anything more, kill "feeds Sistela" as positioning today and replace with "skip the samatininko."

### 1.3 Keyword reality check
- Open Google Keyword Planner (free with Google Ads account).
- Pull monthly search volumes for: `sąmatų programa`, `kiekių žiniaraštis programa`, `samatininko programa`, `AI sąmatos`, `Sistela alternatyva`, `PDF brėžinių kiekiai`, `statybos sąmata`, plus 4 trade-specific (e.g., `vidaus apdailos sąmata`, `fasado kiekiai`, `stogo plotas`, `betono kiekiai`).
- Document the actual volumes.
- **If top single keyword <100/mo:** kill the 24-blog content plan permanently. Replace with 4 ultra-targeted BoFu landing pages (Phase 3).
- **If top single keyword 100-500/mo:** content plan is viable at 1 post/week (not 2.5).
- **If top single keyword >500/mo:** earlier estimates were too conservative; rerun strategy.

### 1.4 Owner-contact list build
- This is the founder's actual first deliverable, per peer reviewer 1.
- Build a list of 100 LT construction company owners, 3-15 employees, who do interior/renovation/general contracting (the segment that pays a samatininkas per project).
- Sources: rekvizitai.vz.lt (free API, name/code/VAT/address; phones/emails paid), LSA member list (member companies), APVA renovation contractor lists (renomap.apva.lt), LinkedIn Sales Navigator filters (LT + Construction + 1-50 + title contains vadovas/direktorius), referrals from accountants.
- For each: company name, owner name (if findable), email or LinkedIn, source, last public activity. Stored in a single CSV.
- **Pass bar:** 100 rows in CSV by end of Day 7.

### 1.5 Audit deliverables (end of Day 7)
- `audit/2026-05-13-product-validation.md` — §1.1 results table
- `audit/2026-05-13-sistela-roundtrip.md` — §1.2 results
- `audit/2026-05-13-keyword-volumes.csv` — §1.3 numbers
- `audit/2026-05-13-owner-list.csv` — §1.4 list of 100

If any pass bar fails: **stop the plan, fix the underlying issue, re-run the check.**

---

## Phase 2 — Days 8-30: Hand-Sell to 10 Owners

Goal: 3 owners pay €49 for a single-project pilot after seeing the tool run on their own PDF. If this fails, no marketing strategy matters — the product/market fit is the problem.

### 2.1 Positioning (overrides original spec)

**KILL unconditionally:**
- "Pirmasis lietuviškas AI sąmatininkas" (press-release line, not a value prop).
- **"Feeds Sistela" / "Sistelai paruošta" / any framing that makes Sąmatų AI an accessory to Sistela.** Add-on pitches die. "Feeds X" hides what the product actually does. The product is the takeoff tool. Sistela compatibility is a feature, not a category. The Notion test: Notion exports to Markdown, but its homepage doesn't say "Notion feeds your Markdown editor."
- Leading with the word "AI" anywhere on the homepage hero. Lead with outcome.

**USE this single pitch** (one pitch, not two — the §1.2 Sistela round-trip test determines a feature bullet, not a re-frame):

> **"Užmeskite PDF brėžinį — kiekius gausite per 5 minutes. Be samatininko."**
>
> Subline: *"Tas pats sąmatos darbas, kurį dabar perka iš kito žmogaus už €200-500 už projektą. Tas pats išvedinys — sumos suvedat patys."*

Both lines are outcome-led, name the price the buyer is currently paying, and call the displaced labour by name. No "AI." No "Sistela." No "pirmasis."

**Homepage hero (per Outsider advisor):** show a real PDF on the left, a real KŽ spreadsheet on the right, with a literal arrow. The pitch above is the headline beneath the visual.

**Sistela appears only here:** on `/funkcijos` (or pricing page) as a checkbox bullet — *"Eksportas į Sistela formatą"* — alongside *"Eksportas į Excel"*, *"Eksportas į PDF"*. If §1.2 round-trip test fails, the Sistela bullet is removed and the product simply ships Excel/PDF. **No positioning change either way.** This is the cleanup of the original "feeds Sistela" line: Sistela is a format, not a relationship.

### 2.2 Channel allocation (Days 8-30)

| Channel | Effort | Goal | Why |
|---------|--------|------|-----|
| **Warm-intro DMs to owners** | 1-2 hrs/day | 10 demo calls booked | The only proven path to a 40-55 yr old LT business owner. Source: §1.4 list + asking each accepting owner for 1 referral. |
| **LinkedIn outreach** | 30 min/day | 30 connect requests/wk → 5 demo calls | Filter: LT + Construction + 1-50 emp + title in {vadovas, direktorius, savininkas}. Message: outcome-led, not feature-led, no AI buzzword in subject line. |
| **APVA general-contractor outreach** | 1-2 hrs/wk | 2 demo calls | APVA renovation pipeline mandates KŽ; this is the highest-fit warm channel. Source: renomap.apva.lt + APVA newsletter contacts. |
| **Accountant network** | 30 min/wk | 5 referrals to construction-clients | Accountants serving construction firms talk to owners about cost; a referral from accountant to "skaitmenizuoti sąmatas" pitch carries weight. Cold-message 10 accountants/wk on LinkedIn. |
| **FB "Statybininkai"** (LEARNING only) | 15 min/day | 0 sales pitches; capture vocabulary, objections, common PDFs | The persona lives there but is **the user, not the buyer**. Use to: (a) gather LT terminology corpus, (b) detect objections before they're raised on a call, (c) eventually post one anonymized "interesting PDF" demo per month for reputation. Do NOT pitch. |
| **Samatininkas-reseller experiment** | 1 hr/wk | 1 freelance samatininkas piloting | Per peer review insight: the displaced user could be a distribution partner. Offer 1-2 freelance samatininkai an early-access deal where they resell to their clients and split fees. Lowest priority but highest leverage if it lands. |

### 2.3 Sales loop

For each owner who agrees to a demo:
1. Ask for one real PDF they actually used in the last 60 days (with anonymization if needed).
2. Run the tool on it before the call.
3. 20-min call: show their KŽ on screen, walk through the deltas vs what they got from their samatininkas, ask "what would you change?"
4. End: "€49 single project, full extraction, your KŽ exported to Sistela or Excel. Pay if it saved you time. If not, I delete the result. Deal?"
5. Track all responses in a single CRM (free Notion/Airtable/spreadsheet). Goal: 3 yes by Day 30.

### 2.4 Phase 2 deliverables (end of Day 30)
- `validation/2026-05-13-pilot-results.md` — 10 demo calls run, conversion rate, top 3 objections.
- `validation/2026-05-13-positioning-validated.md` — which pitch landed, with quotes from demos.
- `validation/2026-05-13-pricing-validated.md` — what owners said about €49/project, alternatives proposed.
- 3 paying customers OR documented diagnosis of why not.

**Pass bar to enter Phase 3:** 3 paying owners. **<3 paying:** do NOT enter Phase 3 marketing scale-up; iterate product/positioning for another 30 days.

---

## Phase 3 — Days 31-90: Conditional Acceleration

Activated ONLY if Phase 2 passes (3 paying owners). If Phase 2 fails, this phase is replaced with another 30-day validation cycle.

### 3.1 SEO foundation (Week 5-6)

Pre-conditions met by Phase 2 success: real customer language captured (use it in copy), real LT keyword volumes known (§1.3), real Sistela integration validated (§1.2).

**Custom domain.** Register `samatu.ai` (preferred — short, brandable) or `samatuai.lt` (LT TLD signal for LT market) via Vercel domains. Point production to it. ~€10-40/yr.

**Static SEO scaffolding in `frontend/index.html`** (no SSR migration yet — that's later):
- `<title>` expanded: `Sąmatų AI — AI iš PDF brėžinių paskaičiuoja kiekius per 5 minutes`
- `<meta name="description">` — 150-160 chars, outcome-led, one verb, one number
- `<meta property="og:title">`, `og:description`, `og:image` (use existing landing-hero asset), `og:url`
- `<meta name="twitter:card" content="summary_large_image">`
- `<link rel="canonical" href="https://samatu.ai/">`
- JSON-LD `SoftwareApplication` schema block (name, description, applicationCategory: BusinessApplication, offers.price, offers.priceCurrency: EUR, inLanguage: lt)
- `public/robots.txt` — `User-agent: * / Allow: / / Sitemap: https://samatu.ai/sitemap.xml`
- `public/sitemap.xml` — listing landing + 4 BoFu pages (when they exist)
- Per-route `<title>` via `react-helmet-async` (added when landing pages added)

**Prerender for crawlable HTML.** Add `vite-plugin-prerender-spa` or migrate the marketing-only routes to a Next.js subapp. The /app/ React SPA stays as is. Goal: served HTML for `/` and `/sistela-alternatyva` etc. contains real LT body text Googlebot can index without rendering JS. ~8h work.

### 3.2 BoFu landing pages (Week 5-10)

Build 4 pages ONLY (not 8-10 as originally scoped). Pick the 4 highest-volume keywords from §1.3 keyword reality check. Likely candidates:
- `/sistela-alternatyva` — comparison page, honest about what Sąmatų AI does vs Sistela. Title: "Sąmatų AI vs Sistela: kuo skiriasi ir kada naudoti vieną ar kitą".
- `/pdf-brezini-kiekiai-automatiskai` — outcome page. Title: "Kiekiai iš PDF brėžinių per 5 minutes — be samatininko".
- `/vidaus-apdailos-samata` — trade-specific. Reuses Section 1 CLAUDE.md formulas as authority signals.
- `/apva-renovacijos-kiekiai` — APVA segment wedge. Title: "APVA renovacijos KŽ: kaip per dieną paruošti pasiūlymą".

Each page: 800-1500 LT words, hero with PDF→spreadsheet visual, 3 testimonial blocks (from Phase 2 customers, with permission), Sistela compatibility note, single CTA (book a demo).

### 3.3 Content cadence (Week 5-12)

**1 LT blog post per week, max 8 posts in the quarter.** NOT 24-30. Topics: only what came up in Phase 2 demo calls. Real objections, real questions. Drafted by Claude (Sonnet), polished by founder (Lithuanian polish is non-negotiable — see SEO agent design §4 on this).

### 3.4 Community + PR

- **FB "Statybininkai"** continues at 15 min/day, now ALSO with 1 weekly anonymized PDF demo post. Sales attribution still goes through calls, not FB.
- **SA.lt pitch** (Statyba ir architektūra) — Week 5: send a feature pitch "Kaip AI per 5 min paskaičiuoja KŽ iš PDF — LT samatininko realybės testas". Include real numbers from Phase 2.
- **Verslo Žinios pitch** — Week 6: founder profile angle "Solo LT startuolis, kuris išmokė AI skaityti statybos brėžinius". Easier hook than feature.
- **vev.lt Sistela trainer partnership** — Week 8: warm-intro conversation. Offer 30% rev-share on any customer the trainer brings.
- **Skaitmeninė Statyba 2026 conference** — Week 12 (only if Phase 2 hit and there's a customer to bring). Sponsor a coffee break (~€300) and bring 1 paying customer for an in-person testimonial.

### 3.5 SEO PR Bot deployment

Activated when: first 5 BoFu pages live + GSC registers first impressions (likely Week 6-8).

Full design in §4 below. The bot stays disabled until that gate.

### 3.6 Phase 3 success criteria (Day 90)

| Metric | Target | Source |
|--------|--------|--------|
| Paying customers | 10 | CRM |
| Product success rate | ≥80% unattended on stranger PDFs | Recurring §1.1-style test |
| MRR | €300-500 | CRM + Stripe |
| Indexed pages | 8-12 | GSC |
| Top 10 ranking | 1-2 LT keywords | GSC + SERP check |
| Demo conversion rate | ≥30% (3+ of every 10 demos pay) | CRM |
| Press features | 1 (SA.lt or VŽ) | Manual |

**Day 90 review checkpoint:** rerun this spec's Phase 1 audit. If MRR <€200 and no product success-rate improvement, the council was right and this is not yet a business. Reset to another validation sprint.

---

## §4 — SEO PR Bot Design (Parked Artifact)

**Status:** Designed now. **Deployed at Phase 3 §3.5 gate** (first 5 BoFu pages live + GSC impressions registered).

**Consensus design from ConsultCouncil 3-round debate** (transcript: `consultcouncil-transcript-2026-05-13-seo-agent.md`).

### 4.1 What it does

One weekly automated job. Opens one GitHub Pull Request per week containing one Sonnet-drafted Lithuanian BoFu landing page or page-improvement patch. Human reviews, polishes Lithuanian grammar/terminology, merges or closes.

**The bot is NOT:**
- A nightly content factory.
- An SEO dashboard / reporting tool. ([Gemini's strongest argument](#consultcouncil-strongest-argument): "Data without a marketing team is distraction; brief is catalyst.")
- A competitor-scraping system requiring maintenance.
- Allowed to auto-merge or auto-publish.

### 4.2 Architecture

```
.github/workflows/seo-pr-bot.yml         # GitHub Actions cron
  trigger: schedule (cron Mondays 08:00 Europe/Vilnius) + workflow_dispatch (manual)
  runs: scripts/seo_pr_bot/run.py
  needs: secrets.ANTHROPIC_API_KEY, secrets.GSC_SERVICE_ACCOUNT_JSON
  permissions: contents: write, pull-requests: write

scripts/seo_pr_bot/
  run.py                # entry point
  config.yaml           # input config (see §4.3)
  prompts/
    brief_system.md     # cached system prompt (~2k tokens, mostly static)
    brief_user.md       # per-run user prompt template
  lib/
    gsc.py              # Google Search Console queries
    serp.py             # optional: DataforSEO SERP fetch (off by default)
    pr.py               # GitHub PR creation via Octokit
    anthropic_client.py # cached Sonnet calls
```

### 4.3 Inputs (config.yaml, version-controlled)

```yaml
target_keywords:
  - sistela alternatyva
  - pdf brėžinių kiekiai
  - kiekių žiniaraštis programa
  - ai sąmatos
  - apva renovacijos kž
  - vidaus apdailos sąmata

competitors:  # manually curated; no scraper
  - sistela.lt
  - prosama.lt
  - dycode.net
  - samata123.lt
  - astera.lt
  - kreo.net
  - togal.ai

gsc_property: https://samatu.ai/
gsc_service_account: env:GSC_SERVICE_ACCOUNT_JSON

serp_enabled: false  # set true only if budget allows (~$0.024/mo via DataforSEO)
serp_provider: dataforseo

draft_target: 1   # number of PRs to open per run; 1 = MVP
content_kill_switch_weeks: 4  # if no PR merged in this window, agent self-disables
```

### 4.4 Output (per run)

Single GitHub PR:
- **Branch name:** `seo-bot/YYYY-MM-DD-{slug}` (e.g., `seo-bot/2026-06-30-apva-renovacijos-kz`)
- **PR title:** `[SEO bot] {Slug} — drafted landing page` (e.g., `[SEO bot] sistela-alternatyva — drafted landing page`)
- **PR body** (markdown):
  - `## Reasoning` — 5-line summary of why this slug was chosen this week (which GSC opportunity, which competitor gap, which target keyword).
  - `## GSC sidebar` (raw numbers, no analysis): top 5 queries by impression for the property this week, with impressions / clicks / position. Founder ignores or uses; bot does NOT interpret.
  - `## Suggested next steps` — 3 bullet checklist (e.g., "polish LT grammar", "add 1 LT-language testimonial", "wire CTA to /demo").
- **Files changed:**
  - `frontend/src/pages/landing/{slug}.md` (or `.tsx`) — the drafted page content
  - Optional: `public/sitemap.xml` updated to include the new route

**Forbidden in output:**
- Edits to `frontend/src/` outside the landing pages directory
- Edits to any backend file
- Edits to `package.json`, `vercel.json`, or config files
- Auto-merge or auto-deploy via push to main

### 4.5 Guardrails

| Rule | Mechanism |
|------|-----------|
| No auto-publish | Branch protection on `main` + no admin bypass |
| No auto-merge | GitHub branch protection requires 1 approving review on PRs |
| No edits to backend / src outside `/landing/` | Pre-commit script in the bot validates changed paths |
| LT human polish required before merge | PR template includes "I read every Lithuanian sentence out loud" checkbox |
| Cost <€10/mo | Token cap enforced in `anthropic_client.py` (50k tokens/run hard limit) |
| Competitor URLs only fetched manually | `serp_enabled: false` by default; if enabled, max 1 query/week |
| Self-disable on inactivity | `content_kill_switch_weeks` check — if no PR merged in N weeks, bot opens an issue "kill switch tripped, review whether to continue" instead of generating new content |
| No fabricated benchmarks or customer counts | System prompt explicitly forbids; PR template has "I verified all numerical claims" checkbox |

### 4.6 Cost model

Per weekly run:
- Sonnet brief generation: ~25k input + 5k output tokens = ~€0.45
- Haiku HTML parsing (if SERP enabled): ~5k tokens = ~€0.01
- GSC query: free
- GitHub Actions minutes: free (within free tier)
- Total per week: ~€0.50 → **~€2.00/mo**

Prompt caching strategy:
- System prompt (brand voice, LT terminology rules, competitor baselines) cached → reused across all runs in a 5-min window
- Per-run prompt only contains: this week's GSC delta (compact) + selected target keyword + brief template

### 4.7 Measurement (self-reported by bot in monthly summary)

The bot opens a separate monthly "self-audit" issue with these stats:
- PRs opened: N
- PRs merged: N
- PRs closed without merge: N
- Tokens consumed: N
- Cost: €N
- **Action ratio** = merged / opened. **Kill threshold: action ratio <30% for 4 consecutive weeks.**

### 4.8 The Executor's MVP, refined

The Executor's original "weekly SERP delta in Slack, 6h to build" is the wrong shape — it generates reading material. The right MVP is: **weekly GitHub Actions cron → opens one PR with one Sonnet-drafted LT BoFu page → human polish + merge → deploy via Vercel auto-deploy**. Build time: ~8-12h (one-time). Maintenance: <30 min/week reviewing the PR.

This is the minimum that produces deployable assets every week and forces founder attention to the content, not the metrics.

### 4.9 What this design explicitly rejects

| Original plan | Rejected because |
|---------------|------------------|
| Nightly cron | No data changes nightly for a 0-DA site; wastes tokens and signal-to-noise |
| Slack message output | Generates anxiety, not action (Gemini R2) |
| SERP delta as primary output | "Sistela outranked you" alone is not actionable (Gemini R1) |
| Competitor HTML scraping pipeline | Fragile, maintenance trap for solo founder (Gemini R2) |
| Heavy multi-job report (5 jobs/run) | Reading material, not deployable assets (Gemini R3) |
| Auto-publish capability | Lithuanian LLM output is robotic; brand trust would die (Gemini R1, ChatGPT R2) |
| Deploy at Mo 1 | Founder bottleneck is product validation, not SEO automation (LLM Council unanimous) |

---

## §5 — Council Risks & Acknowledged Blind Spots

Documented here so future-me cannot pretend the council didn't say these things.

| Risk | Source | Mitigation in spec |
|------|--------|--------------------|
| The founder may not have 10 warm contractor contacts to start | Reviewer 1 (LLM Council) | §1.4 makes the contact-list-build the first deliverable; without it Phase 2 is blocked. |
| Buyer ≠ User; owner reachable via accountants/APVA/LinkedIn, not FB | Reviewer 2 (LLM Council) | §2.2 channel allocation routes sales through accountants/APVA/LinkedIn, treats FB as learning-only. |
| Product unattended success rate is unknown today | Reviewer 3 (LLM Council) | §1.1 makes measuring this Day 1's task. Failure stops the plan. |
| Samatininkas as distribution partner is unexplored | Reviewer 4 (LLM Council) | §2.2 includes a reseller pilot row at lowest priority (won't block validation, but tested if bandwidth allows). |
| Sistela integration claim is unverified | Reviewer 5 (LLM Council) | §1.2 forces the round-trip test; positioning conditional on result. |
| LT LLM output sounds robotic; trade-terminology errors destroy trust | Gemini (ConsultCouncil) | §4.5 mandates LT human polish before merge; no auto-publish. |
| Founder memory dies during validation if any process is manual | ChatGPT (ConsultCouncil) | §4.2 uses GitHub Actions cron, not manual CLI. |
| Reporting payload becomes homework not catalyst | Gemini (ConsultCouncil) | §4.4 strips reporting from PR; only raw GSC sidebar, no interpretation. |
| Mo 4 / 100-visitor gate is too late for hyper-niche LT B2B | ChatGPT + Gemini (ConsultCouncil) | §3.5 gate changed to "first 5 indexed pages live + first GSC impressions register" (likely Mo 2-3). |

---

## §6 — Monday-Morning Single Action

Per LLM Council chairman verdict: the founder's literal first action is **NOT** to open this spec and start building. It is:

> **Run the current beta, unattended, on 5 real contractor PDFs you have never seen before. Score success/failure honestly. Write the numbers down. Email them to yourself by 11am.**

If unattended success rate is <70%, this entire spec is on hold. The next 30 days are product, not marketing.

If unattended success rate is ≥70%, proceed to §1 Phase 1 audit.

---

## §7 — What This Spec Replaces / Defers

**Replaces:**
- The implicit "Hybrid Twin-Engine" 90-day plan brainstormed in this session.
- Any prior intent to build a nightly SEO agent.

**Defers (until Phase 3 §3.5 gate):**
- Custom domain (€10-40/yr — could be done in Phase 1 if zero-effort, but not blocking)
- 8-10 trade-specific landing pages → reduced to 4 BoFu pages, deferred to Week 5-10
- 24-30 LT blog posts → reduced to 1/week max, only Phase 3
- Magnet ebook "Sąmatininko klaidų kaina: 14 pozicijų" → deferred to Mo 4+, only if traffic exists to capture
- Skaitmeninė Statyba 2026 conference sponsorship → deferred to Week 12, only if Phase 2 hits
- SEO PR Bot deployment → deferred to Phase 3 §3.5 gate
- APVA "approved tools" listing — exploratory in Phase 3, real push in Mo 6+
- Baltic / Polish expansion (Expansionist advisor): deferred to Mo 6+ when LT PMF proven

**Permanently killed:**
- "Pirmasis lietuviškas AI sąmatininkas" headline
- **"Feeds Sistela" / "Sistelai paruošta" / any add-on framing — unconditionally.** Sistela is a file format, not a positioning relationship. The §1.2 round-trip test only determines whether the Sistela export checkbox stays on `/funkcijos`; it does NOT bring back the "feeds Sistela" headline under any condition.
- Cold-call outreach (LT €20M scam crisis 2025 makes this dead)
- Nightly SEO agent
- Sales pitching in FB Statybininkai group (FB is learning-only)
- "AI" as the lead noun on the homepage hero (lead with outcome — "kiekiai per 5 min", "be samatininko")

---

## §8 — Related Documents

- LLM Council pressure-test of original strategy: `council-report-2026-05-13-marketing-strategy.html` + `council-transcript-2026-05-13-marketing-strategy.md`
- ConsultCouncil 3-round SEO agent debate: `consultcouncil-transcript-2026-05-13-seo-agent.md`
- Landing page visual design spec: `landing-prompt-v2-claude-design-2026-05-12.md`
- Research streams that informed this spec (see this session's parallel research agents in conversation history):
  - Current site SEO baseline audit
  - LT construction marketing channel inventory
  - Competitor marketing teardown (Sistela, ProSama, Astera, Togal, Kreo, PlanRadar, STACK, PlanSwift, Bluebeam)
  - Anthropic marketing skill availability check
