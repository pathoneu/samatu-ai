# Pathon — social + ads playbook (2026-07-06)

## 1. Facebook — the LT trades channel (priority #1)

**Setup (founder, 1 h):** FB Page "Pathon" — orange-on-graphite avatar (reuse
og-image crop), CTA button → pathon.eu/register, apie = the one pitch.

**Groups — existence verified 2026-07-06** via search index (FB is
login-walled: **member counts + pinned rules could NOT be verified — founder:
15-min logged-in pass to fill counts and read rules before posting**):
- Statybininkai (facebook.com/groups/statybininkai) — public; self-described
  skelbimų group (paslaugos / darbas / medžiagos) → business posts explicitly
  in-scope.
- Statyba ir remontas Lietuvoje | Patarimai • Klausimai
  (facebook.com/groups/statybairremontas) — public; homeowner Q&A ("kokios
  realios kainos darbų") — best fit for value-first posts; promo only per
  pinned rules.
- Statybininkai Lietuvoje (facebook.com/groups/632082554279860) — peer group
  for builders/meistrai ("dalinamės realiais objektais ir patirtimi") —
  closest ICP match.
- Statybos meistrai Vilniuje (facebook.com/groups/statybosmeistraivilniuje),
  Klaipėda - būsto statyba/remontas (facebook.com/groups/klaipedosmeistrai),
  Statyba, Remontas, Pardavimas, Konsultacijos (groups/1034245076637557) —
  public; indexed posts are contractor ads with phone numbers → promo
  tolerated.
- Also confirmed to exist (activity unverified): Statyba ir remontas. Pirk,
  parduok, diskutuok. (groups/175041472964038), Karkasinių namų statyba
  (groups/1391531297735974), Statybininkai konsultuoja
  (groups/statybininkaikonsultuoja — possibly private), Gerų meistrų kontaktai
  Šiaulių apskritis (groups/MeistruKontaktaiSiauliai), Statybininkai Vilniuje
  (groups/692430540888323).

Rules of engagement:
- **Value-first only.** Weekly post formats that survive admins:
  – "Kiek dažų reikia 20 m² kambariui? Formulė + lentelė" (from CLAUDE.md §1.10)
  – "5 klaidos, dėl kurių sąmata 'nesueina'" (§8)
  – prieš/po: ranka skaičiuota vs programa (screenshot, no link)
- Link ONLY in comments when asked, or in own-page reposts.
- Founder personal profile comments on sąmata questions daily (10 min) — the
  compounding asset is *the founder being the sąmatų guy* in these groups.
- 2 deleted posts in a group → switch that group to DM-only.

**Page cadence:** 2–3/wk — one value post, one product visual (creative briefs),
one engagement question ("Kiek laiko užtrunka jūsų sąmata?").

## 2. LinkedIn — founder build-in-public (priority #2)

2 posts/wk, LT, from the founder account (company pages are dead weight at this
stage). Working hooks:
- skaičiai: "Perleidau 6 realius projektus per programą. Štai kur ji klydo."
  (honesty = differentiation; matches the confidence-flag brand)
- rinka: "Sąmatininkas kainuoja €200–500/projektą. Paskaičiavau, kiek LT
  statybininkai išleidžia per metus."
- kelias: "Ką išmokau X" founder-journey posts.
Target follows: LT statybos įmonių vadovai, NT vystytojai, architektai.

## 3. YouTube — the searchable library (priority #3)

Channel = tutorial home (video briefs #1, #5 first). Titles match queries:
"Kaip paruošti statybos sąmatą iš PDF per 15 minučių", "Kiekių žiniaraštis:
nuo brėžinio iki Excel". Shorts = cut-downs of demos. Embed hero video on Landing
(also a dwell-time win).

## 4. TikTok / IG Reels — experiment tier (only if it's fun)

The flood-fill zone-painting animation is genuinely satisfying content (brief #2).
2/wk for 4 weeks → keep only if any video >5k views. Don't force it.

## 5. Google Ads (from week 2, €10–15/day)

**Structure:** 1 campaign (LT geo, LT language, search only, no partners) → 3 ad groups:

| Ad group | Keywords (exact/phrase) | Angle |
|---|---|---|
| Programa | [sąmatų programa], [sąmatos programa], [sąmatų skaičiavimo programa], "statybos sąmatos programa" | tool-seekers |
| Paslauga-steal | [sąmatininko paslaugos], [sąmatininkas kaina], "sąmatos paruošimas" | price-anchor: "€12 vs €300" |
| Kiekiai | [kiekių žiniaraštis], "kiekiai iš brėžinių", [kiekių skaičiavimas] | exact-fit |

**RSA copy (LT — founder polishes!):**
- Antraštės: "Sąmata iš PDF per kelias minutes" · "Kiekiai iš brėžinio — automatiškai" ·
  "Nuo €12 už projektą" · "Be sąmatininko — pats per vakarą" · "Kiekių žiniaraštis + PVM" ·
  "Eksportas į Excel ir PDF"
- Aprašymai: "Įkelkite brėžinį — gaukite kiekius ir sąmatą LT formatu. Kainas
  suvedate patys. Pirmas projektas įmonei nemokamas." · "Tas pats darbas, už kurį
  dabar mokate €200–500. Patikrinkite pažymėtas vietas ir eksportuokite."
- Negatives (start): darbas, atlyginimas, kursai, mokymai, nemokama programa
  skachat, minecraft (yes, really), vertimas.

**Conversions:** GA4 `sign_up` event (trackEvent helper is wired; add the call in
Register success handler — 1-line task) → import into Google Ads. Until the GA4
property exists, ads run blind — set it up FIRST.
**Expectations (verified 2026-07-06):** LT all-industry avg CPC ≈ €0.45
(seorocket.lt/google-ads-kaina/, pub. 2026-01-03); LT B2B services €0.80–3.00
(onlymedia.lt/kiek-kainuoja-google-reklama/). Plan €0.4–1.5 as the central
range with up to €2–3 on the most commercial terms if an incumbent bids —
astera.lt already runs ads on [sąmatų programa] (live SERP, 2026-07-06).
Volumes: genuinely tiny and not publicly verifiable — no free tool exposes LT
numbers (checked Ahrefs/KeywordTool/Ubersuggest/WordStream); pull real ranges
from Keyword Planner once the Ads account exists. **LSV risk is real:** narrow
terms ("kiekių žiniaraštis", "kiekių skaičiavimas") may sit "Low search
volume"-inactive until traffic picks up — auto-rechecked ~weekly, harmless to
leave in (support.google.com/google-ads/answer/2616014); prefer phrase over
exact-only match and group inflection variants. At €10–15/day, impressions —
not budget — will be the binding constraint; expect unspent budget. Treat as
lead trickle + message lab. Kill rule: €150 spend / 0 registrations per ad
group.

## 6. Meta ads (week ~6+, after pixel data)

- Phase A: retargeting only (site visitors 30 d) — €5–10/d, creative = 15 s demo
  video + "pirmas projektas nemokamas" static. Requires Consent Mode marketing
  category (already wired in analytics.js) + Meta pixel install (small task).
  **EU reality (verified 2026-07-06):** the pixel may fire only after explicit
  CMP consent — DPA fines land on the advertiser, €15M precedent
  (secureprivacy.ai/blog/meta-consent-mode-explained-2025); and since Jan 2026
  EU users get a DMA choice screen — anyone choosing "less personalised ads"
  silently drops out of the retargeting pool
  (digital-markets-act.ec.europa.eu, Meta commitments 2025-12-08). Advantage+
  audience is the default but not forced — use "Switch to original audience
  options" at ad-set level for tight retargeting.
- Phase B (only if retargeting converts): interest prospecting. **Verified
  2026-07-06:** "Small Business Owners" (interest) and "Business/Facebook Page
  Admins" (behavior) still exist and remain the standard SMB-owner proxy
  (adlibrary.com/posts/detailed-targeting, 2026). Whether "Construction" /
  "Renovation" survive as named interests is NOT publicly listed — Meta's June
  2025 consolidation wave deprecated thousands of interests (delivery stopped
  2026-01-15, no published list); type them into Ads Manager's audience
  builder and check for deprecation flags before writing Phase B copy. Note:
  detailed-targeting *exclusions* are gone (since 2025-03-31), and on
  conversion goals interest stacks are a suggestion Meta can expand beyond,
  not a hard constraint. Lookalikes: "≥1k events" was wrong — the hard minimum
  is 100 people from one country, 1k–5k only recommended
  (blog.adnabu.com/facebook/facebook-lookalike-audiences/) — reachable in LT
  sooner than assumed, but still only after retargeting proves out.

## 7. Weekly rhythm (founder, ~4 h/wk total)

Mon: check GA4/GSC/ads 15 min, kill/scale per rules · Tue: FB value post ·
Wed: LinkedIn post · Thu: group comments + DMs · Fri: LinkedIn #2 or video work.
Everything else is demo calls.
