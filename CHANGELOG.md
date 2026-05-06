# Changelog

## Launch package M1–M5 — 2026-05-06

### M1 — Codex PlanViewer layout port
- Replaced Sprint 1 mip-pyramid `TakeoffCanvas` (broken at low zoom)
  with codex's `react-pdf`-based `PlanViewer`. New tabs at top
  (Brėžinys / Kiekiai / AI Chat) + page thumbnails sidebar + right
  panel with provenance pills and review queue.
- Click on a room number deterministically pulses a marker on the
  drawing (via pdfplumber-located digit text) — replaces unreliable
  Vision bbox-based click-to-pan.
- Imported 16 codex lib files (planOverlayGeometry, planSymbolTypes,
  planViewerState, quantityOverride, symbolOverlay, takeoffWorkflow,
  viewerPrefs, viewerViewport + their tests). Frontend test count
  118 → 160.

### M2 — Subtle provenance + trust UI
- `ProvenanceChip` already shipped via codex (eksplikacija/manual/
  vision/dimension pills); kept default-trust totals (no review wizard
  per user feedback).
- Bug fix: backend wrote `plotas_saltinis` (LT) but frontend
  `ConfidenceBadge` read `plotas_source` (EN) — every eksplikacija
  room rendered as 🔴 neaišku. Added saltinis→source mirror on both
  sides so eksplikacija rooms now correctly show 🟢 tikslus.

### M3 — Formula audit
- Research agent produced 6,700-word audit
  (`docs/formulas/2026-05-06-formula-audit.md`) + 1-page summary
  citing 27 sources (RICS NRM2, DIN 18181/18299/18350/18363/18365/
  18534-1, EN 13300/14891, ISO 13007, Merkblatt Nr.2, Knauf, Mapei,
  Tikkurila, Caparol, TCNA, NKBA, LT STR 1.05.06/2.04.01).
- Critical fixes shipped:
  - Window reveal `2H + W` → `2H + 2W` (4 sides, 29% undercount).
    Doors stay 3-side. Sources: NRM2 §29.10, DIN 18363 §4.2.4.
  - Tile straight waste 0.08 → 0.10 per NRM2 §28 + LT QS practice.
  - Sanity check `check_window_reveals` expectation 4.0–6.0 m → 4.5–7.5 m.
- Deferred to Sprint 6: GKP CW+UW frame split, acoustic insulation,
  paint coverage by plaster type, hidro consumption tuning.

### M4 — Auth: Google OAuth + open registration
- Backend `GET /api/auth/google` + `/api/auth/google/callback` —
  state CSRF guard, code→token→userinfo, matches by google_sub then
  email then creates new user. Activates only when GOOGLE_CLIENT_ID
  + GOOGLE_CLIENT_SECRET env vars set.
- DB schema: `users.google_sub` (UNIQUE WHERE NOT NULL) +
  `users.avatar_url` via append-only migration. New helpers
  `get_user_by_google_sub`, `create_user_oauth`, `link_google_to_user`.
- Frontend `<GoogleSignInButton next=…/>` polls
  `/api/auth/google/status` and renders nothing when disabled.
- Email/password registration was already open (no beta codes).

### M5 — Production prep + landing
- `backend/.env.example` documenting all env vars
  (ANTHROPIC_API_KEY, SAMATU_SECRET_KEY, ENV, GOOGLE_CLIENT_*,
  SAMATU_USER_DAILY_SPEND_EUR, SAMATU_USER_HOURLY_EXTRACTS,
  SAMATU_CORS_ORIGINS, feature flags).
- Per-user daily Vision spend cap + hourly extract count enforcement
  on `/extract-interior`. `db.user_recent_spend_eur(user_id, hours)`
  joins extractions × projects.
- Security headers middleware: `X-Content-Type-Options=nosniff`,
  `X-Frame-Options=DENY`, `Referrer-Policy`, `Permissions-Policy`.
  In `ENV=production`: HSTS + CSP (default-src self, allows Google
  OAuth domains).
- Session cookie `https_only=true` when `ENV=production` (was always
  false). CORS origins from `SAMATU_CORS_ORIGINS` env (was hardcoded
  localhost).
- New public landing page at `/` with hero + 3 feature cards + 4
  audience cards + CTA + footer. RootRoute redirects logged-in users
  to `/dashboard` (Dashboard moved from `/`).
- Privacy + Terms pages already existed.

### Tests
- Backend: 246 → **255** (+9 from sanity + bbox-validator additions
  earlier in week)
- Frontend: 118 → **160** (+42 from codex lib tests)
- Build: vite ✓, FastAPI loads cleanly with new OAuth + middleware

## Sprint 4 followup — bbox accuracy + ergonomics — 2026-05-05

### Added
- `extractor/sanity_checks.py::check_gk_sheets_math` — was a placeholder;
  now sums per-room `gkp_lubu_standart_m2`, applies `ceil(area/3.0)*1.10`
  formula, compares against the "GKP lapai luboms" pozicija (warns at
  >5% drift). 4 new tests.
- `extractor/vision_call.py::_validate_room_bboxes` — runtime sanity
  check that warns when union of room bboxes covers <5% of the page
  (sign Vision picked label/elevation instances rather than floor plan
  rooms). 5 new tests.
- Empirical `GRINDJUOSCIU_RATIO_CAP=0.65` band-aid now appends a
  user-visible warning when fired, pointing at re-extraction as the fix.
- Page-aware click-to-pan: `QuantitiesPanel.panToRoom()` auto-switches
  PDF page to `room.puslapio_nr` before panning.

### Fixed
- `AssumptionsPanel.jsx` was reading `rooms[].lubu_aukstis_mm` (didn't
  exist) — backend emits `lubu_aukstis_m`. The fallback `|| 2800` always
  fired so AI-extracted ceiling heights were ignored.
- `prompt.py` Pass-1 — strengthened `bbox_pct` instructions with
  explicit DAŽNA KLAIDA section + 5 negative examples (elevation /
  mazgas / eksplikacija / baldai instances must NOT be selected — only
  floor plan top-down view).
- `InteriorProjectV2.jsx` — `committedPolygons` filtered by
  `currentPage` so room polygons only render on the page they belong to.

### Tests
- Backend: 246 → 255 (+9 tests, all passing)
- Frontend: 118/118 passing, vite build clean

## Sprint 3 — Chrome + Verification Wizard — 2026-05-04

### Added — frontend chrome
- `<TopBar>` 48px chrome row with project name, page nav, zoom, Patikrinti
  button (conditional on queue), Sąmatų AI button, ⋯ menu
- `<ToolRail>` 50px vertical rail with 10 visible tool buttons replacing
  Sprint 2's keyboard-only model. ✨ AI badges on G1/G4/G5
- `<RightPanel>` 320px tabbed container (✨ AI / 📋 Kiekiai / 📊 Suvestinė)
- `<QuantitiesPanel>` (replaces Sprint 2 MiniKZPanel) — category tree +
  filter pills (Visos / 🔴 / 🟡 / 🔒) + search + bidirectional highlight +
  G7 inline edit + Σ totals footer
- `<AiPanel>` — Run Sąmatų AI button + recent-runs list (empty state)
- `<SuvestinePanel>` — Σ neto + 21% PVM card + per-category horizontal bars
- `<PageNavigator>` page picker dropdown
- `<VerificationWizard>` — opt-in bottom panel (~140px) walking through
  🟡+🔴 items step-by-step with auto-zoom, Taip/Pataisyti/Praleisti.
  Shift+Taip locks 🔒. Pataisyti dispatches by dispute_type (number →
  inline editor; count → G2/G3 cursor; polygon → G1 cursor)
- `<InlineEditor>` — bottom-panel inline editor for number disputes

### Added — frontend libs
- `verificationQueue.js` — pure: builds queue from rooms+pozicijos,
  orders 🔴 first, classifies dispute_type, supports skipped tracking
- `categoryColor.js` — single primary blue (Sprint 3 spec §3 locked)
- `scaleStore.js` — zustand sub-store for scale ratio + lock

### Added — backend (Section 6 appendix)
- `extractor/verify_pass.py` — Opus 4.7 self-verify shim returning
  advisory corrections[] (Sprint 3 stub; Sprint 4 wires real SDK call).
  Gated by `ENABLE_VERIFY_PASS=1`
- `extractor/grid_overlay.py` — Pillow stamps faint 1m gridlines onto
  page raster. Gated by `ENABLE_GRID_OVERLAY=1`
- `prompt.py` — stripped 3,341 tokens (~28% of SYSTEM_TEXT) of unused
  formula text + stale pozicijos guidance + outdated examples

### Changed
- `viewerStore` extended with `wizardOpen`, `wizardItemPolygon`,
  `lockOnConfirm`, `currentPage` + setters
- `<TakeoffCanvas>` reads `currentPage` from viewerStore (was hardcoded 0);
  added subtle blueprint grid background (Kreo pattern); ScaleBadge
  bottom-left placeholder
- `<AnnotationLayer>` reads `hoveredRoomId` for stroke thicken + glow;
  fourth layer draws `wizardItemPolygon` amber-glow during verification
- `<InteriorProjectV2>` body fully rewritten: composes new chrome
  (TopBar / ToolRail / Canvas / RightPanel / Wizard) with bidirectional
  highlight wiring + per-tab badges + AI run handler
- `MiniKZPanel.jsx` deleted (superseded by QuantitiesPanel)

### Known follow-ups
See `docs/sprint-3-followups.md`. Notable: Pataisyti polygon flow needs
post-gesture wizard re-entry; scaleStore not yet wired to project; AI
recent-runs persistence pending; grid_overlay caller integration into
Pass-1 raster pipeline pending Sprint 4.

### References
- Spec: `docs/superpowers/specs/2026-05-04-sprint-3-chrome-design.md`
- Plan: `docs/superpowers/plans/2026-05-04-sprint-3-chrome.md`
- Brainstorm artifacts: `.superpowers/brainstorm/.../sprint-3-layout-{v1..v4}.html`

## Sprint 2 — Gestures (G1–G5 + G7) + Shared-Walls Polygon Pre-Pass — 2026-05-04

### Added — backend
- `POST /api/vision-fill` (G1) — click-to-fill polygon endpoint (stub Vision shim;
  real Pass-2 zoom call is Sprint 4).
- `POST /api/lasso-rerun` (G5) — freehand-region symbol re-extract endpoint
  (stub shim; real Vision crop is Sprint 4).
- `/api/recompute-quantities` extended with G2/G3/G4/G7 edit fields:
  `add_symbol`, `remove_symbol`, `color_zone`, `override_pozicija`.
- `backend/extractor/wall_adjacency.py` — deterministic shared-edge math from
  per-room `polygon_pct[]`. Subtracts half each shared wall from `perimetras_m`
  to fix grindjuostės double-counting. Feature-flag-gated by
  `ENABLE_POLYGON_PREPASS=1`. Bails out when any room lacks a polygon.
- Vision schema gains optional `polygon_pct: [{x, y}, ...]` per room.

### Added — frontend
- `<AnnotationLayer>` Konva 3-layer overlay (committed `listening=false`,
  active selected layer, preview hover/lasso layer).
- Six gesture hooks: `useG1Handler` (Vision click), `useG2Handler` (add count),
  `useG3Handler` (remove), `useG4Handler` (eyedropper), `useG5Handlers`
  (lasso pointer trio), G7 inline-edit in `<MiniKZPanel>`.
- Keyboard shortcuts V / 1–5 / Esc map to `viewerStore.currentTool`.
- `abortRegistry` cancels prior gesture in-flight on each new same-kind call.
- New libs: `coordTransform.js`, `gestureApi.js`, `abortRegistry.js`,
  `keyboardShortcuts.js`, gesture sub-libs `g4-color-sample.js`,
  `g5-lasso-geometry.js`.

### Changed
- `<TakeoffCanvas>` accepts `renderOverlay({ canvasWidth, canvasHeight, ... })`
  so gesture surfaces mount on top without prop drilling.
- `viewerStore` gains `selection`, `setSelection`, plus `verificationQueue` /
  `verificationIndex` placeholders (Sprint 3 fills these).
- `<AssumptionsPanel>` parent now consumes `onRecomputed` so Sprint 0 paint
  formula delegation actually reaches the UI (was NaN-propagating;
  follow-up #6 fixed).
- `backend/main.py` router imports consolidated to top of file (Sprint 0
  follow-up #2).

### Known follow-ups
See `docs/sprint-2-followups.md`. Notable: G4 polygon-detection is a
placeholder (Sprint 4); G7 lives in MiniKZPanel only (full QuantitiesPanel
in Sprint 3); ENABLE_POLYGON_PREPASS still needs golden-PDF validation
(spec §10).

### References
- Spec: `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md`
  §4.1, §4.3, §4.5, §5.4, §6 Sprint 2.
- Plan: `docs/superpowers/plans/2026-05-04-sprint-2-gestures.md`.

## Sprint 1 — Tile-Based Rendering — 2026-05-03

### Added
- New `<TakeoffCanvas>` component (`frontend/src/components/canvas/`) with
  mip-pyramid (3 fixed zoom levels: 0.5×, 1.5×, 3×) + CSS-transform-during-
  interaction + OffscreenCanvas settle render. Zoom and pan should now hit
  60 fps even on large PDFs.
- New route `/project/:id/v2` mounts the takeoff workspace alongside the
  legacy viewer at `/project/:id`. Default switches at end of Sprint 3;
  legacy removed Sprint 4.
- `MemoryWatchdog` auto-resets the PDF doc when JS heap exceeds 500 MB and
  the user is idle for 30 s, addressing pdf.js #20198 leak.

### Internal
- New libs: `viewerStore.js` (zustand), `renderQueue.js` (p-limit(2)),
  `tileCache.js` (LRU + ImageBitmap close-on-evict), `mipPyramid.js`
  (zoom-level math + OffscreenCanvas page renderer).
- 4 new frontend test files (16 new tests); pure-function math for mip
  selection and cache eviction is fully unit-tested.

### Known follow-ups
See `docs/sprint-1-followups.md`.

## Sprint 0 — Math Fixes + Baseline Timing — 2026-05-03

### Changed (user-visible)
- **GKP pozicijos split** — wall sheets (12.5 mm) and ceiling sheets (9.5 mm)
  are now separate rows. Previously lumped into single "GKP lapai (12.5 mm)"
  row regardless of where they were used. **Order accuracy improvement.**
- **Paint formula** — frontend Prielaidos panel now calls backend for recompute.
  Eliminates the divergence between frontend (`*2/9`) and backend (paint class
  model with 1.8× absorption). Result: numbers stay consistent when you edit
  assumptions.

### Added (under feature flags, default off)
- `ENABLE_PER_ROOM_CEILING=1` — Vision returns ceiling heights per room when
  they vary (soffits, dropped ceilings); paint volume becomes more accurate.
- `ENABLE_PAINT_CLASS_INFERENCE=1` — Vision reads explicit Q-spec from drawing
  ("Q2 matinis", "Q4 blizgus") and pre-fills paint class.

### Added (always-on)
- Scale verification — warns when title-block scale doesn't match rendered DPI
  (catches the "1:100 PDF mislabeled as 1:50" case). Currently a no-op until
  Vision schema emits per-room pixel diagonals (tracked as follow-up).
- Session telemetry — `backend/telemetry/session_log.jsonl` records open/close
  + gestures for Sprint 4 baseline comparison.
- `GET /api/config` — exposes feature flag state to frontend.
- `POST /api/recompute-quantities` — single source of truth for paint recompute.
- `POST /api/telemetry/session` — frontend POSTs session record at end.

### Known follow-ups (tracked in docs/sprint-0-followups.md)
- Frontend `dazaiSienoms`/`dazaiLuboms` consumers produce NaN until parent
  wires `onRecomputed` to feed backend results back into the UI.
- Wall GKP path is dormant (extraction schema only emits ceiling GKP today).
- Scale validator is a no-op until Vision returns per-room diagonal_px.

### References
- Spec: `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md`
- Plan: `docs/superpowers/plans/2026-05-03-sprint-0-math-fixes.md`
- Baseline: `docs/baseline-timing-2026-05.md` (TODO — manual stopwatch runs pending)
- Snapshots: `docs/snapshots/2026-05-03-sprint-0-snapshot-plan.md` (TODO — Ignas to run)
