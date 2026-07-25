# ConsultCouncil 3-Round Debate — SEO Agent Design

**Date:** 2026-05-13
**Topic:** Should Sąmatų AI build an autonomous Claude Code SEO agent? Design specifics.
**Participants:** Claude (Opus 4.7), ChatGPT (GPT-5.5), Gemini (3.1 Pro Preview)

---

## Round 1 — Independent Opening Positions

**Claude R1:** Defer autonomous agent to Mo 4 when daily organic visitors > 100. Use Anthropic marketing plugin's `/seo-audit` slash command monthly until then. Design spec now but flag "do not deploy until Mo 4 or 100 weekly organic visitors." If forced to Mo 2: weekly GitHub Actions cron + manual `/seo-audit` slash; 2 jobs (SERP delta + content gap); DataforSEO API ($0.024/mo for 40 SERPs); GSC; Slack + markdown report; no auto-publish; kill switch at 4 weeks no signal.

**ChatGPT R1:** Don't build "real autonomous SEO agent" — build thin SEO monitoring + briefing bot. <6-8h build. Weekly GitHub Actions cron Mondays 08:00 + manual workflow_dispatch. 3-5 jobs: weekly SERP delta for 10-20 LT keywords, competitor snapshot (title/meta/H1) for 4-6 competitors, own-site technical checklist for 12 URLs, content brief suggestions ranked by commercial intent, GSC delta. Output Slack + markdown in `/seo-reports/YYYY-MM-DD.md`. Focus on BoFu (Sistela alternatyva, PDF brėžinių kiekių ištraukimas) + trade pages, NOT 50 blog articles. No auto-publish. Measurement = actions shipped, not reports.

**Gemini R1:** Don't build autonomous agent. Mo 2 MVP = Locally-Triggered Content Brief Generator. Pure human-initiated CLI (`make seo-sprint`) weekly. No cron, no Slack pinging. 3 tasks: GSC API free, BeautifulSoup scrape top 10 google.lt for 2 BoFu keywords, generate opinionated content brief. Haiku for HTML parse + Sonnet for brief, heavy prompt caching on competitor baselines. Output = Markdown to `/_drafts/`. Hard guardrail: NO Auto-Publishing, NO Final Copywriting. **"Lithuanian LLM output sounds robotic; trade-specific terminology errors will destroy trust."** Executor's weekly SERP delta is "too passive."

---

## Round 2 — Cross-Critique

**Claude R2 (private scratch):** Concedes "Mo 4 / 100 visitors" threshold is too rigid for hyper-niche LT B2B (could take a year). Better gate: "first 5 indexed pages live + first GSC impressions register" — Mo 2-3 realistic. Disagrees with Gemini's no-cron purism (founder memory dies in validation, ChatGPT's point lands). But Gemini's R2 PR-output is the strongest shift in the debate — beats both Slack reports. Convergence emerging: weekly cron + PR draft (no auto-merge) + GSC + competitor lightweight diff.

**ChatGPT R2:** Concedes Claude's "0-traffic has nothing to trend" but rejects Mo 4 / 100 visitors as "far too late" — highest-leverage SEO happens BEFORE traffic exists (indexing hygiene, query mapping, page diffs, title/meta, internal linking). Strongly agrees with Gemini's "robotic LT output" warning. Disagrees with Gemini's no-cron — "cron does not mean reckless autonomy; removing cron makes system dependent on memory which is what automation should solve." Says Gemini's "SERP delta too passive" is fair but overstated. Synthesis call: "Mo 2 = cron-triggered SEO researcher, human-reviewed outputs, strict spend caps, no publishing, success = founder-approved page changes or briefs not rankings alone."

**Gemini R2:** Concedes Claude's "0-traffic has nothing to trend" and "content gap analyzer useless in Mo 2 when gap is everything." Disagrees with 100-visitors / Mo 4 threshold — niche LT B2B could take over a year. Calls ChatGPT's "<6-8h build with 5 jobs + competitor scraper" a "wildly optimistic textbook distraction — fragile headless scrapers are a massive ongoing time-sink." Concedes ChatGPT's BoFu focus is exactly right. **Killer pivot: agent shouldn't output Slack report → should output PULL REQUEST containing drafted localized landing page.** "Slack report creates anxiety, not leverage. Bot must draft deployable assets, not more reading material for already overwhelmed founder."

---

## Round 3 — Final Positions

**Claude R3:** Build a small semi-autonomous SEO PR generator (not full autonomous agent). Weekly GitHub Actions cron + workflow_dispatch. Deploy at Mo 2-3 when first 5 pages indexed + GSC impressions register, NOT Mo 4/100 visitors (concession to ChatGPT+Gemini). Output = GitHub PR with drafted BoFu LT landing page (concession to Gemini — strongest shift in debate). Tiny GSC sidebar in PR description (raw numbers only, no analysis). Inputs: GSC + manual competitor URL list + optional DataforSEO SERPs. Jobs: GSC query delta, BoFu opportunity selection from a curated keyword list, one drafted page or page-improvement patch. NO scraper maintenance. NO auto-publish. <€10/mo (Haiku for parse + Sonnet for brief + prompt caching). Kill if 4-6 weeks no merged PR.

**ChatGPT R3:** "Do not build real autonomous SEO agent in Mo 2. Build small semi-autonomous SEO PR generator that runs weekly, uses GSC once impressions exist, creates reviewable PRs with localized BoFu landing-page drafts." Gate: first ~5 pages indexed + GSC first impressions. Output: PR containing drafted page (sistela-alternatyva.md, samatu-programa-dirbtinis-intelektas.md, "sąmatos iš PDF elektrikams" etc.) + tiny checklist. Avoid BeautifulSoup/headless scraping unless manually triggered. Use GSC + manual competitor URLs + optional DataforSEO/SerpAPI within budget. ONE weekly GitHub Action + workflow_dispatch, ONE Claude Code command, ONE PR. Strongest hold against Gemini's manual-CLI: **"during validation, anything requiring memory becomes nonexistent."**

**Gemini R3:** Concedes Claude+ChatGPT's critique of his "pure CLI / no-cron" — agrees founder memory will fail. Endorses Weekly Cron-Triggered PR Bot at Mo 2 once initial GSC impressions register. **Remaining hold: do NOT add SEO reporting payload (SERP deltas, indexing hygiene, competitor snapshots) to the PR.** "A solo founder with €200/mo does not have the cognitive bandwidth to analyze SERP volatility. They only have time to write. If the agent delivers a report, it creates homework; if it delivers a targeted content brief, it removes friction." Final design: Cron-Triggered Briefing Bot — weekly GitHub Action queries GSC + scrapes top 10 google.lt for one BoFu target + opens PR with Sonnet-generated structured content brief. No Slack, no dashboards, no auto-publish. Success = # of AI-generated briefs the founder writes and merges.

---

## Convergence (All 3 Agree After R3)

1. **NOT a full autonomous SEO agent.** Small semi-autonomous PR-generating bot.
2. **Deploy at Mo 2-3** when first 5 pages indexed + first GSC impressions, NOT Mo 4 / 100 visitors.
3. **Weekly GitHub Actions cron + manual workflow_dispatch.** GitHub-native, free, versioned, founder-memory-proof.
4. **No auto-publish, no auto-merge** — human review required.
5. **Output = Pull Request with deployable Markdown asset**, not Slack reports.
6. **Focus on BoFu localized Lithuanian queries** ("Sistela alternatyva", trade-specific landing pages), NOT 50 generic blogs.
7. **Inputs:** GSC (free) + manual competitor URL list + optional cheap SERP API (DataforSEO ~$0.024/mo).
8. **Cost:** Haiku for HTML parsing + Sonnet for briefs + prompt caching on baselines → <€10/mo.
9. **Lithuanian human polish required.** LLM output sounds robotic; LT trade terminology errors destroy trust.
10. **Kill switch** at 4-6 weeks if no merged PR / no shipped page.
11. **Success metric** = # of AI-generated briefs the founder actually merges (NOT rankings, NOT reports generated).

## Remaining Split — Reporting vs Pure Briefing

**ChatGPT + Claude:** PR includes a small SEO-state report alongside the brief (GSC delta, indexing hygiene check, title/meta diffs).

**Gemini:** PR contains ONLY a drafted brief / page. Reporting = distraction. "Data without a marketing team is distraction; brief is catalyst."

Gemini's argument is the strongest single claim in the entire debate.

## Council Scoreboard (R1 → R3 Evolution)

- **Claude:** R1 "defer to Mo 4 / 100 visitors" → R3 "Mo 2-3 when first GSC impressions register." Conceded the threshold. Adopted Gemini's PR-output framing.
- **ChatGPT:** R1 "weekly cron + Slack report" → R3 "weekly cron + GitHub PR with drafted page." Conceded Slack-anxiety point. Held cron-vs-memory line through all 3 rounds.
- **Gemini:** R1 "no cron, manual CLI only" → R3 "cron-triggered PR bot." Conceded the cron after both opponents made the founder-memory argument. **Held the briefing-not-reporting line through all 3 rounds and won the payload debate** (PR output, BoFu focus, no-scraper-maintenance critique).
