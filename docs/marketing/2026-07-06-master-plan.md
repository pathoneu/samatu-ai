# Pathon — 90-day marketing master plan (2026-07-06)

**North star:** 3 paying pilot customers by day 45, 10 by day 90 — not traffic.
Traffic channels exist to feed the hand-sell funnel until the product sells itself.

**The one pitch** (locked, spec §2.1 — do not dilute):
> **"Užmeskite PDF brėžinį — kiekius gausite per kelias minutes. Be sąmatininko."**
> Subline: "Tas pats darbas, kurį dabar perkate už €200–500 už projektą. Kainas suvedate patys."

No "AI" in the hero. No "pirmasis lietuviškas". No "feeds Sistela". Sistela = a
checkbox feature ("Eksportas į Sistela formatą") only.

## KPIs (weekly founder review — 15 min)

| Metric | Day 30 | Day 60 | Day 90 |
|---|---|---|---|
| Demos delivered (hand-sell) | 10 | 20 | 30 |
| Paying pilots | 1–2 | 4–6 | 10 |
| GSC impressions (LT queries) | indexed | 500/wk | 1 500/wk |
| Registered accounts | 15 | 50 | 120 |
| AI-answer mentions (monthly prompt panel) | baseline | 2/10 prompts | 4/10 prompts |

## Weekly calendar

**Week 1 (now) — plumbing + list building**
- ✅ DONE (code): robots/sitemap/llms.txt, OG + JSON-LD, /duk, og-image, GA4 loader.
- Founder (≈3 h): GA4 property → `VITE_GA4_ID` env on host; Search Console →
  submit sitemap; Google Business Profile; FB **page**; polish /duk copy.
- Founder: build the 30-owner contact list (spec §1.4) — vardas, įmonė, tel,
  iš kur pažįstamas. This list is worth more than every channel below.

**Weeks 1–4 — hand-sell (THE priority; spec Phase 2)**
- 10+ demos from the kit ([outreach-kit-lt.md](outreach-kit-lt.md)). Target: owners
  currently paying a sąmatininkas. Record every objection verbatim → it becomes
  ad copy and blog topics.
- Google Ads ON from week 2 (€10–15/d, exact match only — [social-ads-playbook.md](social-ads-playbook.md)).
  With LT volumes this small, ads are a *lead trickle + message test*, not a growth engine.
- FB page starts posting 2×/wk (value posts from creative briefs), groups 1×/wk value-first.

**Weeks 5–6 — SEO foundation v2**
- Build: prerender public routes (task chip) + 4 BoFu pages ([seo-playbook.md](seo-playbook.md)) + public /kainos.
- First 2 videos live (hero demo + TikTok flood-fill — [creative-briefs.md](creative-briefs.md)).

**Weeks 5–12 — content + proof**
- 1 LT post/wk (max 8 total, topics ONLY from real demo objections).
- 1 video / 2 wks. Photo day on a real client site (once a pilot agrees).
- First case study with numbers → pitch 2 LT outlets ([ai-seo-geo.md](ai-seo-geo.md) PR list).
- Meta retargeting ON once pixel has ≥500 visitors (not before — wasted € otherwise).
- Directory/listing sweep (one afternoon, checklist in ai-seo-geo.md).

## Budget (monthly, lean)

| Item | € |
|---|---|
| Google Ads | 300–450 |
| Meta retargeting (from wk ~6) | 100–150 |
| Tools (GA4/GSC/GBP free) | 0 |
| **Total** | **≤600** |

Kill rules: any ad group with 0 registrations after €150 spend → pause, rewrite,
retry once, then kill. A content topic that gets 0 impressions in 6 wks → stop
that cluster. FB groups: if 2 value posts get deleted by admins → that group is
DM-only territory.

## Who does what

| | Claude (code/copy drafts) | Founder (irreplaceable) |
|---|---|---|
| SEO tech, pages, schema | ✅ | review |
| LT copy (ads, posts, emails) | drafts | **polish — mandatory** (robotic LT kills trust) |
| Video | scripts/briefs | record screen + face, or hire €50 editor |
| Photos | briefs | shoot on real sites |
| Demos, calls, groups presence | — | **100 % founder** |
| GA4/GSC/GBP/FB accounts | instructions | create (accounts = founder-owned) |

## Hard truths (read before spending)

1. **"Top everywhere" is not buyable this quarter.** LT keyword volumes are tiny
   (dozens–hundreds of searches/mo). The good news: competition is equally tiny —
   focused execution can own this niche in 3–6 months, and ads buy the top of
   the page for €0.5–1.5/click *today*.
2. **AI-SEO's #1 blocker is our own stack**: AI crawlers don't execute JS, and
   the site is a JS-only SPA. llms.txt + static head (shipped today) is the
   stopgap; **prerender is the real fix** — it's chipped, do it before expecting
   ChatGPT/Perplexity to cite pathon.eu.
3. **The design being parked caps paid-channel ROI.** Ads → landing that the
   founder himself calls "AI-made" will convert below potential. Run ads anyway
   (message testing has value), but expect the real conversion lift when the
   design lands.
4. **Nothing beats the 30-owner list.** Every hour on channels before 10 demos
   are done is procrastination with extra steps.
