# LLM Council — Sąmatų AI landing prompt for Claude Code

_Run: 2026-05-12 · Source artifacts: `/tmp/samatu-landing/samatu-ai/project/Sąmatų AI Landing.html`, `docs/superpowers/research/2026-05-11-samatu-design-prompt.md`, `docs/superpowers/research/2026-05-11-design-iteration-handoff.md`, `chat1.md`_

## The question

The owner has a landing page draft (`Sąmatų AI Landing.html`, ~1206 lines, single-file React + Tailwind + Babel via CDN, generated through claude.ai/design across two iterations). He wants a prompt to feed into Claude Code that:

- Pivots the hero animation from its current EUR climax (`14 359 €`) to a **kiekiai-first** climax — the AI extracts quantities, the contractor enters their own kainynas, prices are a downstream consequence.
- Makes the kainynas-input step explicit on the page (visible editable inputs that drive the totals live).
- Fixes 12 concrete bugs from the most recent code review (false privacy claim, validation-failing pavyzdys numbers, dead `tel:`/WhatsApp/email placeholders, "60 sekundžių" promise, missing `scroll-margin-top`, status-pill text not changing, "Rasta 11" vs 5 chips, `aria-hidden` on BigStatement, diacritic in `#sąmata`, non-clickable NETRUKUS tiles, missing meta/OG/favicon, waitlist inputs without labels).
- Makes the page feel distinctive and professional, not generic SaaS template, within constraints: light palette (`#f6f5f2` / `#2a6fb5`), native animations only, single-file React + Tailwind + Babel CDN, LT copy.

**Audience.** Practical LT contractor / samatininkas, mid-age, on a phone or laptop on the site. Pre-revenue beta — landing = recruitment funnel.

---

## Anonymization mapping

- **A** = First Principles Thinker
- **B** = Outsider
- **C** = Executor
- **D** = Contrarian
- **E** = Expansionist

---

## Advisor responses

### The Contrarian (Response D)

The single fatal flaw I'd bet money on: **the prompt asks Claude Code to fix a 12-item checklist on a CDN-Babel single-file HTML, and the model will dutifully patch all 12 — while regenerating the pavyzdys numbers from training-data intuition instead of running them through the actual `CLAUDE.md` validation formulas.** You'll trade an EUR-climax lie for a kiekiai-climax lie.

Concrete traps:

1. **"Kiekiai climax" with hallucinated kiekiai is worse than the EUR bug.** A 72 m² butas has *specific* believable ranges (perimeter ~34-40 m, walls 180-260 m², lubos ~72 m², langai 4-6 vnt.). The prompt must hard-code the example numbers.
2. **"Fix privacy microcopy" → model writes new false claim.** It'll replace "lieka tavo kompiuteryje" with "saugu" or "konfidencialu" — still misleading. Force exact wording.
3. **Single-file + Babel CDN + "make it distinctive" = gradient meshes, blob SVGs, 600-line Tailwind soup.** Cap it.
4. **No acceptance test.** Require literal grep/assertion at the end. PASS/FAIL.
5. **Dead `tel:`/WhatsApp** — the model will invent a number. Forbid placeholders explicitly.

Bet: without numeric pinning + final self-audit, you ship landing v3 with a *new* pavyzdys that fails validation #1 from §6.

### The First Principles Thinker (Response A)

You're solving the wrong problem.

The framing assumes the artifact in front of you (the HTML) is the unit of work. It isn't. The unit of work is **a single demonstrable claim a tired contractor believes in 8 seconds on a phone in a van.** Everything else is downstream.

"Pivot from EUR to kiekiai" is a correction, not a claim. "AI extracts quantities, you keep your prices" is a *mechanism*, not a promise. A samatininkas with 20 years of intuition does not wake up wanting a quantities extractor. He wakes up wanting: *the 3 hours I lose every Sunday counting rooms back.* Or: *not losing the job because I quoted slow.* Or: *not eating the €2k I missed on angokraščiai.*

**The first-principles question:** *What specific pain, in the contractor's own language, does this app remove on Monday morning — and what is the smallest piece of evidence on the page that proves we actually remove it?*

If the answer is "we don't know yet" — the right move isn't a Claude Code prompt. It's five 20-minute calls with beta candidates this week.

Fix the promise. Then prompt.

### The Expansionist (Response E)

The asymmetric upside is staring you in the face: **the landing IS the product's killer demo.** Every LT competitor's landing is a feature list with a CTA. None of them dare let a visitor *do the thing* before signing up.

Build the **"Bring Your Own Kainynas" sandbox** as the page's centerpiece:

1. Page loads with a pre-extracted real kiekių žiniaraštis already on screen (5-8 rows from a real PDF). The chips fill in one by one with subtle native CSS — *that's* the kiekiai climax.
2. Below it: an inline kainynas table the visitor types into. Default values are blank or greyed placeholders. As they type, the suma column animates up. No signup. No modal.
3. A small "Kopijuoti į Excel" button that actually works on the demo data.

This is the trust loop made tangible: **we do the boring counting, you own the pricing judgment.** A samatininkas can stress-test the whole value prop in 40 seconds on his phone. The thing he screenshots to his WhatsApp group.

Tell Claude Code: invest 60% of build effort in this one interaction. The sandbox is the moat.

### The Outsider (Response B)

I'm Vytas. 52. Truck smells like coffee and OSB. Phone in one hand.

First thing I see: "14 359 €". Then somebody tells me the AI didn't make that number — *I* made that number, because *I* typed in my own kainynas. So what did the AI do? I scroll up. "Kiekiai." Quantities. That's the boring part of my job. That's what my žmona's cousin Rasa does in Excel for €15/hr. You built a robot for that?

"60 sekundžių." Bullshit. Nothing on a statybų aikštelė takes 60 seconds. Close tab. Honestly.

The word "kiekiai" on a sales page — it sounds like accounting. Nobody in my trade wakes up thinking "I wish someone would extract my quantities faster." We wake up thinking "I lost another tender because my pasiūlymas was three days late and Marius from Kaunas got it in by Tuesday."

What makes me pause: a screenshot of a real Lithuanian PDF — with stamps, with brėžiniai — and next to it a clean list saying *miegamasis 14.2 m², lubos 2.65 m, 2 langai, 1 durys*. That I believe.

The climax shouldn't be a number. The climax should be: **"Tu turi pasiūlymą iki vakaro, ne iki ketvirtadienio."** You get the bid done tonight, not Thursday.

### The Executor (Response C)

Three structural elements I insist on:

**1. A "DO NOT TOUCH" allowlist at the top.** Literal list: keep `<style>` block intact except `.anim-status`; keep `Nav`, `Footer`, `Honesty`, `HowItWorks`, `UploadVignette`, `ExtractVignette` components untouched; keep all CSS tokens; keep CDN script tags.

**2. A numbered FIX TABLE with line anchors and exact replacement strings.** Twelve bugs, twelve rows: `{id, file_anchor, current_string, required_behavior, accept_test}`. For bug 1, give the *replacement* microcopy verbatim. Find-and-replace, not creative writing.

**3. A self-verification checklist with concrete greps the agent runs before declaring done.** `grep "14 359"` returns nothing, `grep "60 sekundži"` returns nothing, `grep "scroll-margin-top"` appears in CSS, etc. Plus one render check.

Cut: brand voice essays, palette philosophy, rationale for *why* the EUR-climax is wrong. The agent needs verbatim, not convincing. Smallest sharp version: allowlist + fix table + verify-greps.

---

## Peer review scoreboard

| Reviewer | Strongest | Biggest blind spot | What ALL missed |
|----------|-----------|---------------------|-----------------|
| 1 | **A** (First Principles) — only one refusing the premise | **E** (Expansionist) — sandbox inverts the funnel; asks Vytas to type prices before he trusts the tool | This is a recruitment funnel for beta, not conversion. A Calendly link probably beats any hero animation |
| 2 | **E** (Expansionist) — only one turning the "AI doesn't price" caveat into a feature | **C** (Executor) — assumes the right answer is known; treats this as refactor when the pivot itself isn't validated | Whether the owner has a real PDF + real extraction output. Per 2026-05-07 prod test, ceiling-height detection fails on real PDFs |
| 3 | **B** (Outsider) — only one speaking the customer's actual language; "kiekiai" itself is jargon | **E** (Expansionist) — ignores Babel CDN + single-file constraint; 60% effort on unproven interaction = opposite of pre-revenue discipline | Whether the hero animation should exist at all on mobile-in-van. Static screenshot + one sentence may outperform any animation |
| 4 | **D** (Contrarian) — only one engaging with the actual failure mode of running this prompt | **E** (Expansionist) — 2-week product feature, not a landing fix; silently rewrites the brief | None checked whether the file exists in the repo. A prompt that says "fix bug 9" is useless without the file pinned by path |
| 5 | **D** (Contrarian) — catches the hallucinated-numbers failure mode | **E** (Expansionist) — static sandbox with one žiniaraštis is a demo of a demo | Recruitment funnel framing; landing optimizes copy against guesses unless 5 contractor calls happen first |

**Tally — Strongest:** D (2), A/B/E (1 each), C (0).
**Tally — Biggest blind spot:** E (4), C (1).

---

## Chairman synthesis

### Where the council agrees

Four of five advisors converged independently:

1. The EUR climax must die, but its replacement cannot be hallucinated kiekiai. Contrarian, Outsider, and Executor all flag that "replace the lie with a fresher lie" is the default failure path. The new pavyzdys numbers must be **pinned in the prompt**, not invented by the model.
2. The current `ROWS` constant fails CLAUDE.md §6 validation. 148 m² lubos on a 72 m² butas isn't a typo — it's the model's training-data intuition leaking into a domain it doesn't know.
3. The medium constrains the message. Babel CDN + single-file HTML means anything fancier than restrained motion + Tailwind utilities balloons to unrunnable.
4. Discipline beats creativity. Three advisors want an allowlist, a fix table with exact strings, and a grep-based self-audit. None want a "make it distinctive" creative brief.

### Where the council clashes

- **Expansionist vs. everyone else.** Sandbox idea shot down by 4 reviewers: inverts the funnel, demands ground truth the project doesn't have (2026-05-07 prod test: ceiling-height fails on real PDFs), 60% effort on an unvalidated interaction violates pre-revenue discipline.
- **First Principles vs. tactical advisors.** First Principles refuses the premise: don't prompt until 5 calls happen. Reviewer 1 amplifies — this is a recruitment funnel, a Calendly link probably outperforms any animation. Tactical advisors implicitly accept the premise and optimize the artifact.
- **Outsider vs. Expansionist on jargon.** Outsider says "kiekiai" itself is insider accounting language; the climax must be a work-outcome ("pasiūlymą iki vakaro"). Outsider is right at the headline level — kiekiai are the *proof*, not the *promise*.

### Blind spots the council caught

- Nobody checked whether the file exists in the repo or what its git state is (Reviewer 4).
- Cherry-picked kiekiai is the same lie as the EUR climax — numbers must come from CLAUDE.md §6 *known-good* ranges, not from any specific real PDF (Reviewer 2).
- No advisor questioned whether the hero animation should exist on mobile (Reviewer 3).
- The phone/email placeholders trap — tell a model to "fix" a `tel:#` and it invents a number. Must be explicitly forbidden, placeholder shape stays placeholder.

### The recommendation

Ship the prompt with three guardrails the advisors agreed on. Ignore Expansionist's sandbox:

1. **Discipline over creativity.** Allowlist + exact-string fix table + grep self-audit. Find-and-replace, not creative latitude.
2. **Numbers come from the prompt, never from the model.** Hard-code a believable 72 m² butas ledger that passes §6.
3. **The new headline is a work-outcome.** "Pasiūlymą tu turi iki vakaro. Ne iki ketvirtadienio." Kiekiai ledger is supporting evidence.

Override the majority on one point: don't delay shipping until 5 contractor calls happen. A landing that *honestly* says "AI counts the boring stuff, you keep your prices" is defensible even pre-validation. The risk isn't shipping; it's shipping a *promise* (60 sekundžių, 14 359 €) the product can't keep. Strip the promises, keep the page, get the calls.

### The one thing to do first

Run `ls "Sąmatų AI Landing.html"` and `wc -l "Sąmatų AI Landing.html"` to confirm the file exists at the expected path with the expected line count (~1206) **before** pasting the prompt. If the file drifted, the line anchors are wrong and the agent will silently fail.

---

## The ready-to-paste Claude Code prompt

See `council-report-2026-05-12-landing-prompt.html` for the formatted version, or copy the block below directly into a Claude Code session.

````
Tu esi Claude Code, dirbi /Users/ignasgaldikas/samatu-ai repe.

Failas, su kuriuo dirbi:
  /Users/ignasgaldikas/samatu-ai/Sąmatų AI Landing.html
  (~1206 eilučių, single-file React + Tailwind + Babel via CDN)

==============================================================================
MISSION
==============================================================================

This is the pre-revenue beta landing page for Sąmatų AI — a Lithuanian
construction quantity-extraction app. The current draft has 12 concrete bugs
and one strategic miss: the hero animation climaxes on "14 359 €", but the
product does NOT compute prices. The contractor enters their own kainynas;
the app multiplies kiekiai × the user's kainos.

Your job: surgical find-and-replace. Not a rewrite. Not a redesign. Not
"make it pop." Preserve the existing structure, components, CSS tokens, and
visual rhythm. Fix the 12 named bugs verbatim. Pivot the hero from a euro
climax to a work-outcome climax with a quantity ledger underneath.

==============================================================================
BEFORE YOU TOUCH ANYTHING
==============================================================================

1. Run: ls -la "/Users/ignasgaldikas/samatu-ai/Sąmatų AI Landing.html"
2. Run: wc -l "/Users/ignasgaldikas/samatu-ai/Sąmatų AI Landing.html"
   Expected: ~1206 lines. If wildly different, STOP and report.
3. Run: git log -1 --oneline -- "Sąmatų AI Landing.html"
4. Read the file fully once before editing.

==============================================================================
DO NOT TOUCH
==============================================================================

Preserve unchanged unless explicitly listed in the FIX TABLE below:

  - <head> structure beyond the additions listed in BUG 11
  - All CDN <script> tags (React, ReactDOM, Babel, Tailwind). Do NOT add libs.
  - The <style> block — only modify the specific keyframes / rules named in
    the FIX TABLE; do not refactor, reorder, or "tidy" CSS.
  - Components: Nav, Footer, Honesty, HowItWorks, UploadVignette,
    ExtractVignette
  - Color tokens, font stacks, spacing scale, border-radius values

Do not introduce: new components beyond what's needed for the hero+pavyzdys
pivot, new dependencies, gradient meshes, blob SVGs, glassmorphism, or
any animation longer than 600ms or with more than 3 simultaneous transforms.

==============================================================================
HERO PIVOT — THE ONE CREATIVE INSTRUCTION
==============================================================================

The hero must climax on a WORK-OUTCOME line, not on an euro number, and not
on the word "kiekiai" by itself (insider accounting jargon).

New hero headline (replaces whatever is at the H1 level):

  Pasiūlymą tu turi iki vakaro.
  Ne iki ketvirtadienio.

New hero subhead (one line, ~16–18 words):

  Įkeli brėžinį PDF — gauni kambarius, plotus, perimetrus ir angas
  paruoštus sąmatai. Kainas suvedi tu.

Hero artifact (right side / under headline on mobile):
  A static, layered raster mimicking a Lithuanian aukšto planas — light
  paper background, thin black lines, room labels in IBM Plex Mono
  ("MIEGAMASIS 14,2 m²", "VIRTUVĖ 11,8 m²", "VONIA 4,6 m²"), a scale-bar
  element and a faint stamp shape in a corner. Use plain inline SVG.
  NO photo. NO 3D. NO neon.

  Floating measurement chips attach to walls/rooms one at a time with a
  restrained slide-and-fade (180–240ms each, staggered 350ms apart). Five
  chips total. Loop after a 4s rest. Respect prefers-reduced-motion.

Numbers use IBM Plex Mono. Add ONE <link> for it in <head> if not present.

==============================================================================
NEW ROWS CONSTANT — HARD-CODED, DO NOT RECOMPUTE
==============================================================================

The pavyzdys must pass CLAUDE.md §6 validation. Replace the existing ROWS
constant block (~lines 812–820) with EXACTLY:

const ROWS = [
  { kambarys: "Svetainė + virtuvė", plotas: 28.4, perimetras: 22.1, lubos: 2.65, langai: 2, durys: 1 },
  { kambarys: "Miegamasis",          plotas: 14.2, perimetras: 15.3, lubos: 2.65, langai: 1, durys: 1 },
  { kambarys: "Vaiko kambarys",      plotas: 11.8, perimetras: 13.8, lubos: 2.65, langai: 1, durys: 1 },
  { kambarys: "Vonia",                plotas:  4.6, perimetras:  8.8, lubos: 2.65, langai: 0, durys: 1 },
  { kambarys: "WC",                   plotas:  2.1, perimetras:  5.9, lubos: 2.65, langai: 0, durys: 1 },
  { kambarys: "Koridorius",           plotas: 10.9, perimetras: 14.4, lubos: 2.65, langai: 0, durys: 4 },
];

// Totals (displayed as summary row — do not recompute in JSX):
//   Plotas grindų:     72.0 m²
//   Perimetras viso:   80.3 m
//   Sienų plotas:     213.0 m²
//   Langai:             4 vnt.
//   Durys:              9 vnt.

Validation rationale (do not include in page, just verify):
  walls / floor = 213 / 72 = 2.96   → inside §6 range 2.5–4    ✓
  ceiling ≈ floor                    → 72 ≈ 72                  ✓
  langai 4 vnt. for 72 m² butas      → believable               ✓

==============================================================================
ESTIMATE PREVIEW — KAINYNAS INPUTS (LIGHTWEIGHT)
==============================================================================

Below the kiekiai ledger, make the kainynas step visible and explicit.
NOT a full sandbox. A small inline 4-row table with pre-filled defaults
the visitor can override:

  | Pozicija                | Kiekis      | €/vnt. (tavo) | Suma €     |
  |-------------------------|-------------|---------------|------------|
  | Dažomas sienų plotas    | 213.0 m²    | [12.00]       | 2 556.00   |
  | Lubų dažymas             |  72.0 m²    | [10.00]       |   720.00   |
  | Grindų danga             |  72.0 m²    | [28.00]       | 2 016.00   |
  | Vidaus durys (montavimas)|   5 vnt.    | [85.00]       |   425.00   |

  Viso (be PVM):                                            5 717.00 €
  PVM 21%:                                                  1 200.57 €
  Iš viso:                                                  6 917.57 €

The €/vnt. cells are <input type="number"> with greyed default values.
Suma and totals recompute live on change. Use a controlled React state,
no external lib. Above the table, ONE explanatory line:

  Kainas suvedi tu — tai tavo kainynas, ne mūsų. Mes pateikiame tik kiekius.

A small note under the table:

  Pavyzdys — 72 m² 3-kambarių butas. Tavo projekto sumos priklauso nuo
  tavo kainyno.

NO "Kopijuoti į Excel" button. NO download. NO email-gate.

==============================================================================
THE 12-BUG FIX TABLE
==============================================================================

For each bug: find the literal old_string and replace with new_string. If
old_string is not unique, add ~2 lines of surrounding context. Do NOT skip
a bug. Do NOT improvise replacements.

BUG 1 — Hero microcopy is a false privacy claim (~line 586)
old_string:
  Brėžinys lieka tavo kompiuteryje — neperduodamas tretiesiems
new_string:
  Brėžinį siunčiame į Anthropic Claude API skaičiavimui ir nesaugome jo
  serveryje po analizės

BUG 2 — ROWS pavyzdys numbers fail §6 validation (~lines 812–820)
Replace entire ROWS block per "NEW ROWS CONSTANT" section above.
Verify after edit:
  grep -n "148.6" "Sąmatų AI Landing.html"   → no matches
  grep -n "386.2" "Sąmatų AI Landing.html"   → no matches
  grep -n "14 359" "Sąmatų AI Landing.html"  → no matches

BUG 3 — Placeholder constants (~lines 269–272) + footer href
PHONE_TEL: leave shape as "+3706XXXXXXX" with TODO[owner] comment above.
WA_LINK: leave shape as "https://wa.me/3706XXXXXXX" with TODO comment.
EMAIL: use "mailto:solutions@pathon.eu" (real, from MEMORY.md).
Footer privacy link (~line 1141): href="#" → href="/privatumas"
DO NOT invent a real phone number. "6XXXXXXX" shape stays.

BUG 4 — BigStatement breaks "no time promises" rule (~line 1158)
old_string:  Brėžinys → kiekiai per 60 sekundžių
new_string:  Pasiūlymą tu turi iki vakaro. Ne iki ketvirtadienio.

BUG 5 — Sticky 64px nav overlaps anchored sections
Append inside the existing <style>:
  section[id] { scroll-margin-top: 80px; }

BUG 6 — .anim-status flips color but text doesn't change (~line 218–222)
Replace the static "AI analizuoja" span with two crossfading spans:
  "AI analizuoja…" and "Kiekiai paruošti". Add keyframes status-swap /
  status-swap-in that crossfade them in 4s loops. Disable both in
  prefers-reduced-motion (show only "Kiekiai paruošti"). Delete the old
  .anim-status keyframe and rule entirely.

BUG 7 — "Rasta brėžinyje 11" but only 5 chips (~line 432)
old_string:  Rasta brėžinyje 11
new_string:  Rasta brėžinyje 5

BUG 8 — BigStatement has aria-hidden on section root (~line 1161)
old_string:  <section aria-hidden="true"
new_string:  <section

BUG 9 — Lithuanian diacritic in id/href (~lines 580 and 830)
old_string:  href="#sąmata"        → new_string:  href="#samata"
old_string:  <section id="sąmata"  → new_string:  <section id="samata"

BUG 10 — MultiType tiles are non-clickable <div>s (~lines 643–660)
Convert each tile <div> to <button type="button">, keep className,
add disabled, aria-disabled="true", cursor-not-allowed (Tailwind),
onClick={() => {}}. Above the tiles, add ONE line:
  Šios sritys jau projektuojamos — pranešime, kai bus pasiekiamos.

BUG 11 — <head> missing meta description, OG tags, favicon
Inside <head>, after <title>, INSERT:
  <meta name="description" content="Sąmatų AI — iš PDF brėžinio gauk
    kambarius, plotus, perimetrus ir angas, paruoštus sąmatai. Kainas
    suvedi tu.">
  <meta property="og:title" content="Sąmatų AI — kiekiai iš brėžinio">
  <meta property="og:description" content="Įkeli PDF brėžinį — gauni
    kiekius, paruoštus sąmatai. Tavo kainynas, tavo pasiūlymas.">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="lt_LT">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg
    xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect
    width='32' height='32' rx='6' fill='%232a6fb5'/%3E%3Ctext x='16' y='22'
    text-anchor='middle' font-family='monospace' font-size='18'
    font-weight='600' fill='white'%3ES%3C/text%3E%3C/svg%3E">

BUG 12 — Waitlist inputs have placeholder but no label (~lines 1086–1089)
For each <input>, wrap with <label className="sr-only" htmlFor="wl-..."
matching id>. Add wl-name, wl-email, wl-company ids. If sr-only is not
defined in <style>, add it:
  .sr-only { position:absolute; width:1px; height:1px; padding:0;
    margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap;
    border:0; }

==============================================================================
THINGS YOU MUST NOT DO
==============================================================================

  - Do NOT invent a phone number, WhatsApp link, or email beyond what's
    specified above. Placeholder shape stays placeholder.
  - Do NOT add new dependencies, fonts beyond IBM Plex Mono, icon libs,
    or analytics snippets.
  - Do NOT regenerate or "improve" the ROWS numbers. They are pinned.
  - Do NOT introduce a sandbox where visitors upload PDFs from the landing.
  - Do NOT add a "Kopijuoti į Excel" or "Atsisiųsti pavyzdį" button.
  - Do NOT rewrite the Nav, Footer, Honesty, HowItWorks copy.
  - Do NOT add gradient meshes, blob SVGs, glass cards, or marquee text.
  - Do NOT exceed 600ms for any single animation.

==============================================================================
SELF-VERIFICATION CHECKLIST — RUN BEFORE DECLARING DONE
==============================================================================

cd /Users/ignasgaldikas/samatu-ai
F="Sąmatų AI Landing.html"

# 1. EUR climax is gone
grep -n "14 359" "$F"          # expect: no output
# 2. False privacy claim is gone
grep -n "lieka tavo kompiuteryje" "$F"   # expect: no output
# 3. 60 sekundžių promise is gone
grep -n "60 sekundži" "$F"     # expect: no output
# 4. New hero outcome line is present
grep -n "iki vakaro" "$F"      # expect: ≥1 match
grep -n "Ne iki ketvirtadienio" "$F"  # expect: ≥1 match
# 5. ROWS numbers are the new pinned set
grep -n "148.6" "$F"           # expect: no output
grep -n "386.2" "$F"           # expect: no output
grep -n "213.0" "$F"           # expect: ≥1 match
grep -n "72.0"  "$F"           # expect: ≥1 match
# 6. Truthful API microcopy is present
grep -n "Anthropic Claude API" "$F"   # expect: ≥1 match
# 7. Diacritic anchors are ASCII
grep -nE 'id="sąmata"|href="#sąmata"' "$F"  # expect: no output
grep -nE 'id="samata"|href="#samata"' "$F"  # expect: ≥2 matches
# 8. scroll-margin-top exists
grep -n "scroll-margin-top" "$F"   # expect: ≥1 match
# 9. No invented phone number — placeholder shape stays
grep -nE "tel:\+3706[0-9]{7}" "$F"   # expect: no output
grep -n "6XXXXXXX" "$F"               # expect: ≥1 match
# 10. <head> has description + OG
grep -n 'name="description"' "$F"   # expect: ≥1 match
grep -n 'property="og:title"' "$F"  # expect: ≥1 match
grep -n 'rel="icon"' "$F"           # expect: ≥1 match
# 11. Waitlist inputs have labels
grep -nE 'htmlFor="wl-' "$F"        # expect: ≥2 matches
# 12. MultiType tiles are buttons
grep -n 'aria-disabled="true"' "$F" # expect: ≥1 match
# 13. Chip count claim matches chip count
grep -n "Rasta brėžinyje 5" "$F"    # expect: ≥1 match
grep -n "Rasta brėžinyje 11" "$F"   # expect: no output
# 14. File still parses
wc -l "$F"                           # expect: within ±50 of original
# 15. CDN scripts still present
grep -nE 'react@|tailwindcss|@babel/standalone' "$F"  # expect: ≥3

==============================================================================
WHEN DONE
==============================================================================

Output, in order:
  1. A one-line summary of what changed.
  2. The output of every grep above.
  3. A list of any bug you could NOT fix and the reason. Do not silently skip.
  4. The first 25 lines of the new ROWS constant as rendered in the file.
  5. Open the file in a browser if possible (Playwright MCP is registered)
     and report: does the hero render, do the chips animate, does the
     kainynas table recompute on input change. If you cannot open it,
     say so — do not pretend you did.

No commit unless explicitly asked. End with: "Done — ready for review."
````
