# Phase C — OpenCV-Based Polygon Detection: Feasibility Study (Path B)

**Date:** 2026-04-29
**Author:** Research subagent (CV focus)
**Audience:** Solo dev + Claude Code, no CV expertise on team
**Companion docs:**
- `2026-04-29-phase-c-libraries.md` (PDF + overlay stack — already locked on react-pdf + Konva)
- `2026-04-29-phase-c-competitor-tech.md` (Togal/Kreo/STACK reverse-engineering)

---

## Executive verdict

**Path B (full automatic OpenCV polygon detection) is a trap for this team. Do not pursue it as the primary solution.**

The honest read of the literature and the competitor stack is unambiguous:

1. **Naive OpenCV pipelines** (Canny + Hough + flood-fill + morphology) work on clean residential plans and fail predictably on commercial Lithuanian project PDFs — the failure modes (open doors, hatching, furniture, multi-line walls, overlapping dimension text) are not solvable by parameter tuning. They require either (a) plan-specific tuning per PDF or (b) ML on top.
2. **Pretrained ML models** (CubiCasa5K, DeepFloorplan, Raster-to-Graph, FloorSAM) all report 85-92% IoU **on their own test splits**, but every paper that does cross-dataset evaluation reports a sharp drop. CubiCasa5K is Finnish residential — **the closest proxy to LT we will find** — and even there real-world post-processed polygon accuracy lands around mean room-IoU 57.5%. Lithuanian commercial/interior projects are out-of-distribution for every published model.
3. **The realistic effort to reach 80% accuracy on standard LT apartment plans** is 4-8 weeks for a CV-experienced developer building a tuned classical pipeline, **3-6 months** for a solo dev without CV expertise, and we should expect a long tail of edge-case PDFs that never converge above 60%. Commercial layouts are not realistic at all without a labeled LT dataset, which we do not have.
4. **The commercially-shipping competitors (Togal, Kreo, STACK) all run server-side ML, and Kreo openly admits it took them U-Net + Mask R-CNN + a bespoke pipeline + their own training corpus to get there.** A solo dev with no labeled LT data has no path to that within a useful timeline.

**What to do instead:** Ship Path A (manual polygon trace with strong UX) **now**, in parallel with a narrow OpenCV-assisted hybrid where deterministic CV is used **only** to (a) snap user clicks to detected wall edges, and (b) suggest candidate polygons that the user can accept/reject — never auto-confirm. This is the same UX pattern Bluebeam Dynamic Fill uses, and it is the only path with a believable 4-6 week ship date for a solo dev. Path C (grid-calibrated Vision) is worth a 2-day spike before committing — see end of doc.

**Bottom line: Path B as a standalone solution = months of work for results worse than Bluebeam's 2018-era flood-fill. Path B as snapping/assist for Path A = a few hundred lines of OpenCV that genuinely help. Pick the second framing.**

---

## Q1 — Browser-side OpenCV (opencv.js)

### Bundle size and load time

- **Current opencv.js (4.x) full build is ~8.1 MB WASM, ~9.0 MB with threads+SIMD.** That is ~3-4× the size of our entire current frontend bundle. On a typical LT broadband (50 Mbps) it is a 1.5-3 s extra cold load; on mobile/coffee-shop wifi it is 5-15 s.
- **You can shrink it by 60-80%** with a custom Emscripten build that whitelists only the modules you need (`imgproc`, `core`, `imgcodecs`). Realistic minimum for our use case (Canny + Hough + findContours + floodFill + morphology) is ~2-3 MB, but **you have to build it yourself from the OpenCV source tree**. There is no NPM package that ships a slimmed build of the modules we want — `TechStark/opencv-js` and `mirada` are full builds.
- The official build script (`platforms/js/build_js.py`) requires Emscripten SDK + Python + a working OpenCV build environment. It is not a 30-minute task. Plan a full day for the first slim build, plus CI integration if we want to keep it slim across upgrades.
- Use `--disable_single_file` so the WASM is loaded as a separate file (browser-cacheable). Without that flag, the WASM is base64-embedded in the JS, which roughly doubles parse time and breaks streaming compilation.

### Memory footprint

- **opencv.js memory leaks are a documented, persistent issue.** GitHub issue #23216 and #20409 both describe `OutOfMemoryError` after extended use even when `.delete()` is called diligently. The Emscripten heap does not shrink — you must manually `cv.Mat.delete()` every temp Mat, and you still observe slow growth.
- For a single 3500×2500×4-channel image (RGBA), the in-heap Mat is ~33 MB. An 8-step pipeline (gray, blur, canny, dilate, contours-temp, mask, fill, output) keeps roughly 4-5 of these alive concurrently → **150-200 MB just for one page processed**. The default opencv.js heap is 128 MB. You need `Module.TOTAL_MEMORY` set to 512 MB+ for this size, which is not available on iOS Safari at all (caps around 200-250 MB before the tab is killed).
- **Verdict on browser memory for a 300 DPI page (3500×2500 px):** workable on desktop Chrome with manual Mat lifecycle discipline; **borderline-unsafe on mobile Safari**; downright dangerous if the user processes more than 2-3 pages in one session.

### Performance on a 300 DPI rendered page

Empirical reference points from the literature:
- **Canny on full image** (3500×2500): ~150-250 ms on a 2022-class M1, 400-700 ms on a mid-range Intel laptop. The WebAssembly slowdown vs native OpenCV is **1.16-1.22×** (Diva-portal benchmark, Chrome 2024 SIMD build), so this is close to native.
- **HoughLinesP** on the same image: 200-400 ms.
- **findContours**: 50-150 ms.
- **floodFill** (single seed): 30-100 ms.
- **Morphological close (5×5 kernel)**: 80-200 ms.
- **End-to-end "find rooms" pipeline**: realistically **1.5-3 s per page** on a mid-range laptop, **4-7 s on a 5-year-old laptop**, and you cannot run it on mobile.

That is just acceptable for "click button, wait 2 s, see polygons" UX. It is **not** acceptable for "live-update on every parameter slider change," which is the natural UX for tuning edge sensitivity. So the in-browser approach also pushes you toward server-side computation if you want a Bluebeam-like edge-sensitivity slider.

### Realistic in-browser operations

| Operation | Realistic in browser? | Notes |
|---|---|---|
| Canny edge detection | yes | First step of every wall-detection pipeline |
| Hough lines (probabilistic) | yes | Useful for axis-aligned wall segments |
| findContours + approxPolyDP | yes | Polygon simplification works fine |
| Morphological open/close | yes | Critical for closing door gaps before flood-fill |
| floodFill | yes | One-click "fill this room" UX |
| Connected components | yes | For separating rooms after fill |
| Distance transform | yes | Needed for adaptive thresholds |
| Mask R-CNN / SAM / U-Net | **no** | None of these run in opencv.js. SAM ONNX in WASM is theoretically possible (~150 MB model + 5-15 s inference), but you'd be loading more than the rest of the app combined |
| Custom CNN inference | partial | TF.js / ONNX Runtime Web exist but are a separate dependency tree |

**Conclusion on Q1:** classical CV in the browser is feasible for assistive tooling (snap-to-edge, suggest-polygon-on-click). Anything that requires processing the entire page to produce all polygons before user interaction is too heavy for this stack and pushes you toward the server.

---

## Q2 — Server-side OpenCV (Python)

### Performance on a $20/mo VPS

A typical $20/mo Hetzner CX22 / DigitalOcean basic droplet = 2 vCPU shared, 4 GB RAM, Linux. For Python+opencv-python:
- Same pipeline above runs in **300-700 ms per page** (no WASM overhead, but slower CPU than your laptop). Memory is ~200-400 MB peak for a 3500×2500 image — fits in 4 GB.
- Concurrency: 2 vCPU = ~2 simultaneous extractions before you queue. For a single-user MVP, fine. Past 5-10 concurrent users you need a worker queue (Celery/RQ + Redis) or you need to scale up.
- Hetzner CX32 ($12-15/mo, 4 vCPU, 8 GB) is a strictly better deal than DO basic at this size class — recommend that instead of $20 DO.

### Roundtrip cost (PDF → PNG → OpenCV → polygons → frontend)

Current pipeline already does PDF→PNG (via pdfplumber/pdf2image) at extraction time. So the marginal cost of adding OpenCV is:
1. Re-load the rendered PNG (already on disk if cached): ~50 ms
2. Run OpenCV pipeline: 300-700 ms
3. Polygon JSON serialize + return: <10 ms
4. Network roundtrip: 50-200 ms LT→DE/Frankfurt

**Total: ~0.5-1 s extra per page** on top of the existing extraction call. That is fine for a one-time "detect rooms" action; it is too slow for live slider tuning.

### Caching

- **Cache the rendered PNG by PDF hash + page index + DPI.** We already do something close to this for `/extract-interior` page rendering — extend it.
- **Cache OpenCV intermediate results** (gray + canny + morphological-closed) per page — they are deterministic given the input PNG and parameters. Hash on (png_hash, params_hash). Stored as numpy `.npz` or PNG, ~1-3 MB each.
- **Cache final polygon JSON** per (png_hash, params_hash). <50 KB.
- Storage: ~5 MB per page processed. A 100-page PDF = 500 MB cache. On a $20 VPS with 80 GB SSD, fine for ~150 active projects, then we LRU-evict.
- **Recommended:** Redis for cache index + polygon JSON, filesystem for intermediate PNGs, keyed on SHA-256 of PNG + params blob.

### Verdict

Server-side beats browser-side for everything except "single-click snap" interactions. **The right architecture is: server computes polygon candidates once on demand; browser uses a tiny opencv.js subset (or even pure-JS) for click-time snapping.** Trying to put the whole pipeline in the browser only saves the developer some backend code and costs the user 7 MB of bundle.

---

## Q3 — Floor plan vectorization research (academic + open source)

### State of the art (2022-2026)

| Method | Year | Approach | Reported accuracy | OOD risk for LT |
|---|---|---|---|---|
| **Raster-to-Vector** (Liu et al.) | 2017 | Junction detection + integer programming | 90% precision (own dataset) | High — trained on R3D Asian residential |
| **CubiCasa5K + improved multi-task model** (Kalervo et al.) | 2019 | Multi-task CNN, room/wall/icon heads | mean room-IoU **57.5%** on real estate test set | Lower (Finnish residential = closest to LT we'll find) but still fails on commercial |
| **DeepFloorplan** (Zeng et al., ICCV 2019) | 2019 | Multi-task with room-boundary attention | ~88-90% pixel acc on R2V/R3D | High — in-distribution only |
| **R-FP** (Lv et al., CVPR 2021) | 2021 | Cascade detection + graph reasoning | ~92% on residential | High |
| **Raster-to-Graph** (Hu et al., EG 2024) | 2024 | Autoregressive Transformer, graph prediction | Edge-F1 **96.1** on LIFULL (10k Japanese plans) | Very high — Japanese style is far from LT |
| **FloorSAM** (2025) | 2025 | SAM-guided + LiDAR fusion | precision/recall >0.90 | Requires LiDAR — irrelevant to us |
| **FloorplanVLM** (arxiv 2026) | 2026 | VLM + geometric reasoning | 92.5% external-wall IoU | New, no real-world deployment data; OOD risk unknown |
| **Multibranch+attention framework** (De Nardin, Wiley 2025) | 2025 | Multibranch CNN + attention | new SOTA on R2V/R3D | Same OOD problem |
| **Sparse point set vectorization** (Wei et al. 2025) | 2025 | Quartet of points, no semantic seg | strong on LIFULL | Same OOD problem |

**Key insight from the literature:** every paper reports ≥85% on its own test split. None of them publish numbers on Lithuanian or Eastern European architectural plans, and the few cross-dataset studies show big drops (CubiCasa→R3D is the documented case where annotation quality differences alone cause significant accuracy loss).

### Pretrained models — what is actually downloadable and usable

| Model | License | Pretrained weights | Inference speed | Setup cost |
|---|---|---|---|---|
| `art-programmer/FloorplanTransformation` | MIT | yes (Google Drive, Torch) | ~2-3 s/page on CPU | Torch dep, old code, last update 2018 |
| `zlzeng/DeepFloorplan` | Apache 2 | yes (TF1) | ~1-2 s/page | TF1 — needs porting to TF2 (`zcemycl/TF2DeepFloorplan` or `JulianJuaner/DeepFloorPlan_Pytorch` exist) |
| `CubiCasa/CubiCasa5k` | CC BY 4.0 (data); MIT (code) | yes (PyTorch) | ~1 s/page on GPU, 5-10 s CPU | Cleanest setup of the bunch |
| `xmarva/floorplan-detection` | MIT | trained on CubiCasa via MMDetection | 2-3 s/page | Needs MMDetection (heavy install) |
| `SizheHu/Raster-to-Graph` | research | yes (LIFULL-trained) | slower (autoregressive) | Newest, complex setup |
| `RasterScan/Floor-Plan-Recognition` | unclear | "on-premise" — unclear weights | unknown | Avoid (license unclear) |

**Realistic option for us:** the `zcemycl/TF2DeepFloorplan` repo is the most production-friendly — it has TF Lite export, a Flask wrapper, Docker, and Colab notebooks. CubiCasa5K is the most architecturally relevant (Finnish ≈ LT in convention). Either one can be running on our backend in **2-3 days**.

### How well do these handle Lithuanian plans?

**They will not handle Lithuanian commercial / interior projects acceptably.** Specific reasons:

1. **Drawing convention drift.** LT plans use ISO 128 / EN-style hatching for materials (railiavimas), thicker exterior walls, dimension chains laid in tight rows close to walls, room labels often in a separate eksplikacija table not inside the polygon. CubiCasa5K is real-estate marketing material — clean, single-line walls, room labels inside, no dimension chains. Models overfit to clean plans hallucinate walls where there are dimension chains and miss walls where there is hatching.
2. **Symbol inventory mismatch.** Doors swing arcs in LT plans use a different convention than Finnish/Japanese. Door/window detection is brittle to symbol style (Mask R-CNN trained on Asian doors barely fires on LT doors).
3. **Furniture in interjero projektai.** CubiCasa5K plans have minimal furniture. LT interior projects (our primary use case!) are dense with furniture, fittings, plumbing fixtures. These confuse contour-based room extraction and confuse CNN room-segmentation heads (the model was never shown rooms full of furniture).
4. **Multi-line wall representation.** Heavier LT exterior walls are drawn as 2-3 parallel lines with hatch fill between. To a CNN trained on single-line walls, this looks like 2 rooms separated by a thin space.
5. **Eksplikacija-based labeling.** The label "Sandėliukas" might not appear inside its polygon at all — it's only in the schedule. This breaks any pipeline that uses inside-polygon OCR for room classification.

**Bottom line:** the models give us a starting point, not a solution. Expect 40-60% real-world accuracy on LT plans without fine-tuning, 70-80% with fine-tuning on a labeled LT dataset (which we'd have to build — minimum 200-500 annotated LT plans, which alone is 60-100 hours of labeling).

---

## Q4 — Specific challenges for Lithuanian project PDFs

These are the failure modes a deterministic OpenCV pipeline must handle. None are solved by parameter tuning alone:

1. **Thick exterior + thin interior walls.** Hough/Canny pipelines have to threshold at two different line weights or run twice. Solvable, but it doubles complexity.
2. **Hatching for materials.** Diagonal hatch fill inside walls produces hundreds of tiny line segments that drown out the actual wall outline. **Mitigation:** apply a directional morphological closing oriented along principal wall axes (horizontal + vertical), then erase non-axis-aligned line segments. This works for orthogonal plans but breaks on rotated / non-orthogonal layouts (common in commercial).
3. **Dimension text and dimension chains.** OCR + erase before CV pipeline. Practical: run Tesseract on the page, mask the text bounding boxes to white, then run wall detection. This is **mandatory** for LT plans — without it, dimension characters become "rooms."
4. **Door openings break wall closure.** A swing arc + 80 cm gap = unclosed polygon = floodFill leaks into the corridor. **Standard fix:** morphological closing with kernel size > door width in pixels (typical: 35-50 px at 300 DPI). Side effect: can fuse rooms separated only by thin partition walls (e.g., bathroom-WC adjacency). Single global kernel is wrong; needs per-region adaptation, which is where the engineering complexity explodes.
5. **Furniture symbols inside rooms.** Confuses contour finding (false inner contours). **Mitigation:** filter contours by area, but that loses small actual rooms (sandėliukas = ~1.5 m² = surprisingly small at our scale).
6. **Eksplikacija labels outside polygons.** The room schedule (eksplikacija) lists rooms by number. Numbers inside polygons map to schedule rows. **Mitigation:** OCR detects in-polygon numbers, then a separate parser reads the eksplikacija table. We already have `pdfplumber_eksplikacija.py` and `eksplikacija_reader.py` — those are reusable here.
7. **Multi-floor plans on one page.** One PDF page sometimes shows ground + first floor side-by-side. Naive flood-fill bleeds across the gap. Need page-region segmentation first (find the "boxes" enclosing each plan).
8. **Scale + orientation drift.** Different pages have different scales/rotations. Wall thicknesses change. Closing kernel size must be adaptive based on detected wall thickness or scale bar. We already have `ScaleCalibrationModal.jsx` — exploit user-provided calibration to set kernel sizes deterministically per page.

**The critical realization:** items 3 (text masking), 6 (eksplikacija binding), 8 (scale-aware kernels) are unique to LT/AEC plans. None of the open-source pretrained models handle them. We'd be building this LT-specific glue on top of the model regardless. So the model is doing maybe 60% of the work; we're doing the LT-specific 40% either way.

---

## Q5 — Hybrid approach (CV finds polygons, Vision labels them)

**This is the single best architectural idea in this whole document.** It separates the two things LLMs are bad at vs good at:

| Task | Vision LLM | OpenCV |
|---|---|---|
| Pixel-precise geometry | bad (current bbox_pct disaster) | good (deterministic) |
| Reading a Lithuanian label "Sandėliukas" inside a polygon | great | impossible |
| Counting doors | medium | brittle but doable |
| Identifying that polygon is a bathroom from fixtures | great | hard |
| Confidence calibration | hallucinates | predictable |

### Proposed pipeline (LT-tuned)

```
1. PDF page → 300 DPI PNG (existing)
2. OCR pass (Tesseract LT): extract text bounding boxes, save text+location, mask out
3. Adaptive threshold + morphological closing (kernel size from scale calibration)
4. Connected-components / floodFill from interior seed points
5. Filter components by area (>= 1.0 m² in real units, < total page × 0.6)
6. Polygon extraction (findContours + approxPolyDP epsilon ~0.5% of perimeter)
7. For each polygon: crop a region with 30 px padding → send to Vision with
   prompt "What room type is this and what is its label number?"
8. Bind Vision labels back to eksplikacija via existing eksplikacija_reader
9. Return {polygon_pixels, polygon_world, room_label, room_type, confidence}
```

This is 80% of what Bluebeam Dynamic Fill does, plus the labeling-only Vision call (which is what Vision is actually good at). Expected accuracy on **standard LT apartment plans**: 70-85% polygons correct on first try, with the user fixing the rest in Path A's manual editor. On **commercial plans**: 30-50% — still useful as a starting point if the UI clearly shows "we're guessing, please verify."

### Failure mode if walls aren't closed (gaps at doors)

This is the make-or-break issue. Three strategies:

1. **Aggressive morphological closing** (kernel ≥ door width). Works on apartments. Fails on bathroom-WC adjacency (those merge into one polygon).
2. **Door detection + virtual wall insertion.** Detect door symbols (swing arcs), draw a virtual wall across the opening before flood-fill. Symbol detection can be a small Mask R-CNN or template matching against a curated LT door symbol library (we'd build this — ~2 weeks of work + a labeled set of LT door symbols).
3. **User gap-bridging (Bluebeam's escape hatch).** When auto-fill fails, user clicks two points to draw a "boundary segment," then re-runs flood-fill. This is the pragmatic backstop and is the same UX Bluebeam ships. **Recommended as the v1 fallback** because it always works and keeps the user in control.

The honest answer: there is no parameter set that handles open doors perfectly. Strategy 3 must exist as a fallback even if you build 1+2. Build 3 first.

---

## Q6 — Realistic effort estimate

### Solo dev + Claude Code, no CV expertise

**To get 80% accuracy on standard LT apartment floor plans:**

| Approach | Realistic time | Confidence |
|---|---|---|
| Pure classical CV (Canny + Hough + flood-fill + morphology + LT-specific text masking + scale-aware kernels) | **6-10 weeks** | medium-low; 80% is a stretch goal, 65% is more honest |
| Pretrained model (CubiCasa5K) + LT-specific post-processing + text masking | **3-5 weeks** | 70-75% on apartment-style plans; commercial fails |
| Pretrained model + fine-tune on LT data | +**4-6 weeks for dataset labeling and training** on top of above | 80-85% if dataset is ≥300 plans and labels are clean |
| Hybrid (OpenCV polygons + Vision labels) without ML | **4-6 weeks** | 70-80% on apartments, 35-50% on commercial |
| Path A (manual trace) with great UX + snap-to-edge | **2-3 weeks** | 100% accuracy by definition; cost is user time per project |

**To handle commercial / complex layouts: not realistic without a labeled LT commercial dataset and likely a CV consultant.** Expect ≥3 months of part-time work just to get past the embarrassment threshold (≥60% polygons correct without obvious errors), and that's optimistic. The literature is clear: even SOTA papers don't ship commercial results because their datasets don't include them.

### Risk summary

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pipeline accuracy plateaus at 50-60% on real LT projects | high | kills feature credibility | Position auto-detect as "suggestions, please verify" — never auto-confirm |
| opencv.js bundle blows up first-load metric | medium | hurts SEO + perceived perf | Server-side OpenCV; tiny opencv.js subset only for snapping |
| Memory leaks in opencv.js cause production crashes | medium-high | user-facing crashes | Avoid opencv.js for batch work; use it only for short-lived per-click ops |
| Pretrained model license forces source disclosure | low | legal | CubiCasa5K data is CC BY 4.0 (attribution OK), most code Apache/MIT — check each before shipping |
| Door-gap closing fuses rooms unintentionally | high | wrong totals | User fallback: "draw boundary line" tool (Bluebeam pattern) |
| Solo dev gets stuck on a single hard PDF for 2 weeks | very high | calendar slip | Time-box per-PDF debugging to 4 hours; if not solved, manual fallback wins |
| Fine-tuning requires labeled LT data we don't have | very high if pursued | blocks ML path | Ship Path A first, collect user-corrected polygons as training data over months |

---

## What could go wrong (honest)

1. **The "AI Vision will solve it" trap repeats with "OpenCV will solve it."** Both are true on toy examples and false on real customer PDFs. Expect a six-week project to take three months.
2. **The two-line wall problem.** LT exterior walls drawn as parallel lines with hatching produce two parallel polygons (an "outer" wall ring and "inner" wall ring) and floodFill fills the *space between them* as if it were a room. Specific known failure mode in Bluebeam Dynamic Fill on LT plans — Bluebeam users routinely have to hand-correct this.
3. **OCR on Lithuanian characters in dimension text.** Tesseract's Lithuanian language pack is OK but small mis-recognitions of `ą/a`, `š/s` happen. For text-masking that's fine (we just need the bbox, not the chars), but if you start using OCR for room-label binding you'll have to QA the LT pack output.
4. **Memory leaks in opencv.js will bite during user testing.** Issue #23216 specifically reports leaks despite diligent `.delete()` calls. Plan a memory-watchdog timer that reloads opencv.js (yes, the whole module) every N minutes if heap grows — ugly but documented as the only reliable fix.
5. **Polygon-coordinate space mismatches.** PDF coords vs PDF.js viewport coords vs our canvas overlay coords vs mm-real-world coords. Four spaces, all conversions are sources of bugs. We already had this mess with `bbox_pct`; do not repeat. Settle on one canonical space (recommend: PDF page points, 1/72 inch) and convert at every boundary.
6. **The "standard apartment" assumption is narrower than it sounds.** P1, P2, T1, T2, T3, T4, T5, T6, T7 — out of these, ~3 are "standard apartment-like." The rest are commercial or interjero with heavy furniture. Designing the pipeline only for the 3 nice ones and breaking on the rest is the predictable trap.
7. **Pretrained model licensing is messier than people admit.** CubiCasa5K data is CC BY 4.0 (commercial OK with attribution), DeepFloorplan code is Apache (OK), but **R3D and LIFULL are research-only**. If your model was trained on those, downstream commercial use is in a grey zone. Check each weights file's actual provenance before shipping.
8. **Path A becomes harder to ship if Path B is "almost working."** Sunk-cost trap: 6 weeks into the OpenCV pipeline with 65% accuracy, the temptation is "one more week and we'll hit 80." Don't. Ship Path A no matter what Path B does.

---

## Specific tool / library recommendations (if hybrid path is pursued)

### Server-side (Python, FastAPI — already our stack)

- `opencv-python-headless==4.10.x` — server CV. Avoid full `opencv-python` (drags in GTK on Linux).
- `numpy` (already there)
- `pytesseract` + `tesseract-ocr-lit` (Debian package) for LT text masking
- `shapely` for polygon ops (intersection, simplification, area in real units)
- `pdf2image` (already there) — keep at 300 DPI for now; consider 200 DPI as a perf optimization once accuracy is locked
- **For pretrained model path:** start with `zcemycl/TF2DeepFloorplan` (TF2 + Flask wrapper, easiest setup) before trying CubiCasa5K's PyTorch repo. Run on CPU; GPU is overkill for our query volume.

### Client-side (only if opencv.js is needed for snapping)

- **Do not use full `opencv.js` from CDN.** Build a slim version (`core` + `imgproc` + `imgcodecs` only). Target <2 MB.
- Wrap it in a Web Worker so the main thread stays responsive.
- Provide a `loadOpenCV()` lazy-loader, only initialized when user opens the polygon editor. Most users on a takeoff project never need it.
- Use `paper.js` (already mentioned in `phase-c-libraries.md`) for client-side polygon boolean ops — much smaller than dragging in OpenCV just for that.

### Hybrid storage

- Polygon JSON in Postgres (when we move off localStorage) as `jsonb` column on the room/page row. ~5-50 KB per page.
- OpenCV intermediates cached on disk by `(pdf_sha256, page_index, dpi, params_hash)` key.

---

## Recommended path forward

1. **Ship Path A (manual polygon trace) in 2-3 weeks** as the always-works baseline. This is the floor of what we can deliver.
2. **Spike Path C (grid-calibrated Vision) for 2 days** before committing to anything more. If we overlay a numbered coordinate grid on the rendered PDF and ask Vision to return polygons in grid coordinates instead of percentages, we may dramatically cut the bbox_pct disaster without any CV work. This is the cheapest experiment in the space and we have not run it.
3. **If Path C does not get to 80%, build the hybrid OpenCV+Vision pipeline server-side** (4-6 weeks). Use it only as "suggested polygons" in Path A's editor. Never auto-confirm.
4. **Do not attempt pretrained model fine-tuning until we have ≥200 labeled LT plans**, which we will only get from users actually using Path A and us harvesting their corrections.
5. **Re-evaluate purchasing Apryse / Bluebeam SDK at €60k ARR or 200 paying users** (per `phase-c-libraries.md` recommendation). Their measurement tooling beats anything we'd build in 2026, and at that revenue scale the $5-15k/yr is a rounding error.

---

## Sources

### Browser-side opencv.js
- [OpenCV: Build OpenCV.js docs](https://docs.opencv.org/4.x/d4/da1/tutorial_js_setup.html)
- [OpenCV: Using OpenCV.js](https://docs.opencv.org/4.x/d0/d84/tutorial_js_usage.html)
- [Issue #23216: opencv.js OutOfMemoryError after extended use](https://github.com/opencv/opencv/issues/23216)
- [Issue #20409: opencv.js memory leak with `new cv.Mat()`](https://github.com/opencv/opencv/issues/20409)
- [Issue #21431: partly built opencv.js size is too big](https://github.com/opencv/opencv/issues/21431)
- [Reducing opencv.js bundle size — Q&A](https://answers.opencv.org/question/181963/decreasing-size-of-opencvjs/)
- [Memory management in opencv.js](https://answers.opencv.org/question/223059/memory-management-in-opencvjs/)
- [TOTAL_MEMORY for OpenCV JS](https://answers.opencv.org/question/207044/how-to-increase-total_memory-for-opencv-js/)
- [OpenCV.js webcam filters performance](https://opencv.org/blog/opencv-js-real-time-webcam-filters/)
- [How to custom build OpenCV.js (and slim it down)](https://medium.com/@jinkawin.p/how-to-custom-build-opencv-for-javascript-and-slim-it-down-c9f832c1dcd5)
- [WebAssembly performance evaluation (DiVA)](https://www.diva-portal.org/smash/get/diva2:1764648/FULLTEXT02.pdf)
- [OpenCV and WebAssembly — Omar Islas](https://www.oislas.com/blog/opencv_wasm/)

### Server-side OpenCV pipeline
- [Find contours for walls in floor plan images](https://forum.opencv.org/t/find-contours-for-walls-in-floor-plan-images/11640)
- [Floor Plan Recognition with CV — Maik Paixão](https://medium.com/@maikpaixao/an%C3%A1lise-de-plantas-baixas-usando-intelig%C3%AAncia-artificial-40fa12e339be)
- [OpenCV floodFill official sample](https://github.com/opencv/opencv/blob/master/samples/python/floodfill.py)
- [Filling holes with OpenCV — LearnOpenCV](https://learnopencv.com/filling-holes-in-an-image-using-opencv-python-c/)
- [Hough Line Transform — OpenCV docs](https://docs.opencv.org/3.4/d9/db0/tutorial_hough_lines.html)
- [Autonomous Room Detection in Floor Plans Pt 3 — Ivanovich](https://ivanovi.ch/blog/2019/12/how-heatmap-works-3/)

### Floor plan vectorization research
- [CubiCasa5K dataset + paper (Springer)](https://link.springer.com/chapter/10.1007/978-3-030-20205-7_3)
- [CubiCasa5K GitHub](https://github.com/CubiCasa/CubiCasa5k)
- [CubiCasa5K dataset overview (Emergent Mind)](https://www.emergentmind.com/topics/cubicasa5k-dataset-1b6b7d61-dd68-406e-aa2a-87eb0dd79b93)
- [Raster-to-Vector: Revisiting Floorplan Transformation (Liu et al.)](https://github.com/art-programmer/FloorplanTransformation)
- [Raster-to-Vector project page](https://art-programmer.github.io/floorplan-transformation.html)
- [DeepFloorplan (Zeng et al., ICCV 2019)](https://github.com/zlzeng/DeepFloorplan)
- [DeepFloorplan ICCV paper PDF](https://openaccess.thecvf.com/content_ICCV_2019/papers/Zeng_Deep_Floor_Plan_Recognition_Using_a_Multi-Task_Network_With_Room-Boundary-Guided_ICCV_2019_paper.pdf)
- [TF2DeepFloorplan (production-friendly fork)](https://github.com/zcemycl/TF2DeepFloorplan)
- [PyTorch-DeepFloorplan](https://github.com/zcemycl/PyTorch-DeepFloorplan)
- [Raster-to-Graph (EG 2024)](https://github.com/SizheHu/Raster-to-Graph)
- [Raster-to-Graph paper (Wiley CGF)](https://onlinelibrary.wiley.com/doi/10.1111/cgf.15007)
- [FloorSAM: SAM-Guided Floorplan Reconstruction (arxiv 2025)](https://arxiv.org/abs/2509.15750)
- [FloorplanVLM: VLM for Floorplan Vectorization (arxiv 2026)](https://arxiv.org/abs/2602.06507)
- [Multibranch + multiattention framework (Wiley 2025)](https://onlinelibrary.wiley.com/doi/10.1111/mice.70030)
- [Comprehensive floor plan vectorization with sparse points (ScienceDirect 2025)](https://www.sciencedirect.com/science/article/abs/pii/S0926580525000639)
- [Few-shot foundation models for floor plans (ScienceDirect 2024)](https://www.sciencedirect.com/science/article/pii/S2772991524000562)
- [Multi-Unit Floor Plan Recognition (arxiv 2024)](https://arxiv.org/html/2408.01526v1)
- [Wall polygon retrieval from floor plans (U. Chile thesis)](https://repositorio.uchile.cl/bitstream/handle/2250/196842/Wall-polygon-retrieval-from-architectural-floor-plan-images-using-vectorizacion-and-Deep-Learning-methods.pdf?sequence=1&isAllowed=y)
- [Residential Floor Plan Recognition and Reconstruction (CVPR 2021)](https://openaccess.thecvf.com/content/CVPR2021/papers/Lv_Residential_Floor_Plan_Recognition_and_Reconstruction_CVPR_2021_paper.pdf)
- [Hierarchical IoU evaluation for floor plan vectorization (ASCE)](https://ascelibrary.org/doi/abs/10.1061/JCCEE5.CPENG-6434)
- [ResPlan: 17,000 Residential Floor Plans dataset (arxiv 2025)](https://arxiv.org/pdf/2508.14006)
- [floorplan-detection (MMDetection on CubiCasa)](https://github.com/xmarva/floorplan-detection)

### Industry context
- [Kreo: Floor Plan Recognition Technologies](https://www.kreo.net/news-2d-takeoff/floor-plan-recognition-technologies)
- [Kreo: Auto Measure 2.0](https://www.kreo.net/news-2d-takeoff/auto-measure-2-0)
- [Eano: AI Construction Takeoff strengths and limitations](https://www.eano.com/blogs/ai-construction-takeoff-software-what-it-gets-right-and-where-it-still-falls-short)
- [Bluebeam Dynamic Fill official docs](https://support.bluebeam.com/online-help/revu21/Content/RevuHelp/Menus/Tools/Measure/Dynamic-Fill--T.htm)
