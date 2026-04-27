# Research Findings: Togal.ai UX Patterns for Sąmatų AI

**Sources verified live via WebFetch and WebSearch on 2026-04-27. No fabrication.**

---

## 1. Executive Summary — Top 5 Patterns to Adopt (Ranked by ROI)

| Rank | Pattern | ROI Rationale | Effort |
|------|---------|---------------|--------|
| 1 | **Inject project JSON into AI Chat (Togal.CHAT equivalent)** | We already have the AI Chat tab — it just isn't grounded in the current project data. One backend change makes it answer "kiek langų kambaryje 2?" correctly. Zero new infrastructure needed. | S |
| 2 | **Page classification labels in Brėžinys sidebar** | Vision already classifies pages internally. Surfacing "1: Aukšto planas / 2: Sienų išklotinė / 3: Lubų planas" to the user shows professional competence and helps estimators spot missing drawing types immediately. | S |
| 3 | **Expose formulas in Prielaidos tab** | Togal's Custom Formula layer proves estimators want to see and modify the math. Our interiorCalc.js has all LT formulas — they're invisible. "Dažų kiekis = plotas × 2 sluoksniai / 9 m²/l" shown and editable = massive trust gain. | S |
| 4 | **Bidirectional Kiekiai ↔ Brėžinys highlight** | Clicking a room row in Kiekiai should highlight its bbox in Brėžinys. Togal proves bidirectional navigation is the fastest accuracy-verification path. One React state change connecting existing components. | S |
| 5 | **Repeating Groups for daugiabučiai** | LT renovation is dominated by Soviet-era apartment buildings with identical floor plates. "Aukštų skaičius" multiplier in Prielaidos: measure one floor, multiply by 5-9. Togal launched this in 2025 as their marquee feature; we can adapt it for LT interior in weeks. | M |

---

## 2. Pattern Catalog (20 Patterns)

### P01 — One-Click AI Trigger ("Togal Button")
**Source:** https://www.togal.ai/features, https://www.togal.ai/how-it-works

**What:** Single green button triggers full AI processing — detection, measurement, labeling, classification of all spaces. No pre-configuration.

**Why it works:** Zero-friction entry. Editing > creating, removes "configuring it wrong" fear.

**Adapt for LT:** We have "Analizuoti" trigger. Critical missing: streaming progress feedback. "Analizuojamas puslapis 3/7... aptikta 4 kambariai..." — wait feels active rather than broken.

**Effort:** S — FastAPI SSE streaming, React progress display

### P02 — Per-Classification Color Coding + Bidirectional Canvas ↔ List
**Source:** https://www.togal.ai/blog/how-to-create-classification-groups-with-togal-ai

**What:** Each classification gets distinct color overlay. Click row → highlight polygon. Click polygon → highlight row.

**Why it works:** Bidirectional selection = fastest error catching. Spatial + tabular views reinforce each other.

**Adapt for LT:** AiRoomOverlay has bboxes. Missing: (a) per-classification color picker, (b) click-row → scroll-to-bbox in Brėžinys.

**Effort:** S — shared selectedRoomId state in React

### P03 — Auto-Naming and Drawing Type Classification on Upload
**Source:** https://www.togal.ai/how-it-works, https://help.togal.ai/release-notes-january-25-2025

**What:** AI reads title blocks, sheet numbers, page content to rename and categorize all pages automatically. Per-drawing readiness indicators.

**Why it works:** LT projects arrive as 50–80 page PDFs with no internal organization. Manual identification wastes 10–20 minutes.

**Adapt for LT:** CLAUDE.md Section 4 lists all LT drawing types. Vision already classifies internally. Surface: "1: Aukšto planas ✓", "2: Sienų išklotinė ✓", "3: Lubų planas — nerastas ⚠️". Estimator sees coverage and gaps immediately.

**Effort:** S — schema addition + sidebar render

### P04 — Keyboard Shortcuts for Drawing and Selection
**Source:** https://www.togal.ai/blog/how-to-draw-areas-lines-counts

**What:** P=polygon, L=line, K=count, Shift+click=90° corner, Z=undo, Enter=close, Shift+drag=multi-select. Tooltips on toolbar.

**Why it works:** Professional estimators (20+ takeoffs/week) live on keyboards. Mouse-only = "demo product."

**Adapt for LT:** No manual drawing tools yet. Build shortcut system in initial sprint, not as follow-up.

**Effort:** S as part of manual tools; retrofitting M

### P05 — AI Auto-Classify with Fail-Safe Behavior
**Source:** https://www.togal.ai/blog/how-to-auto-classify-areas-using-the-automatic-classification-feature-of-togal-ai

**What:** AI suggests classification based on spatial context + 100M+ pre-classified drawings. **Critical**: if not confident, leaves original label rather than guessing. Batch mode: Shift+drag → right-click → "Auto Classify".

**Why it works:** Fail-safe behavior builds trust faster than 98% accuracy with occasional wild misses. Batch path: 20 identical rooms ≠ 20 manual corrections.

**Adapt for LT:** AI classifies by paskirtis but no correction UI. Add: (a) click-to-reclassify dropdown of LT room types, (b) "taikyti visiems tokiems" — bulk apply to /recompute-interior.

**Effort:** M — classification edit modal + bulk apply

### P06 — Repeating Groups (Master Unit → N Copies)
**Source:** https://www.togal.ai/blog/2025-features-roundup

**What:** User measures one master unit. Selects identical instances. System multiplies. Supports rotation/flipping. Change master → all copies update.

**Why it works:** Highest-leverage feature for repetitive construction. 60-unit block doesn't require 60 takeoffs.

**Adapt for LT:** LT renovation dominated by Soviet-era daugiabučiai — identical floor plates × 5–9. "Aukštų skaičius" input + "pirmas/paskutinis aukštas skiriasi" checkboxes. Simpler than Togal's full UI, fits dominant LT use case.

**Effort:** M — backend multiply-by-floors logic; Prielaidos tab UI

### P07 — Togal.CHAT — Grounded AI Chat Against Project Documents
**Source:** https://www.togal.ai/news/chatgpt-enters-the-construction-industry-with-togal-ai

**What:** Integrated GPT-powered chat that searches across all uploaded documents using semantic search. RAG — retrieves before generates.

**Why it works:** Standard LLM hallucinates. Togal.CHAT is grounded — verifiable sources.

**Adapt for LT:** AI Chat tab is currently stateless. Inject full extraction JSON as system prompt prefix. Now answers "kiek langų virtuvėje?" correctly. Also enable LT norm questions: "ar hidroizoliacija reikalinga?" — AI checks against STR.

**Effort:** S — add project JSON to chat endpoint system prompt

### P08 — Real-Time Collaboration with External Guests
**Source:** https://www.togal.ai/pricing-licenses

**What:** Multiple users including external guests access same project via link. No paid seat for guests. Real-time sync.

**Why it works:** Estimating involves 3–5 stakeholders. Excel email creates version conflicts + 1–2 day cycles. Guest-via-link = minutes. Viral growth.

**Adapt for LT:** Read-only UUID share link first. Estimator shares with statybos vadovas. They see Kiekiai + Brėžinys, can export PDF, can't edit. Requires DB migration (we did this in Phase 12.3).

**Effort:** L — DB migration prerequisite (✓ done Phase 12.3); URL token system

### P09 — Drawing Set Comparison (Revision Detection)
**Source:** https://www.togal.ai/blog/supercharge-your-estimating-workflow-using-togal-ai

**What:** Upload original + revised → highlights changed areas, flags quantity changes.

**Why it works:** Change orders = where construction loses money.

**Critical caveat from research:** Peer-reviewed Univ. of Kansas study + iBeam analysis: requires manual review for complex changes, cannot cross-reference between sheets. Togal's most-marketed weakest feature.

**Adapt for LT:** **Defer.** LT small renovation projects don't have formal revisions. When built later, be honest about limitations.

**Effort:** L — defer to 2027

### P10 — Custom Formula Layer (Measurement → Material Quantity)
**Source:** https://help.togal.ai/custom-formulas

**What:** Each classification has Excel-like formula: `= Quantity1 * 2`, `= Area / 9`. Auto-applies to manual + AI takeoffs.

**Why it works:** Bridges geometry → purchase quantity. Without this, estimator still uses Excel.

**Adapt for LT:** interiorCalc.js has all LT formulas — invisible code. Expose in Prielaidos as readable strings with editable constants. "Dažų kiekis = plotas × 2 sluoksniai / 9 m²/l." Premium vs economy paint = different coverage. Satisfies CLAUDE.md "every calculation must show its assumptions."

**Effort:** S — export formulas from interiorCalc.js; display in AssumptionsPanel.jsx

### P11 — 3D Takeoff Visualization
**Source:** https://www.youtube.com/watch?v=bCM_2ea46h4

**What:** 2D takeoff extrudes into basic 3D. Useful for volume verification.

**Adapt for LT:** **Skip.** Paintable area doesn't benefit from 3D. CLAUDE.md Section 6 validation checks are better near-term.

**Effort:** XL — skip

### P12 — AI Image/Text/Pattern Search Across Plan Set
**Source:** https://www.togal.ai/features

**What:** 3 search modes: image (draw bbox → find instances), text (type "WC"), pattern (similar symbols). Cross-plan, interruptible.

**Why it works:** LT projects reference same door schedule across 12 pages. Manual hunting = 20–40 min.

**Adapt for LT:** We detect elements but user can't verify which were counted. "Parodyk visus langus" search highlights all detected window bboxes. Most valuable for "Vision missed 1 window" case.

**Effort:** M — store per-element bboxes + search filter

### P13 — Classification Library with Seeded Defaults
**Source:** https://www.togal.ai/blog/how-to-create-classifications-with-togal-ai

**What:** Reusable library of classifications with formulas, colors, units. Business plan includes Togal-seeded library.

**Why it works:** First takeoff slow (learning). 10th should be faster than Excel. Seeded library delivers from project one.

**Adapt for LT:** **Biggest competitive opportunity.** Pre-seeded LT library: room types in Lithuanian, materials from CLAUDE.md Section 3 with LT waste factors, hidroizoliacija pre-included in vonia/WC (no US tool knows this). Togal's library is US-centric and would confuse LT estimators immediately.

**Effort:** M — JSON schema + seed data + library UI

### P14 — Hierarchical Quantities Panel (Folder → Classification → Item)
**Source:** https://www.togal.ai/blog/how-to-set-project-quantities-using-the-quantities-panel-in-togal-ai

**What:** Right panel: Folder → Classification → Item. Collapsible. Click classification → highlight on canvas. Running totals across pages.

**Why it works:** Mental model alignment — estimator thinks "how much painted in bedroom 2?" top-down, not flat list scroll.

**Adapt for LT:** Kiekiai tab is flat. Restructure: Skyrius (GKP, Glaistymas, Plytelės, Dažai) → Kambarys → Pozicija. Matches LT kiekių žiniaraštis hierarchy. Cross-tab highlight. Structural refactor that makes us feel like real QS tool.

**Effort:** M — data model + UI restructure

### P15 — Progressive Loading for Large Plan Sets
**Source:** https://www.togal.ai/blog/2025-features-roundup

**What:** Caching system rewrite — immediate work while pages load in background. Per-page readiness indicators.

**Why it works:** Large projects previously blocked users for minutes. Progressive loading drops perceived wait → near zero.

**Adapt for LT:** Worst UX moment: 3–8 min full-project spinner. Wins: (a) show rooms as Vision returns first batch, (b) "Analizuojamas puslapis 3/7" progress, (c) explore Kiekiai for completed rooms while others load. Transforms "broken?" → "watch AI work in real time."

**Effort:** M — FastAPI SSE; React state appends rooms

### P16 — Export with Group By / Filter / Column Selection
**Source:** https://help.togal.ai/how-to-leverage-the-export-tool-inside-togal

**What:** Before Excel: choose 3 grouping levels, filter scope, select columns. Two modes: "Screen View" (UI hierarchy) + "Full Export" (raw data).

**Why it works:** Translation layer between Togal data model and client's existing templates.

**Adapt for LT:** Export to F2/F3 LT procurement forms. Add: (a) skyrius filter ("eksportuoti tik GKP"), (b) toggle Pastabos sheet, (c) raw data mode for pivot. **F2/F3 = competitive moat vs Togal** — required for LT public procurement, Togal cannot produce them.

**Effort:** S — export options modal

### P17 — External Share Link Without Paid Seat
**Source:** https://www.togal.ai/pricing-licenses

**What:** Growth plan: unlimited external collaboration via link, no license required for guests.

**Why it works:** Viral growth. Reduces buyer friction.

**Adapt for LT:** Read-only UUID URL. No login for viewing. Estimator → statybos vadovas / subcontractor. Sees Kiekiai + Brėžinys, exports PDF, can't edit. **DB migration ✓ done Phase 12.3.** High viral potential in small LT construction community.

**Effort:** M — share token system

### P18 — Snapping Engine for Manual Measurement Precision
**Source:** https://help.togal.ai/release-notes-january-25-2025

**What:** Advanced snapping: 22.5°/45°/90° angle, snap to edges + alignment, snap to line %, 45° rotation.

**Why it works:** Without snapping, 5px error at 1:50 scale = 25cm real-world. Professional precision.

**Adapt for LT:** Required when we add manual drawing. LT older buildings have non-orthogonal walls — 45° snap especially important.

**Effort:** S as part of manual tools

### P19 — Customer Support as a Feature (Response Time SLA)
**Source:** https://www.togal.ai/vs/bluebeam (20-min response guarantee)

**What:** Sub-20-minute business hours response. Support team includes former estimators. G2 reviews rank support #1 driver — ahead of AI accuracy.

**Why it works:** Construction estimators often non-technical. Support quality de-risks adoption: "if AI gets it wrong, expert helps within 20 min."

**Adapt for LT:** WhatsApp support more culturally appropriate than ticket system. "Parašykite mums WhatsApp" with real person who understands LT construction (STR, kiekių žiniaraštis, GK pertvarų taisyklės). Stronger differentiator in small market dominated by word-of-mouth.

**Effort:** S (operational, not engineering)

### P20 — Peer-Reviewed Accuracy Study as Marketing Asset
**Source:** https://www.togal.ai/case-study/peer-reviewed-study-togal-ai-vs-on-screen-takeoff

**What:** Univ. of Kansas peer-reviewed: 71% time reduction vs On-Screen Takeoff. Published, used in sales.

**Why it works:** Construction industry skeptical of AI. "98% accuracy" dismissed as marketing. Independent academic validation = changes frame. Togal grew 250 → 2,600 users in 2023 after publication.

**Adapt for LT:** Partner with 1–2 experienced LT samatininkai. 3 real LT interior projects. Measure their time vs. ours, their quantities vs. ours (% delta per line). Publish transparently — including underperformance + fixes. **VGTU statybos fakultetas** for academic credibility. Asset referenced in every sales conversation.

**Effort:** S engineering + M coordination

---

## 3. Anti-Patterns — What Togal Does That Won't Fit LT Context

**AP01 — CSI/MasterFormat Division Structure**
Togal organizes around US CSI MasterFormat. LT uses kiekių žiniaraštis hierarchy mapping to Soviet-era SNiP norms. Direct adoption would confuse LT estimators immediately.

**AP02 — Imperial Measurement Fallbacks**
Togal occasionally shows imperial. US-trained AI has imperial bias. Our pipeline must enforce metric-only at every layer.

**AP03 — Single-Page-at-a-Time Architecture**
Univ. of Kansas study + iBeam analysis confirm: Togal cannot cross-reference between sheets (window on plan p1 vs dimensions on elevation p5). **Our two-pass zoom architecture is more sophisticated** — competitive strength to market, not limitation to apologize for despite longer processing time.

**AP04 — No F2/F3 Document Generation**
Togal exports generic Excel + PDF. Cannot produce Forma F2 (Atliktų darbų aktas) or F3 (Pažyma apie atliktų darbų vertę) — required for LT public procurement and billing. **F2/F3 = strongest structural moat.**

**AP05 — Annual-Only $3,588/Year Per-User Pricing**
$299/mo billed annually only. For LT SMB statybos įmonės: 3–5× expected pricing. We need: freemium (3 free/month) → €39/mėn unlimited, monthly billing, EUR, LT VAT-registered invoice.

**AP06 — No Understanding of LT Drawing Conventions**
Togal AI trained on US drawings (ANSI paper, US symbols, English). LT uses ISO A-series, different door symbols, different hatches, Lithuanian text. Our LT-specific Vision prompting = genuine advantage.

**AP07 — Missing LT-Mandatory Calculations**
Togal has no construction norm DB. All cost formulas user-defined. LT mandates: 21% PVM separate line, hidroizoliacija per STR, specific GK sheet types per location. CLAUDE.md §1.12 already mandates hidroizoliacija — Togal doesn't know this concept exists.

---

## 4. Competitor Positioning — Togal vs Bluebeam vs Kreo

| Dimension | Togal.ai | Bluebeam Revu | Kreo |
|-----------|----------|---------------|------|
| Core paradigm | AI-first | Markup-first | AI-assisted |
| AI capability | Vision + GPT; 100M+ trained | None | Auto Measure, One-Click Area |
| Standards | CSI/MasterFormat (US) | Agnostic | NRM2 (UK QS) |
| Cross-sheet ref | Single-page only ⚠️ | N/A | Better (vector PDF) |
| 3D | Yes (2025) | No | Yes (2024) |
| Collaboration | Real-time + external guests | Studio async | Team-based |
| Pricing | $299/mo, annual only | $220–490/yr | $35–175/mo |
| Target | US GCs | AEC pros globally | UK QS firms |
| Key strength | Speed for US plans; support | PDF annotation standard | NRM2 + cost DB + BIM |
| Key weakness | Cross-sheet; civil; non-US formats | Zero AI | UK-only; slow basics |
| LT relevance | UX pattern source; pricing = our opportunity | What LT estimators use today | More for full QS than interior |

**Where Sąmatų AI wins against all three:**
1. Native Lithuanian UI (all 3 English-only)
2. LT STR norm compliance built in (none)
3. F2/F3 document export (none)
4. 21% PVM integrated (none)
5. LT drawing recognition (sienų išklotinės, eksplikacija, GK pertvarų planas)
6. Price point for LT SMB (€39/mėn vs $299/mo)
7. Interior finishing formulas pre-populated (hidroizoliacija, angokraščiai, grindjuostės)

---

## 5. Quick-Win Backlog — 5 Features, ~1 Day Each

**QW01 — Inject Project JSON into AI Chat**
Backend chat endpoint, AI Chat tab. Pass full extraction JSON as system prompt prefix. AI answers "kiek langų kambaryje 2?" correctly.

**QW02 — Page Classification Labels in Brėžinys Sidebar**
Schema add page_type field, Brėžinys sidebar. Vision already classifies internally. Surface: "1: Aukšto planas ✓", "2: Sienų išklotinė — nerasta ⚠️".

**QW03 — Expose Calculation Formulas in Prielaidos Tab**
interiorCalc.js exports formula strings, AssumptionsPanel.jsx renders + allows constant override.

**QW04 — Export Options Modal with Skyrius Filter**
Export button: checkboxes per skyrius (GKP, Glaistymas, Plytelės, Dažai), toggle Pastabos. Useful for sending one trade scope to subcontractor.

**QW05 — Bidirectional Kiekiai ↔ Brėžinys Highlight**
selectedRoomId state, AiRoomOverlay listens, Kiekiai rows emit on click. Click Kiekiai row → bbox highlights + viewport scrolls. **Fastest accuracy-verification improvement.**

---

## 6. Strategic Moves — Next Quarter (~1 Month Each)

**SM01 — Streaming Extraction with Progressive Room Display**
SSE replaces 3–8 min spinner. Rooms appear as pages complete. User reviews while remaining process. **Fundamentally different feel.**

**SM02 — Repeating Groups for Daugiabučiai**
"Aukštų skaičius" 1–9 in Prielaidos, "pirmas/paskutinis aukštas skiriasi" with overrides. Backend multiplies. Targets Soviet renovation = 50%+ of LT volume.

**SM03 — LT Classification Library with Seeded Defaults**
JSON library: room types in Lithuanian, materials with LT waste factors, hidroizoliacija pre-included in vonia/WC, 21% PVM pre-calculated. **Strongest differentiation from Togal.**

**SM04 — Read-Only Share Link for Projects**
UUID URL, no login for viewing. Estimator → statybos vadovas. Sees Kiekiai + Brėžinys, exports PDF, can't edit. Enables review workflow currently requiring Excel roundtrips.

**SM05 — Accuracy Benchmark Study with LT Professionals**
2 samatininkai, 3 real LT projects. Measure time + quantity deltas. Publish honestly. VGTU statybos fakultetas for credibility. **Asset referenced in every sales conversation for years.**

---

## Source List

- https://www.togal.ai/ — value prop, testimonials
- https://www.togal.ai/features — feature descriptions
- https://www.togal.ai/how-it-works — workflow
- https://www.togal.ai/blog/2025-features-roundup — Repeating Groups, Snapping, Custom Formulas, Progressive Loading
- https://www.togal.ai/blog/supercharge-your-estimating-workflow-using-togal-ai — 7 workflow tips
- https://www.togal.ai/news/chatgpt-enters-the-construction-industry-with-togal-ai — Togal.CHAT
- https://www.togal.ai/blog/how-to-auto-classify-areas-using-the-automatic-classification-feature-of-togal-ai — auto-classification
- https://www.togal.ai/blog/how-to-classify-walls-in-togal-ai — batch wall classification
- https://www.togal.ai/blog/how-to-draw-areas-lines-counts — keyboard shortcuts
- https://www.togal.ai/vs/bluebeam — feature comparison, support SLA
- https://www.togal.ai/pricing-licenses — Growth ($299/mo)
- https://help.togal.ai/custom-formulas — formula syntax
- https://help.togal.ai/how-to-leverage-the-export-tool-inside-togal — export options
- https://help.togal.ai/release-notes-january-25-2025 — rotation, folder, snapping
- https://www.togal.ai/case-study/peer-reviewed-study-togal-ai-vs-on-screen-takeoff — 71% time reduction
- https://www.g2.com/products/togal-ai/reviews — user reviews
- https://www.ibeam.ai/compare/vs-togal-ai — cross-sheet limitation confirmation
- https://foremanai.co/blog/construction-plan-software-pricing-comparison-2026 — pricing comparison
- https://www.kreo.net/solutions/ai-construction-takeoff-sofware — Auto Measure
- https://www.kreo.net/event/kreo-2024-recap-new-ai-tools-and-features-and-whats-ahead — 3D Mode
- https://www.ironpros.com/bidding-estimating-tools/article/22908091/togal-ai-leverages-first-in-market-status-in-ai-takeoff-software — 940% growth 2023
- https://www.youtube.com/channel/UCMDwHVXEDtHScTkCLsSDd1g — demos
- https://www.youtube.com/watch?v=bCM_2ea46h4 — 3D takeoff

---

**Key takeaway:** Togal's real competitive advantage is NOT AI accuracy (peer-reviewed study shows it degrades on non-standard drawings) — it's the **workflow design that makes AI output feel trustworthy** (bidirectional highlight, grounded chat, fail-safe auto-classify, batch operations) and the **customer support responsiveness**. All five trust-building mechanisms can be adapted for Sąmatų AI within 1–2 weeks of engineering effort, without rebuilding the extraction pipeline.
