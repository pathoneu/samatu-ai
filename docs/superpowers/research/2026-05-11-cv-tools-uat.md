# CV Tools — User Acceptance Test (UAT) Plan

**Status:** Draft, pending 5-user run
**Date:** 2026-05-11
**Owner:** product + first paying samatininkai (rangovas + 4 others)
**Source:** Task 11 of `2026-05-10-drawing-analysis-tools.md`
**Branch shipping the feature:** `week1-canonical-execution`

---

## What we're testing

Two new tools live in PlanViewer's experimental Ženklai (β) panel:

| Tool button | Backend route | Purpose |
|-------------|---------------|---------|
| Skaičiuoti CV  | POST /api/cv/match-template | Drag a box around a symbol → CV finds similar across the page |
| Aptikti patalpą CV | POST /api/cv/magic-wand | Click inside a room → CV suggests a polygon outline |

Both are gated behind `localStorage.setItem('samatu_experimental_tools', '1')`. Each accept/reject calls `/api/cv/record-decision` and writes the cropped image into `data/symbol_training/<klass>/` for a future YOLO V2.

## Recruit

5 samatininkai, each working on a real LT interior project that has:
- ≥1 floor plan page with ≥10 rozečių/jungiklių symbols
- ≥1 room with a closed door (architectural ~6-12 px door gap)
- Existing manual takeoff data we can compare against (we already have rangovo P1, P3 — reuse)

Time per session: 30-45 min. Recorded screen + voice. We pay an honorarium so the session is reciprocal, not extractive.

## Protocol

### Setup (5 min)
1. User opens an existing project with a PDF attached.
2. We unlock the experimental panel via DevTools.
3. We show the two new buttons; user reads the tooltip but is not coached on technique.

### Click-to-count run (10 min)
1. User picks a recurring symbol on the floor plan (e.g. rozetė).
2. User drags a box around one instance → measure
   - **Wall-clock time to first candidate response** (perf SLA target: ≤4 s on a typical A1 page; the matcher caps candidates per scale/rotation at 500 to keep NMS bounded)
   - **Precision** — accepted that were truly that symbol / total accepted (we score against manual ground truth)
   - **Recall** — accepted truly-symbol / true count from manual count
3. User repeats on 2 more symbol classes.

### Magic-wand run (10 min)
1. User clicks inside a closed room with no door gaps → polygon area within ±10% of true room area (true area from existing manual polygon).
2. User clicks inside a room with a door gap, default sensitivity 7 → likely fails; user bumps sensitivity to 11; check the new polygon.
3. User clicks on a wall → expects the inline error nudge ("Paspaudei ant sienos…").

### Comparison (10 min)
- "How long would the same task take you in Bluebeam / on print?"
- "Which tool is more useful — the symbol counter or the room wand? Why?"
- "What would make you stop using this and go back to your old workflow?"

### Open feedback (5 min)
Free-form. Record verbatim.

## Acceptance gates (ship/no-ship)

| Gate | Target | Source of truth |
|------|--------|-----------------|
| Click-to-count completes in ≤60 s for ≥10 symbols on one A1 page | wall-clock from session timing | screen recording |
| Click-to-count precision ≥85% | per-symbol-class | manual ground-truth count |
| Magic-wand area within ±10% on closed rooms | per-room | existing manual polygon area |
| Magic-wand area within ±25% on rooms with door gaps | per-room | existing manual polygon area |
| ≥3 of 5 users say "I'd use this again" | post-session 5-pt scale (≥4) | recorded answer |
| Server-side: 0 OOM events during a 5-user session | RSS over time | host metrics |

## Known limitations to disclose to UAT users up front

- No pan/zoom inside the rubber-band drag — we draw on screen pixels only.
- Mode switch (count → wand or vice-versa) clears the candidate panel.
- Training data is captured silently; we describe it once at consent time.
- Backend cap of 500 candidates per (scale, rotation) means a 200-instance symbol class will return all of them, but a featureless template will return at most 500 — that's how we avoid NMS blow-ups, not a quality bound.

## What to do if a gate fails

| Failed gate | Most likely fix | Re-test? |
|-------------|-----------------|----------|
| Time gate | Pre-render the page at lower DPI for fast first match, then refine at 200 DPI on accept | yes (1 user) |
| Precision <85% | Bump default `threshold` from 0.80 to 0.85; surface threshold slider in CountTool | yes (1 user) |
| Wand area off | Bump default `close_kernel` from 7 to 9; expose sensitivity hint earlier | no (just ship updated default) |
| OOM | Drop `MAX_CANDIDATES_PER_VARIANT` from 500 to 200 | yes (load test) |
| <3/5 "use again" | Council — find the actual blocker; do NOT just re-tune thresholds | yes (re-recruit) |

## Ship plan

If gates pass: tag `cv-tools-v1`, merge `week1-canonical-execution` to main, announce in changelog as "Eksperimentinis: skaičiavimas + patalpos aptikimas brėžinyje (CV)". Keep behind the `samatu_experimental_tools` flag for one more sprint while we collect real-world precision/recall data from the training-data writer.

If gates fail: one focused iteration per failure mode, then re-test with 1 user per regression.

## Out of scope for this UAT

- Multi-page batch counting (`/api/cv/match-template-batch`) — future RQ-backed route.
- Legend extraction — explicitly rejected by Council R3.
- YOLO V2 — needs the 6-12 month training-data ramp first.
- Mobile / tablet — desktop-only by design (both tools require pixel-precise mouse input).

## Open questions for the user before we run UAT

1. Do you want to record the sessions on Loom for sharing with the council?
2. Are the 5 LT samatininkai the same we used for the prior bake-off, or fresh recruits? (Fresh = stronger signal; same = faster onboarding.)
3. Should we include `_markers` from accepted candidates in F2/F3 exports, or keep them as audit-only metadata?

