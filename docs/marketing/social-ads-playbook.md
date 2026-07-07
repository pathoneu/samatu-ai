# Pathon — social + ads playbook (2026-07-06)

## 1. Facebook — the LT trades channel (priority #1)

**Setup (founder, 1 h):** FB Page "Pathon" — orange-on-graphite avatar (reuse
og-image crop), CTA button → pathon.eu/register, apie = the one pitch.

**Groups** [VERIFY names/sizes before posting — search: "statybininkai",
"statybos darbai", "remontas ir statyba", "namų statyba ir renovacija",
"rangovai", "interjero įrengimas"]. Rules of engagement:
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
**Expectations [VERIFY]:** LT niche CPC ~€0.3–1.5; volumes tiny — treat as lead
trickle + message lab. Kill rule: €150 spend / 0 registrations per ad group.

## 6. Meta ads (week ~6+, after pixel data)

- Phase A: retargeting only (site visitors 30 d) — €5–10/d, creative = 15 s demo
  video + "pirmas projektas nemokamas" static. Requires Consent Mode marketing
  category (already wired in analytics.js) + Meta pixel install (small task).
- Phase B (only if retargeting converts): interest prospecting — įmonių
  savininkai + statyba/remontas interests [VERIFY current LT targeting options];
  lookalikes need ≥1k events — months away, ignore for now.

## 7. Weekly rhythm (founder, ~4 h/wk total)

Mon: check GA4/GSC/ads 15 min, kill/scale per rules · Tue: FB value post ·
Wed: LinkedIn post · Thu: group comments + DMs · Fri: LinkedIn #2 or video work.
Everything else is demo calls.
