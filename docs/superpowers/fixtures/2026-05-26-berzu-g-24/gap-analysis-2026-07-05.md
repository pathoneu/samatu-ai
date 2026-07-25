# Gap analysis — Beržų g. 24 — FRESH MEASURED RUN (2026-07-05)

**Supersedes** `gap-analysis.md` (2026-05-27, now 5+ weeks + an engine generation stale).
**Engine:** Opus 4.8, native-PDF pass-1, voting on, 9 zoom passes (1 applied), apdailos+doors+door_type+fixtures readers.
**Run:** `app-output-2026-07-05-opus48.json` (RUN_ID=0705, 746 s wall-clock, status=ok, 11 rooms, 66 pozicijos).
**Truth:** `samata-truth.pdf` + `contractor-notes-verbatim.md` (Rangovas A).

## Measured per-line gap (corrected for line-splitting)

> ⚠️ The two big "over" reads a naïve matcher produces (LED +79%, Šviestuvai +247%) are **artifacts of summing lines the app still keeps separate** (glaistymas + dažymas; montavimas + gręžimas + apdirbimas). The per-operation numbers below are the real comparison.

| Item | Truth | App | Δ | Root cause |
|---|---|---|---|---|
| Paint **iki 3m** | 371,4 m² | 360,51 | **−3%** ✅ | — |
| Paint **virš 3m** | 213,41 m² | 162,09 | **−24%** 🟥 | **Garage assumption** (below) |
| Paint **total** | 584,81 m² | 522,60 | **−10,6%** 🟥 | Garage (was +0,5% in 2026-05 — the garage default changed the picture) |
| GKP lubų standart | 102,78 m² | 104,43 | +2% ✅ | — |
| GKP lubų **virš 3m** | 62,82 m² | 50,54 | **−20%** 🟥 | Garage ceiling not GKP (below) |
| Rotband/lyginimas | 138,69 m² | 107,09 | −23% 🟨 | Follows the smaller painted-wall base |
| LED niše (per op) | 42,3 m | 37,95 | **−10%** ✅ | Much better than 2026-05 (−41%). Still 2 lines → combine |
| Angokraščiai (per op) | 89,39 m | 78,8 | −12% 🟨 | Slightly under |
| Dažymo kampai | 493,35 m | 383,98 | **−22%** 🟨 | Missing corner categories (~110 m) |
| Šviestuvai (priglaist.) | 38 vnt | 42 | +11% 🟨 | Slightly over (pendants?) |
| Lentynėlės dušo | 5 vnt | 4 | −20% 🟨 | Close |
| **Difūzoriai** | 15 / 21 vnt | **0** | **−100%** 🟥 | Vision emits NO difūzoriai line at all |
| **Rozetės+jungtukai** | 113 vnt | 62 | **−45%** 🟥 | Vision under-count on electrical plan (already ONE combined line ✅) |
| **Termoreguliatoriai** | 8 vnt | 0 | **−100%** 🟥 | Category not tracked |

## The headline finding: the big money gap is an ASSUMPTION, not a bug

`ROOM_TYPE_RULES["garazas"]` = `walls_paint: 0.0, ceiling_type: "betonas"` — the app **defaults to a raw/unfinished garage**. Beržų's garage is **finished**: contractor paints its walls (31,45 m²) and GKPs its ceiling (~10 m²), all at the 3,4 m tier. That ≈41 m² is essentially the **entire** virš-3m gap.

- Vision read the garage **correctly** at H=3,4 m. This is not a detection miss.
- Garages genuinely vary (Beржų finished; Objektas B raw — the default was tuned to Objektas B).
- There is **already** a `garazas_painted` Setup-Wizard override (`translate_user_prefs_to_room_rules`).
- → This is a **project-specific assumption with an existing override**, not a silent calc bug. Do NOT blind-flip the default (would break raw-garage projects). Better: infer garage finishing from the išklotinės, and/or surface it as a prominent, one-click assumption.

## The gaps split cleanly into two buckets

**(A) Assumptions / structure — cheap, no Vision $:**
- Garage finished-vs-raw (above) — better default inference + surface as assumption.
- LED niše: combine `glaistymas` + `dažymas` into one line (number is now −10%, so worth doing; mirrors the 2026-06 paint consolidation, behind the same flag).
- Dažymo kampai: audit which corner categories are summed (some ~110 m unaccounted).

**(B) Vision detection — needs prompt iteration + $ per run, and hits the industry VLM ceiling:**
- Difūzoriai 0/15 — total miss on the lubų plane. Prompt must enumerate per-room.
- Rozetės+jungtukai 62/113 — −45% under-count; likely needs a dedicated electrical-plan reader.
- Termoreguliatoriai — not detected at all.
- Šviestuvai +11% (distinguish priglaistomi vs pakabinami).

## Real measured per-project cost (Opus 4.8, full pipeline)

**≈ $2,37** (≈€2,18) for this 17-page project:
- Pass-1 main: ~$0,93 (output 20 591 tok + cache write 56 k)
- Readers/zoom/door_type/fixtures (18 extra calls): ~$1,44

At €12/project one-off that's ~18–20% COGS on extraction alone — healthy but not fat; **re-runs erode it fast**. Confirms the "guard gross margin" point.

## Recommendation (ties to the assisted-not-automatic strategy)

Don't pour $ into chasing bucket (B) to perfection — that's the VLM ceiling. Invest in making (A) + (B) **fast to correct**: garage finishing as a one-click assumption, difūzoriai/rozetės counts trivially editable, every fix trained into the corpus. The measured data on his own project validates the thesis: the last 20% is correction UX, not detector accuracy. The one clean free win to bank now: **LED niše line combination**.
