# Contractor vs App reconciliation + fix plan (2026-06-17)

Rangovas A/Beržų g.24 contractor samata (53 lines, 50,328.67 € su PVM) vs app extraction (project 1fc49edf, 66 poz., Opus 4.8). Careful per-line categorization (4-agent workflow + chairman). Full detail: workflow wl52wmj1d.

## Headline counts (of 53 contractor lines)
- ✅ **16 MATCH** (≤10%) — trustworthy
- 🔻 **9 UNDER** (>10% low) — ALL trace to known frozen/recall gaps; **zero new defects**
- 🔼 **2 OVER** (minor: epoxy-miter +15%, tile aggregate +12%)
- 🧩 **~10 BUNDLED** — app splits/merges differently (tile 3-way, GKP material breakdown, maišytuvai pot/virš). NOT gaps.
- ❌ **12 MISSING** scopes — real reader holes
- ➕ **a separate set of app-INVENTED lines with NO contractor counterpart** ← the real problem

## ⚠️ The #1 finding: OVER-billing, not under-billing
The app invents scope the contractor never quoted, and presents it with 🟢/🟡 confidence:
- 🔴🔴 **Whole flooring stack** — parketas/laminatas 123 m² + išlyginamasis 155 m² + pamušalas 123 m² + slenksniai 10 vnt. **Contractor samata has ZERO flooring.** Biggest invented € block.
- 🔴 **Lubų karnizas** (ceiling cornice) 118.66 m × 2 lines — no contractor counterpart.
- 🟠 **Grindjuostės** 107.67 m vs contractor's 22.72 m — **4.7× inflation** (app counts full perimeter; contractor only tile-plinth).
- 🟡 Pastoliai, statybvietės sutvarkymas (may double-count šiukšlių), apsauginės dangos, koregavimas catch-alls.

**Why this matters most:** under-billing loses margin; over-billing loses the customer's trust when the contractor disputes the sąmata. And these render GREEN — a disclosure failure. This directly drives the confidence-UX work: app-invented lines must read 🔴 "patikrinti — pridėta automatiškai", never green.

## The under-reads (all known, mostly frozen — no surprises)
paint virš-3m −27% (heights) · GKP virš-3m −19% (heights) · kampai −28% (FROZEN) · rotband −21% (FROZEN) · doors beapvadinės −48% (recall) · angokraščiai −23% (recall) · light fixtures 22 vs 38 (−42%, hard symbol count) · lentynėlės −20%.

## The 12 missing scopes (real holes, mostly cheap)
Santechnika long-tail (bide #45/46, vonios maišytuvas #38/39, lauko čiaupas #37, džiovyklė #51, maišytuvas pot/virš split #40-43) · magnetinė TRACK lighting #11/#21 · gipsiniai difūzoriai #9/#22 (emitter fired 0) · GKP dėžutės #4 · partition niches #5/#6 (hard) · GK katilinėje #8 · ortakių dėžutė #12 · angokraščių sandarinimas #13.

## FIX PLAN (ranked)

### TRACK 0 — Over-billing guardrails (DO FIRST, correctness > completeness)
- **0.1** Scope-confidence badge: any line with no provenance anchor in the source PDF (flooring, karnizas, apsauginės dangos, koregavimas) renders 🔴 "patikrinti — pridėta automatiškai", never 🟢. **S. Highest-trust, cheapest win.** (= the confidence-UX ask.)
- **0.2** Resolve grindjuostės scope (full-perimeter vs tile-plinth 22.72). S–M. Needs human GT.
- **0.3** Gate the flooring stack behind a "grindų danga įtraukta?" toggle (default OFF — canonical samata excludes it). M. Needs human GT.

### TRACK 1 — Recall fixes (line exists, low)
- **1.1** Beapvadinės doors recall (−48%, worst %; reader-recall not frozen). S–M.
- **1.2** Light-fixture count 22→38 (hard ceiling-symbol count; flag 🟡 till solved). M–L.
- **1.3** virš-3m height detection (feeds #2 + #17). M. Needs the 2.8/3.4 m tier boundary GT.
- **1.4** Angokraščių length recall (−23%; also feeds the new sandarinimas line). M.

### TRACK 2 — Missing-scope additions (deterministic cluster first)
- **2.1** Maišytuvas pot/virš split + bide pair (S — billing-convention doubling, counts exist; `vision_call.py` ~1785-1835).
- **2.2** Gipsiniai difūzoriai decoupled montav.+apdirb. (prompt mislabels as vėdinimo). S–M.
- **2.3** Angokraščių sandarinimas companion line (S, deterministic).
- **2.4** Lauko čiaupas + džiovyklė (S, baseline lines).
- **2.5** Magnetinė TRACK montav.+apdirb. (M, new symbol field; shares ceiling-count blocker → 🟡).
- **2.6** GKP dėžutės soffit steps (M, from height-tier boundary). **2.7** katilinė + ortakių dėžutė (S each). **2.8** partition niches (L — hard geometry, DEFER).

### TRACK 3 — FROZEN, leave alone
kampai (−28%, calibrated to N=1), rotband (0.30 proxy), silikonavimas. Re-fitting to this one contractor = the N=2 over-fit the culture forbids.

## Needs human ground truth before shipping
1. Is flooring ever in this contractor's scope? (0.3) 2. Grindjuostės full-perimeter or tile-only? (0.2) 3. Lubų karnizas real or phantom? (0.1) 4. The 2.8/3.4 m ceiling-tier boundary (1.3). 5. Diffuser 15 montav. vs 21 apdirb. asymmetry (even the oracle is inconsistent).

---

## ADDED FINDINGS (testing, 2026-06-17)

### 🔴 BUG: ceiling-height change does NOT recompute the displayed/exported quantities
`/api/recompute-quantities` (used by AssumptionsPanel / Prielaidos per-room height editor) recomputes each ROOM's paint fields from the new height (verified: Svetainė dazymo 167→173 m² at 3.8→4.0m) BUT returns the OLD `pozicijos` unchanged — it never rebuilds the aggregated paint lines (iki/virš-3m split, kampai). Verified: all rooms → 4.0m, paint iki/virš stayed 376.82/154.81 (the "iki 3m" line should collapse to ~0). **Changing ceiling height in Prielaidos has zero visible/exported effect.** HIGH priority.
- **Fix:** after `_apply_assumption_edits` recomputes the rooms, rebuild the geometry-derived pozicijos (paint iki/virš, kampai, angokraščiai, lubu karnizas, grindjuostės) from the recomputed rooms — preserving reader-derived lines (doors/fixtures) + manual overrides. File: `backend/api/recompute_quantities.py:recompute()`. (Mirror what `/recompute-interior` does, but targeted so reader lines survive.)

### Determinism (5 runs, voting on)
- **doors beapvadinės: STABLE 20.4 across runs** (the #1 voting fix worked — was the −61%↔−9% swing).
- paint_iki tight (372–377), led 38–48, kampai 356–377, **paint_virš still wobbles (138–207)** and angokraščiai bimodal — the height + opening-dim recall remain the unstable axes (known; not yet fixed).

---

## GROUND-TRUTH ANSWERS (founder, 2026-06-17) — TRACK 0 resolved
1. **Flooring** — contractor includes it on SOME projects (not this one). **Keep the line; do NOT gate/remove.** Flag 🟡 "įtraukiama ne visada — patikrinkite, ar šiame projekte yra rangovo apimtyje". (TRACK 0.3 toggle → dropped; flag-only.)
2. **Grindjuostės** — full perimeter EXCEPT door gaps + wet places. **The app already computes exactly this** (subtracts door widths, skips tile/wet + concrete rooms; verified on 1fc49edf: skalbykla/san/vonia/garažas = 0). **It is correct — over-billing flag REMOVED.** (TRACK 0.2 resolved: not a bug. The contractor's 22.72 m #35 is a different, tile-zone-only "supjovimas/suklijavimas" operation.)
3. **Lubų karnizas** — used to mount curtains; founder doubts it's always present. **Keep 🟡 "užuolaidoms — įrengiamas ne visada, patikrinkite".**

Net: only the flooring stack is genuinely "added but absent here", and it stays (flagged), since the contractor uses it elsewhere. Shipped in `confidence._OVERBILLING_RULES`.
