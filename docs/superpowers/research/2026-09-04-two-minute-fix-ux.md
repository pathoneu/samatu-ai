# Fixing any miscount in under two minutes — measured friction + loop design

**Date:** 2026-09-04 · **Branch:** `viewer-rebuild` · **Scope:** UX/product only. No accuracy work, no paid extraction, no code changed.
**Measured on:** the 11-room interior dev project (`1fa0415d-…`, objektas_a shape: 11 patalpos, 118 pozicijos, 17-page PDF), local dev servers, Chromium 1440×900, LT UI.

> **Premise (founder, 2026-09-04):** on the contractor's own projects the failures were *input-level* — wrong or missing room table, defaulted heights, wrong pages — not formula nuance. So the product question is not "how do we show the maths", it is **"how fast can he replace a wrong input and see the money move".**

---

## 0. Method

Every count below is exact (clicks, keystrokes, screen switches, DOM state before/after). Seconds are **derived**, not stopwatch-on-a-human, from a stated model — so the ratios are trustworthy and the absolutes are indicative:

| Unit | Cost |
|---|---|
| pointer move + click | 1,2 s |
| keystroke | 0,3 s |
| tab / panel switch incl. repaint | 1,5 s |
| find a control inside a labelled grid of ≤ 12 | 3 s |
| find a row inside the 118-row Kiekiai table | 12 s (measured: 85 px/row × 118 ≈ 10 000 px of scroll) |
| read one Patikra card | 3 s |

Machine latency **is** measured and is not the problem: `POST /api/recompute-quantities` **42–45 ms** (n = 5), project save 33–36 ms, `AssumptionsPanel` debounce **400 ms** (`AssumptionsPanel.jsx:14`). A full rebuild of 118 rows is under half a second. **Every second in the tables below is human navigation, not compute.**

---

## 1. Measured friction — the eight scenarios

| # | Scenario | Path that exists today | Clicks | Keys | Screens | ≈ Time | Propagates? | Survives recompute? |
|---|---|---|---|---|---|---|---|---|
| **a** | A room's **AREA** is wrong | **none** | — | — | — | **∞** | — | — |
| **b** | Ceiling height wrong for **3 rooms** | Prielaidos → per-room height grid → Kiekiai to look | 3 | 13 | 2 | **~15 s** | ✅ 3 recomputes, 42–45 ms each | ✅ |
| **c** | One room's walls are **tiled, not painted** | **none** (only „dažoma / nedažoma", which removes paint and adds nothing) | 1 | 0 | 1 | partial only | ✅ removes paint | ✅ |
| **d** | A quantity is simply wrong — type his own number | Kiekiai table → click the number → type → Enter | 2 | 8 | 1 | **~18 s** (7 s if the row happens to be the top Patikra card) | n/a (leaf) | ✅ **verified twice** |
| **e** | A whole **family is missing** — add rows | „Pridėti eilutę" per section | 6/row | ~30/row | 1 | **~24 s per row**; a 5-row family ≈ **2 min** | ✅ | ⚠️ survives but is badged **„pasenusi eilutė"** |
| **f** | Doors/windows miscounted **in a room** | **none per room** (Langai/Durys are one project-wide list of plotis × aukštis, no room) | — | — | — | **∞** | — | — |
| **g** | **4 rooms** wrong because the room table was misread | **none** (= a × 4) | — | — | — | **∞** | — | — |
| **h** | A room is **missing** / a **phantom** room exists | **none** | — | — | — | **∞** | — | — |

### 1.1 Detail on what was actually observed

**(a)(g)(h) — the room-table editor exists and is 100 % unreachable.**
`RoomsGrid.jsx` + `RoomCard.jsx` edit `plotas_m2`, `perimetras_m`, `lubu_aukstis_m`, `paskirtis`, add a room (`RoomsGrid.jsx:132`) and remove one, with source badges and a jump-to-page — and they are wired to `handleRoomsChange` → `POST /recompute-interior` (`InteriorProject.jsx:817`), which is live. They are rendered **only** inside `{tab === 'kiekiai'}` (`InteriorProject.jsx:1093`, `:1362`), and `kiekiai` is **not in the TabBar** — the bar lists `brezinys · main · aichat` only (`InteriorProject.jsx:234`), the initial state is `'brezinys'` (`:646`) and **no `setTab('kiekiai')` call exists anywhere in the codebase**. There is no URL parameter either. So the single most valuable correction surface in the product is dead code that still compiles.
The two live producers of `/recompute-interior` are `projectStore.updateRoomPolygon` (a zone redraw) and `markRoomVerified` (the confidence badge) — **neither changes an area or a perimeter**.

**(a) — the nearest thing, „Taisyti zoną", explicitly refuses to fix the area.** Focus a room in the Patalpos list → the toolbar grows „Taisyti zoną" → click inside the room → the outline is re-traced by `POST /api/click-to-fill`. The success toast says so out loud (`TakeoffViewer.jsx:751`): *„Plotas ir kiekiai lieka iš eksplikacijos — kontūro pataisymas naudojamas žymėjimui ir tikslumo mokymui."* Correct and honest — and it means a contractor who redraws a zone *because the area looked wrong* has spent 4 clicks on nothing.
(Also: at 1440 px that button **overflows and is clipped** by the toolbar — see `ux-13-room-focus.png`.)

**(b) — the fastest real path in the product, and still blind.** One click opens Prielaidos; the 11 per-room height inputs are a 3-column grid; **Tab moves to the next room and selects the value** (browser default), so keyboard entry is efficient. Two defects:
1. **Clicking** into a field does *not* select its content — typing `3,2` into a field holding `2,8` produced **`3,22,8`** (reproduced). A mouse user must Cmd+A or backspace first. This affects every numeric field in the app, including the Kiekiai quantity editor.
2. **Zero feedback.** After three height edits the panel is visually identical (`ux-03-after-height-edit.png`). The panel's own intro says the quantities recompute *„dešinėje"* — but Prielaidos is a **full-screen takeover**, there is nothing on the right, and the drawing is gone. He must switch to Kiekiai and compare against numbers he never memorised. (The effect was real: `sienos iki 3 m` 253,20 → 139,80 m², `virš 3 m` 155,39 → 271,80 m², `kampai` 423,60 → 432,00 m — a swing worth hundreds of euro, announced by nothing.)

**(d) — works well, and is the one place the product is already good.** The override shows `140 · RANK. · AI: 123,48` and survived two independent recomputes (assumption edit and Q-level change). Both merge layers protect it (`mergeDarbuSarasas.js:260`, `api/recompute_quantities.py:711`). In the Patikra card the same fix is **1 click + Cmd+A + type + Enter, and the card auto-advances** — measured. There is, however, **no way back**: no "restore the AI value" control exists on the `RANK.` badge.

**(e) — the added row is immediately called stale.** „Pridėti eilutę" appends `Nauja eilutė · m² · 0` at the **bottom of the section**, numbered 119, **without focus or scroll-into-view**. It survives a recompute — but comes back badged **„pasenusi eilutė" + „Šalinti"** (`ProjectMainView.jsx:318`), with the toast *„senesnės sąmatos eilutės nebeatnaujinamos…"*. Cause: `mergeDarbuSarasas.js:375` sets `_orphaned_after_rebuild` on every carried unmatched row with no exemption for the `rnk-…` hand-added ids that `darbuRows.js:47` mints precisely to identify them. **The app tells the contractor his own 30-second-old row is obsolete.**

### 1.2 The finding that dominates everything: **a recompute erases every „Teisinga ✓"**

Reproduced twice, deterministically:

```
liko 72  →  „Teisinga" ×7        →  liko 65
         →  ONE Prielaidos click (Q lygis Q2→Q3)
         →  liko 71     (6 of 7 verifications destroyed)
```

Checkmarks are durable across a **page reload** (68 → reload → 68), so this is not state loss. `isRowVerified` (`lib/takeoffWorkflow.js:167`) reads `user_verified_at` and `_review_status` — and **neither field is in either merge carry-set**: `api/recompute_quantities.py:1115 _CARRY_KEYS` and `lib/mergeDarbuSarasas.js:260 carry()` both carry money, quantity overrides and price provenance, and drop verification.

The consequence is not a cosmetic bug. It makes the contractor's natural order — *check a few, notice something wrong, fix it, carry on* — **self-destructive**. Fixing an input punishes him for having verified. Any "two-minute loop" that interleaves verification and correction is impossible until this is fixed; it is prerequisite #1.

### 1.3 Other measured friction

| Observation | Evidence |
|---|---|
| First run puts **two blocking modals** on screen at once (cookie banner + a 3-step, ~90-word wizard). **4 clicks and ~250 words before he can touch anything.** | `ux-01-first-screen.png` |
| The viewer opens on **page 1 = the marketing cover render**, not on a plan. Scale there reads „nekalibruotas"; on the plan page it auto-seeds „~1:109 (automatinis)". | `ux-01`, `ux-09-plan-page2.png` |
| The €-risk queue **leads with un-fixable rows.** The top 5 cards were all material lines whose only verb is „Pataisyti kiekį" and whose hint is a generic *„palyginkite su gamintojo nurodytomis sąnaudomis"*. The first card with a real input fix („Pataisyti aukštį") was **#6**. | measured walk of the queue |
| The **„SUVESKITE PATYS (12)"** list — the rows the AI honestly could not count — is **read-only**. `onAccept={null} onReject={null}` (`ReviewQueueSidebar.jsx:430`); clicking a row does not take the card; the detail panel it opens has no input (`RowDetailPanel.jsx` — only *close* and *show drawing*). The 12 things he **must** supply are the 12 he cannot supply from there. | code + click test |
| „Kaip suskaičiuota" is a **full-height overlay that covers the top bar** — with it open, the Prielaidos button is unclickable (Playwright refused: *"intercepts pointer events"*). | measured |
| The ledger for material rows leaks a raw internal key to the user: *„Šaltinis: **medziagu_norma**."* | `ux-10-ledger.png` |
| One height edit writes **3 rows to `corrections`** (one per intermediate valid keystroke). 4 real decisions produced 20 correction rows, and „Mokymosi žurnalas" counts them. The learning counter counts keystrokes, not decisions. | DB: 20 rows |
| **Two parallel review systems.** The Patikra rail (Brėžinys tab) says `72`; the „PATIKROS REŽIMAS · LIKO 85" strip inside the Kiekiai tab says `85`, with its own „Pataisyti / Patvirtinti" verbs. Same job, different counts, different gestures. | `ux-04-kiekiai.png`, `ux-06-patikra-rail.png` |
| No keyboard anywhere in Patikra. Only `Enter`/`Escape` inside the quantity input (`PatikraCard.jsx:141`). „Teisinga" is mouse-only; 72 rows = 72 clicks. | code |
| Undo exists **only** for row delete (6 s). No undo for an assumption change, a quantity override, or a room edit — even though `corrections` stores old and new values. | code |

### 1.4 What is genuinely good today (build on these, don't rewrite them)

- **The deep-link works.** „Pataisyti aukštį" on a card → Prielaidos opens, scrolls to and focuses **exactly** `lubu_auksciai:110`. One click, right control. (It just lands with no drawing and no highlight beyond the browser focus ring.)
- **The ledger is right.** For paint the „Kaip suskaičiuota" panel shows `Σ 6 patalpų (virš 3 m) 333,55 m²`, every contributing room with its m² and page link, **and** `NEĮTRAUKTA (3)` with reasons (*„Šios patalpos sienos nedažomos"*). This is the derivation-before-checkmark the research called for, and it is built. (`ux-11-ledger-paint.png`)
- **The sensitivity hint is the right idea:** *„Jautriausia vieta: lubų aukštis patalpoje 102 — 3,40 m (skaityta iš brėžinio). Ši patalpa sudaro 31 % visos eilutės."*
- **The ripple is half-built:** „Pataisyta: Lubų aukštis · 110 / Perskaičiuota: 11 eilučių / ◉ Įsiminta mokymui".
- **Room focus works:** click a room → the drawing jumps to its page and draws a red ring on its printed number with a `50,5 m²` chip.
- **Manual quantity provenance is exemplary:** `140 · RANK. · AI: 123,48`.
- **Auto scale.** On plan pages the page scale seeds itself (`~1:109 automatinis`), so measuring works with no calibration step.

---

## 2. Input coverage — what can be fixed with a live recompute today

| Input | Fix surface | Endpoint | Live? | File |
|---|---|---|---|---|
| Lubų aukštis, per room + „visiems" | Prielaidos grid | `/api/recompute-quantities` | ✅ | `AssumptionsPanel.jsx:560–630` |
| Sienos dažomos / nedažomos, per room | Prielaidos toggles | same | ✅ | `AssumptionsPanel.jsx:647–670` |
| Įtempiamos lubos, per room | Prielaidos toggles | same | ✅ | `AssumptionsPanel.jsx:688–710` |
| Glaistymo lygis Q1–Q4 (project) | Prielaidos | same | ✅ | `AssumptionsPanel.jsx:495` |
| Potinkiniai / virštinkiniai maišytuvai | Prielaidos | same | ✅ | `AssumptionsPanel.jsx:526` |
| Sienos storis | Prielaidos | same | ✅ (self-described as *not changing quantities*) | `AssumptionsPanel.jsx:478` |
| Langai / durys — **sizes**, project-wide list | Prielaidos | `custom_windows` / `custom_doors` | ✅ | `AssumptionsPanel.jsx:746, :773` |
| One position's **quantity** | inline Kiekiai edit, or Patikra „Pataisyti kiekį" | client-side + `manual_override` | ✅ | `lib/quantityOverride.js:1` |
| Add / delete a **row** | „Pridėti eilutę", trash + 6 s undo | client-side | ✅ (mislabelled „pasenusi") | `ProjectMainView.jsx:661, :677` |
| Room **outline** | „Taisyti zoną" | `/api/click-to-fill` | ✅ **marking only — area unchanged by design** | `TakeoffViewer.jsx:740–755` |
| Room **plotas / perimetras / paskirtis** | `RoomsGrid`/`RoomCard` | `/recompute-interior` | ❌ **unreachable** (dead tab) | `RoomsGrid.jsx`, `RoomCard.jsx`, `InteriorProject.jsx:1093` |
| **Add / remove a room** | `RoomsGrid.jsx:132` | `/recompute-interior` | ❌ unreachable | same |
| **Openings per room** (count) | — | — | ❌ **does not exist** | would need `AssumptionsPanel.jsx` + `_ASSUMPTION_FIELDS` (`api/recompute_quantities.py:58`) |
| **Wall finish = tiles** per room (vs simply "unpainted") | — | — | ❌ does not exist in UI; the engine has the hooks (`walls_paint_factor_override`, `plyteliu_aukstis`, `extractor/tile_calculator.py:153`) | `AssumptionsPanel.jsx` |
| **Floor finish** per room | — | — | ❌ does not exist | `AssumptionsPanel.jsx` / room grid |
| **A measured area/perimeter → a room** | — | — | ❌ measurements are display-only. Only *counts* have „Į sąmatą" (`WorkspacePanel.jsx:260`); geometry rows have no verb at all (`WorkspacePanel.jsx:678`) | `MeasureLayer.jsx`, `WorkspacePanel.jsx` |
| A row's **verification state** across a recompute | — | — | ❌ **silently destroyed** | `api/recompute_quantities.py:1115`, `lib/mergeDarbuSarasas.js:260` |

**The shape of the gap:** everything that is *per-position* is fixable; almost everything that is *per-room* is not. And the founder's report says the failures were per-room.

The data for the missing surface is already persisted on every room: `plotas_m2` + `plotas_saltinis` + `eksplikacija_row_idx`, `perimetras_m`, `lubu_aukstis_m` + `lubu_aukstis_saltinis`, `marker_pct`, `polygon_pct`, `puslapio_nr`, `paskirtis`, `plyteles_sienos_m2`, `plyteliu_aukstis_m`, `windows_deducted_m2`, `doors_deducted_m2` — plus `_eksplikacija.patalpos[]` with `plotas_m2_raw`, `row_idx` and `page`. **Nothing new has to be extracted to build the screen in §3.**

---

## 3. The two-minute loop

### 3.0 The one structural decision: **verify rooms, not rows**

Today the queue is 72 rows. Eleven rooms produce them. A contractor cannot check 72 arithmetic results against a drawing, but he can check **11 rooms** — that is exactly how he reads a plan. At ~8 s per room card, 11 rooms is **90 seconds**. 72 rows at 1 click each is 1,5 min of rubber-stamping over a surface with a measured 50–60 % false-green rate (`extractor/confidence.py:1`).

So: **a row inherits its verification from the rooms that contribute to it** — the ledger already knows exactly which rooms those are (`contributions[]`, `excluded[]`). Rows with no room (materials derived from a norm) inherit from their parent work row. Rows the builder could not compute do not get verified at all; they go to an explicit *"you must fill these"* list.

This is not a new surface. It is `ReviewQueueSidebar` + `PatikraCard` with the unit of audit changed from position to room — which is Option C of the transparency research, folded into the Patikra loop the founder already approved.

### 3.1 First 30 seconds after extraction

What he should see, in order:

1. **The plan, not the cover.** Open on `eksplikacija_source_page` (already stored) or the first page classified as a plan.
2. **One sentence of state, in money:** „Perskaičiau 17 psl. Radau 11 patalpų, 165,64 m². Paruošiau 118 eilučių."
3. **One call to action:**
   > **Patikrinkime pagrindus**
   > Prieš skaičiuojant kainas — patvirtinkite patalpas. Nuo jų priklauso apie 80 % sąmatos. Užtruks ~1 min.
   > `[ Patikrinti patalpas (11) ]`  `[ Praleisti — rodyti kiekius ]`
4. **No onboarding wizard, no cookie banner on top of it.** (Cookie consent belongs on first app entry, not on top of a project.)

**Before or after the numbers?** — **Before**, with a one-click escape. Three reasons, one of them measured:
- **Measured:** §1.2. If he verifies first and fixes second, the fix erases the verification. Ordering the inputs first is the only sequence the current data model survives — and it stays the better sequence after that bug is fixed, because the ripple then has nothing to ripple over.
- Numbers anchor. Once „423,60 m" is on screen he audits *that number* rather than the height that produced it.
- The wait is free. `NewProject` already tells him *„Analizė trunka iki 30 min."* The room table is known long before the last page is read; the confirm step is the obvious use of dead time.

**The honest counter-argument, and the mitigation:** a contractor with no numbers yet has no reason to care about `perimetras`. So the step must (a) be one screen, not a wizard, (b) show what each input controls in his language — „šis aukštis nustato sienų dažymo plotą", (c) be pre-filled and skippable, and (d) be the *same screen* he returns to later from any „Pataisyti". One component, two entry points — never a parallel surface.

### 3.2 Screen 1 — „Patalpos": the grid beside the drawing

Left 60 %: the plan, on the eksplikacija page, room zones on. Right 40 %: an editable grid, one row per room. Focus a row → the drawing rings that room **and** highlights the eksplikacija row it came from (we store `eksplikacija_row_idx`).

```
PATALPOS                                    11 patalpų · 165,64 m²
Nr   Patalpa            Plotas  Perim.  Aukštis  Sienos      Lubos      Grindys
101  Tambūras           11,01   13,5    3,10     dažomos     dažomos    plytelės
     iš eksplikacijos            prielaida  iš brėžinio
102  Svetainė/virtuvė   50,54   31,5    3,40     dažomos     dažomos    parketas
103  Koridorius          9,64   18,0    2,90     dažomos     dažomos    parketas
…
                                              [+ Pridėti patalpą]
Visoms patalpoms:  aukštis [    ] m   ·   sienos [dažomos ▾]   ·   grindys [parketas ▾]

Enter — kita patalpa · Tab — kitas laukas · M — išmatuoti brėžinyje · Del — šalinti patalpą
                                                     [ Patvirtinu patalpas (11) ]
```

Column rules, all of them derived from what broke:
- **Every cell carries its source under it**, in the existing vocabulary: `iš eksplikacijos` · `iš brėžinio` · `prielaida`. A `prielaida` cell is visually lighter — it is the one he is being asked to look at.
- **Sienos** is a three-state picker, not a checkbox: `dažomos` / `plytelės iki [2,0] m` / `neliečiamos`. This is scenario (c), and the engine already accepts it (`walls_paint_factor_override`, `plyteliu_aukstis`).
- **Lubos**: `dažomos` / `įtempiamos` / `GKP` (the first two ship already).
- **Grindys**: the room's floor finish, which today has no control at all.
- **Langai / durys** as two extra narrow count columns (`n` per room) — scenario (f). Persist `n_windows` / `n_doors` per room; the builder already computes them and throws them away (`vision_call.py:937`).
- **A cell the extractor could not read renders empty with a placeholder „Neradau — įrašykite"**, not a silently defaulted number. This is the single most important honesty change on the screen: today a defaulted 2,80 m looks identical to a read 2,80 m unless you hover.
- **Add / remove a room** on the grid — scenarios (h).
- **Bulk row at the bottom** — scenario (g) and „visos lubos 3,0 m" in one gesture.

Keyboard: `Tab` next field (select-on-focus), `Enter` next room, `↑ ↓` move, typing replaces, `M` arms the measure tool for the focused cell, `Cmd+Z` undoes the last cell.

Commit: **„Patvirtinu patalpas (11)"** stamps `user_verified` on all 11 rooms (this is also the ground-truth harvest — `scripts/build_ground_truth.py` reads exactly these), then reveals the quantities.

### 3.3 Screen 2 — measure-to-fix (the "two clicks on the plan")

Scale is already auto-seeded on plan pages, so no calibration step. Press `3` (Plotas) or `M` from a grid cell, trace the room, close the outline. The result chip that appears over the shape gains a verb:

```
   48,72 m²
   [ Naudoti kaip „104 Darbo kambarys" plotą ]   [ Tik matavimas ]
```

Apply → `plotas_m2` on that room → `/recompute-interior` (already live) → the ripple bar. Same for `Perimetras` → `perimetras_m`. Nothing new in the geometry engine; `MeasureLayer` needs to know the focused room and the Matavimai list needs the apply verb it already has for counts (`WorkspacePanel.jsx:260`).

This is the answer to (a) and (g) for the case where the eksplikacija is *absent or wrong* rather than merely mistyped.

### 3.4 Screen 3 — Patikra, room-first

Same rail, same verbs, unit changed:

```
PATIKRA                                    Patikrinta 3 iš 11 patalpų · 41 % vertės

  102  Svetainė/virtuvė                                       1 240 €  (24 %)
  50,54 m² · 31,5 m · 3,40 m · sienos dažomos · lubos dažomos
  ⚠ Ką patikrinti: aukštis 3,40 m nuskaitytas iš brėžinio. Ši patalpa duoda
    31 % visos „Sienų glaistymas/dažymas (virš 3m)" eilutės.
  [ Viskas teisinga ✓ ]   [ Taisyti ]   [ Rodyti brėžinyje ]
  18 eilučių iš šios patalpos ›
```

- **„Taisyti" opens the Patalpos grid row for that room** — the same grid as §3.2, with the drawing still on screen. Not a full-screen Prielaidos takeover.
- The €-share is the ranking key, and it is now honest: a room's share of the sąmata is computable and stable, unlike a material row's.
- Keyboard: `T` = teisinga, `P` = taisyti, `↓` = kita patalpa, `Esc` = išeiti. 11 rooms, two keys each.
- **Rows the drawing cannot answer never enter this queue.** They go to their own block, with an input:

```
KĄ REIKIA SUVESTI PATYS (12)                     brėžinys šito neparodo
  GKP „dėžučių" montavimas ant lubų        [        ] m    [Įrašyti] [Nereikia]
  Nišų pertvarose įrengimas (dušo, dekoro) [        ] m    [Įrašyti] [Nereikia]
```

### 3.5 The ripple — what a fix did

After every input change, one line under the card, persistent until dismissed:

```
Pataisyta: 104 Darbo kambarys · plotas 13,51 → 14,20 m²
Perskaičiuota 14 eilučių · sienų +6,4 m² · +58 €      [Rodyti pakeistas]  [Atšaukti]
```

- `Rodyti pakeistas` filters the Kiekiai table to exactly the changed row ids (ids exist — `extractor/position_id.py`).
- `Atšaukti` reverts that one correction. The `corrections` table already stores old and new values; today nothing reads them back.
- When no prices are entered yet, the € clause is replaced by the quantity delta only. Never invent a €.
- Show it **in place** — never require a tab switch to learn whether an edit did anything.

### 3.6 How he knows he is done

Replace the row-based „Patikimumas 4 %" (which is both wipeable and meaningless at 72 rows) with:

```
Patikrinta 11 iš 11 patalpų · 96 % sąmatos vertės
Liko 12 eilučių, kurių brėžinys neparodo — suveskite patys arba pašalinkite.
[ Eksportuoti ]
```

Export stays available at all times, but the button carries the state: „Eksportuoti (3 patalpos nepatikrintos)".

### 3.7 Copy rules for all of the above

All strings guide, they do not confess (per the existing vocabulary guard): say **what to check**, never a client name, an error rate, a benchmark count, or a pipeline identifier. `medziagu_norma` must never reach a user; the honest version is *„Kiekis apskaičiuotas iš darbo kiekio pagal sąnaudų normą"* — which the card already says.

---

## 4. Simplicity cuts — first-time contractor, NewProject → export

`NewProject` is already good (`ux-12-new-project.png`): one default type, two optional fields, one dropzone, one button. Leave it. Two nits: the dropzone says 50 MB while the backend accepts 200; and the 30-minute wait is dead time that §3.1 should use.

Everything after upload is where the load is. Proposed minimal screen set: **Brėžinys (with the Patalpos grid + Patikra rail) · Sąmata · Eksportas.**

| Cut | Why | Where |
|---|---|---|
| **Delete the 3-step onboarding wizard** | 4 clicks and ~90 words of prose before he sees his own drawing; the Patalpos step teaches the same thing by doing it | `OnboardingTooltips.jsx` |
| **Do not open on page 1** when page 1 is a cover render | his first sight of the product is a stock interior photo, not his plan | `TakeoffViewer` initial page |
| **Delete the „PATIKROS REŽIMAS · LIKO 85" strip in Kiekiai** | a second review system with a different count (85 vs 72) and different verbs | `ProjectMainView.jsx` |
| **Collapse „Takeoff kontrolė" (4 stat tiles) and the 4 filter chips** | 8 controls above the table before the first row; the same information is one line | `ProjectMainView.jsx` |
| **Hide „Analizės detalės (admin)" and „AI brėžinyje rasti simboliai (181)"** | developer telemetry on a customer screen | `ProjectMainView.jsx` |
| **Row height 85 px → ~40 px** | 118 rows ≈ 10 000 px of scroll; measured 12 s to find a row | `ProjectMainView.jsx` WorkRow |
| **Prielaidos: stop taking over the whole screen**, and move heights / sienos / lubos into the Patalpos grid. Leave Prielaidos with the 3 project-wide settings | its own copy promises a recompute „dešinėje" where nothing exists; and a per-room control belongs on the per-room screen | `AssumptionsPanel.jsx`, `InteriorProject.jsx:988` |
| **Move „Sienos storis" out of first position** or label it plainly | its own note says it does not change quantities — it is the first control on the page | `AssumptionsPanel.jsx:478` |
| **Demote AI Chat from a top-level tab to a button** | a third of the primary navigation for something he will not use before he trusts the numbers | `InteriorProject.jsx:234` |
| **Fix the toolbar overflow** — „Taisyti zoną" is clipped at 1440 px | `ux-13-room-focus.png` | `TakeoffViewer.jsx` toolbar |
| **Select-on-focus for every numeric input** | reproduced `3,22,8` | shared input component |
| **Words to drop or gloss**: „pozicijos" → „eilutės"; „prielaidos" → „nustatymai"; „Q lygis" → keep but always with „(glaistymo kokybė)"; „medziagu_norma" → never shown. Keep „eksplikacija" — it is the real LT term and it is what is printed on his drawing. | | i18n `lt.json` |

Screenshots referenced (all in the session scratchpad `…/scratchpad/ux/`):
`ux-01-first-screen.png` (two modals on load) · `ux-02-prielaidos.png` (full-screen Prielaidos, no area/tiles/floor) · `ux-03-after-height-edit.png` (no feedback) · `ux-04-kiekiai.png` (the second review system) · `ux-05-add-row.png` (row heights, added row at the bottom) · `ux-06-patikra-rail.png` (the rail + ripple, drawing stuck on the cover) · `ux-07-patikra-fix.png` (inline quantity fix) · `ux-08-deeplink-prielaidos.png` (deep-link lands, no drawing) · `ux-09-plan-page2.png` (plan + auto scale) · `ux-10-ledger.png` (material row: dead end + leaked key) · `ux-11-ledger-paint.png` (the good ledger) · `ux-12-new-project.png` · `ux-13-room-focus.png` (red ring, clipped toolbar button).

---

## 5. Build list, ordered

Ordering rule: nothing that adds a verification gesture ships before the thing that stops verification being destroyed.

| # | Change | Size | Component that evolves | Unblocks |
|---|---|---|---|---|
| 1 | Carry `_review_status`, `user_verified_at` (and `_room_verified`) through **both** merge layers | **S** | `api/recompute_quantities.py:1115`, `lib/mergeDarbuSarasas.js:260` | the entire loop (§1.2) |
| 2 | Exempt `rnk-…` ids from the „pasenusi eilutė" badge; scroll-to + focus a newly added row | **S** | `mergeDarbuSarasas.js:375`, `ProjectMainView.jsx:661` | (e) |
| 3 | Select-on-focus on every numeric input; `Enter` = commit + next | **S** | shared input | (b)(d) everywhere |
| 4 | Debounce the correction log to one row per committed decision | **S** | `AssumptionsPanel.jsx:297` | honest „Įsiminta" counter |
| 5 | Inline quantity input on the „SUVESKITE PATYS" rows | **S** | `ReviewQueueSidebar.jsx:420–433` | the 12 must-fill rows |
| 6 | Open on the plan page; delete the onboarding wizard; cookie banner off the project screen | **S** | `TakeoffViewer`, `OnboardingTooltips` | first 30 s |
| 7 | **Resurrect the room editor as the „Patalpos" grid beside the drawing** (plotas, perimetras, aukštis, paskirtis, add/remove) | **M** | `RoomsGrid.jsx` + `RoomCard.jsx` re-homed into `InteriorWorkspace`; delete the dead `tab === 'kiekiai'` branch | **(a)(g)(h)** |
| 8 | Ripple bar with € delta, „Rodyti pakeistas", and a working „Atšaukti" off the `corrections` table | **M** | `ReviewQueueSidebar` ripple block + `ProjectMainView` filter | feedback + undo |
| 9 | Room-first Patikra: verify 11 rooms, rows inherit; keyboard `T`/`P`/`↓` | **M** | `ReviewQueueSidebar` + `PatikraCard` (unit change, not a new surface) | the 2-minute loop |
| 10 | Measurement → room: „Naudoti kaip … plotą / perimetrą" | **M** | `MeasureLayer.jsx` + `WorkspacePanel.jsx:678` | (a) without a table |
| 11 | Per-room **wall finish** three-state (dažomos / plytelės iki N m / neliečiamos) and **floor finish** | **M** | `AssumptionsPanel`→grid + `_ASSUMPTION_FIELDS` (`api/recompute_quantities.py:58`) + `extractor/tile_calculator.py` | **(c)** |
| 12 | Per-room **langai / durys** counts: persist `n_windows`/`n_doors`, expose as grid columns | **M** | `vision_call.py:937` (stop discarding), `_ASSUMPTION_FIELDS`, grid | **(f)** |
| 13 | Fold heights/sienos/lubos into the grid; shrink Prielaidos to project-wide settings; kill the Kiekiai review strip; slim the Kiekiai table | **L** | `AssumptionsPanel`, `ProjectMainView`, `InteriorProject` tabs | simplicity |
| 14 | Run the confirm step **during** extraction, on partial results | **L** | extraction progress → `InteriorWorkspace` | uses the 30-min wait |

---

## 6. Top 5 changes that most reduce time-to-correct

1. **Stop a recompute from erasing „Teisinga ✓"** (S). Measured: one Prielaidos click destroyed 6 of 7 verifications. Until this is fixed, correcting and checking cancel each other out and no loop of any length is possible.
2. **Give the room table back its editor — the „Patalpos" grid beside the drawing** (M). Four of the eight scenarios (a, g, h, and half of c/f) go from **impossible** to ~10 s. The editor already exists and is already wired to a live endpoint; it is rendered inside a tab that no button can reach.
3. **Make verification per-room, not per-row** (M). 72 decisions → 11, each one a thing he can actually check on a plan. 11 rooms × ~8 s ≈ **90 s** — this is the two-minute loop, and it also fixes the queue leading with un-fixable material rows.
4. **Show the ripple where the fix happened — € delta, changed rows, undo** (M). Today an assumption edit moved `sienos virš 3 m` by 116 m² and the screen did not change by one pixel. A correction he cannot see is a correction he will not trust or repeat.
5. **Per-room finishes and openings — tiles, floor, langai, durys** (M). These are the remaining "impossible" scenarios, the engine already accepts the overrides, and the extractor already computes the opening counts before discarding them.

---

## 7. Appendix — state of the test project after this session

The dev project was mutated during measurement and then restored: ceiling heights, Q level, row 1's quantity and the row count are back to their original values (`253,2 / 142,2 / 423,6`, 118 rows). Residue, deliberately left rather than hand-edited in the DB: `_overrides.lubu_auksciai` now carries explicit entries whose values equal the rooms' own, row 1 keeps `manual_override: true` at the AI value (no "restore AI value" control exists — see §1.1 d), and the `corrections` table holds 20 rows from the session. A PDF was attached to the project from the repo fixture so the viewer could be driven; the local `pdf_store` was previously empty.
