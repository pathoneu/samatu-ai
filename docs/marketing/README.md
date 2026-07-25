# Pathon marketing — index

Written 2026-07-06. The complete go-to-market execution set. Positioning inherits
[`../superpowers/specs/2026-05-13-marketing-and-seo-plan-design.md`](../superpowers/specs/2026-05-13-marketing-and-seo-plan-design.md)
(one pitch, outcome-led, no "AI" in hero, no "feeds Sistela").

| File | What it is |
|---|---|
| [2026-07-06-master-plan.md](2026-07-06-master-plan.md) | The 90-day integrated plan: KPIs, weekly calendar, budget, who-does-what |
| [seo-playbook.md](seo-playbook.md) | Website SEO: what shipped in code today, keyword map, 4 BoFu page outlines, content calendar |
| [ai-seo-geo.md](ai-seo-geo.md) | AI SEO (ChatGPT/Perplexity/AI Overviews): what shipped, citation building, measurement |
| [social-ads-playbook.md](social-ads-playbook.md) | Facebook/LinkedIn/YouTube/TikTok playbook + Google & Meta ads with written LT ad copy |
| [creative-briefs.md](creative-briefs.md) | 10 scripted video briefs + 8 photo briefs |
| [outreach-kit-lt.md](outreach-kit-lt.md) | Hand-sell kit: cold emails, DM, phone script, objection handling, demo flow — all LT |

## Status ledger

**Shipped in code (2026-07-06, branch viewer-rebuild):** robots.txt (AI crawlers
explicitly allowed), sitemap.xml, llms.txt, full OG/Twitter/canonical head,
JSON-LD (Organization + SoftwareApplication + FAQPage), og-image.png share card,
per-route meta helper, /duk FAQ page, consent-gated GA4 loader (no-op until
`VITE_GA4_ID` is set).

**Founder-only tasks (no code):** create GA4 property → set `VITE_GA4_ID` on
host; Google Search Console + submit sitemap; Google Business Profile; FB page;
directory listings; polish all LT copy before it goes anywhere public
(LLM Lithuanian sounds robotic — non-negotiable review step); the Phase-2
hand-sell itself.

**Pending build (task-chipped):** prerender of public routes (the #1 AI-SEO
blocker — AI crawlers don't run JS), 4 BoFu landing pages, public /kainos page.

**[VERIFY] markers — resolved 2026-07-06:** a live-web verification pass
replaced every marker with verified facts + source URLs and dates (crawler UA
census + per-crawler JS behavior, llms.txt adoption reality, LT media
contacts, FB groups, LT CPC benchmarks + low-search-volume mechanics, Meta EU
targeting post-DSA/DMA, live google.lt SERP check). robots.txt gained 7
retrieval-relevant UAs the same day. Two things stayed explicitly
unverifiable without logins: FB group member counts (founder: 15-min
logged-in pass, URLs ready in social-ads-playbook §1) and exact LT keyword
volumes (pull from Keyword Planner once the Ads account exists).
