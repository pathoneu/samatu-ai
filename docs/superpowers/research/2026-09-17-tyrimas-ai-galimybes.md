<!-- Tyrimo agento ataskaita (EN), 2026-09-17. Užsakyta Pathon Patikros tyrimui; žr. 2026-09-17-patikra-visapusiskas-tyrimas.md -->

# Machine reading of floor plans for quantity takeoff — state of the art, 2025–2026

## Executive summary

1. Frontier VLMs read **text** on drawings well (OCR-type QA 0.70–0.95) but **count symbols badly**: on 120 floor plans the best model, Gemini 3 Pro, hits only 0.39 exact-match on doors and 0.34 on windows (MAPE 15–20 %); Claude Opus 4.5 is at 0.16/0.16 (MAPE 31–37 %) ([AECV-Bench](https://arxiv.org/pdf/2601.04819)).
2. Room-level concepts anchored by labels (bedrooms, toilets) are fine (0.89–0.91 exact-match) — the bottleneck is graphical symbol interpretation, not reading ([AECV-Bench](https://arxiv.org/pdf/2601.04819)).
3. For **area**, scale is the killer: in a 15-plan micro-eval, >70 % of the area error of GPT-5.5 / Claude Opus 4.8 / Claude Fable 5 (23.2 % / 13.2 % / 6.5 % mean error) came from mis-estimating scale, not from marking rooms ([Staley 2026](https://kerrickstaley.com/2026/07/01/floor-plan-area-micro-eval)).
4. Techniques with measured gains: learned crop/zoom (+7.5 to +14.9 pp on TextVQA/DocVQA/InfoVQA for Qwen2.5-VL-3B, [CropVLM](https://arxiv.org/html/2511.19820)); multi-turn zoom agents (V* 75.5→88.2 for a 7B model, [Mini-o3](https://arxiv.org/html/2509.07969v1)); giving the model the **vector SVG alongside the PNG** (GPT-4o room-count accuracy 0.75→0.96, [SVG decomposition study](https://arxiv.org/html/2511.03478v1)).
5. The only published system beating human estimators on takeoff is a CV-primitives + tool-using-agent stack, not a bare VLM: 81.6 % composite vs 77.6 % human vs 61.4 % for the best frontier agent ([Handoff-H1](https://arxiv.org/html/2608.15032)).
6. Specialised raster→vector models are strong on clean plans (Raster2Seq Room-F1 88.7 on CubiCasa5K, weights public) but drop to 73.9 % IoU on in-the-wild plans ([Raster2Seq](https://www.alphaxiv.org/overview/2602.09016), [GitHub](https://github.com/Cornell-VAILab/Raster2Seq)). RoomFormer/HEAT/PolyRoom take point-cloud density maps, not drawings.
7. Vector-native segmentation beats raster nets on the same data: +4–5 mIoU and +25 pts "room integrity" on CubiCasa-5k ([VectorFloorSeg](https://openaccess.thecvf.com/content/CVPR2023/papers/Yang_VectorFloorSeg_Two-Stream_Graph_Attention_Network_for_Vectorized_Roughcast_Floorplan_Segmentation_CVPR_2023_paper.pdf)); every commercial tool treats vector PDFs as the accurate path ([Togal](https://www.togal.ai/blog/ai-blueprint-reading-accuracy), [Bluebeam](https://novedge.com/blogs/design-news/bluebeam-tip-enable-snap-to-content-for-faster-more-accurate-takeoffs)).
8. Independent takeoff accuracy: Togal.AI vs a contractor's 29-item finishes takeoff ran −1 % to −11 % on floors/ceilings with a statistically significant **underestimation** bias on areas (p = .027) ([Sadeh et al.](https://easychair.org/publications/paper/pkrRp/open)); a university study found ~70 % time saving at within-5 % after manual fixes ([KU/Togal](https://www.togal.ai/case-study/peer-reviewed-study-togal-ai-vs-on-screen-takeoff)).
9. No independent time-to-verify number exists; vendor studies quote 30 s/page processing and "2–3 h head start" ([ConstructConnect](https://www.constructconnect.com/blog/are-ai-takeoffs-accurate-in-2026)).
10. Recommendation for Pathon: (a) vector-first room polygons from the PDF path layer, (b) dimension-string cross-check as a hard constraint, (c) ≥300-dpi crop loop for the reads that stay visual, (d) a small detector for doors/windows with VLM verification, (e) explicit measurement convention (internal finished face, NRM2 opening threshold) with evidence crops.

---

## 1. Vision-language models on floor plans

| Benchmark | Data | Best result | Claude | Notes |
|---|---|---|---|---|
| [AECV-Bench](https://arxiv.org/pdf/2601.04819) (Jan 2026) counting | 120 plans (CubiCasa5K, CVC-FP, web) | Gemini 3 Pro 0.51 mean exact-match; doors 0.39, windows 0.34, bedrooms 0.89, toilets 0.82; MAPE 16.0 % | Opus 4.5: 0.42 mean; doors 0.16, windows 0.16; MAPE 24.9 % (windows 37.3 %) | GPT-5.2: 0.49 / 19.4 %. One fixed prompt, JSON output, whole sheet, no tiling |
| AECV-Bench document QA | 21 drawings, title blocks/schedules/scales | OCR 0.70–0.95; spatial 0.6–0.78; counting worst | — | "bottleneck lies not in reading text but in understanding the graphical language" |
| [ArchSIBench](https://arxiv.org/html/2605.20837) (May 2026) | 3,000 MCQ | Gemini-3-Pro 77.9 %; humans 85.1–89.2 % | Opus 4.5/4.6 tested, below Gemini (exact figure not extracted) | Perception is the weakest axis: best VLM 67.5 % vs trained humans 87.0 % |
| [ArchPlanVQA](https://ascelibrary.com/doi/abs/10.1061/JCCEE5.CPENG-7571) (JCCE 2026) | CAD floor-plan VQA | General VLMs 33.0–37.9 % semantic accuracy | not extracted | paywalled |
| [Area micro-eval](https://kerrickstaley.com/2026/07/01/floor-plan-area-micro-eval) (Jul 2026) | 15 plans × 4 runs, agents with code exec | Claude Fable 5 6.5 % mean error | Opus 4.8 13.2 %; GPT-5.5 23.2 % | >70 % of error from scale; one mislabeled dimension (20′ vs ~10′10″) fooled all models |
| [Blueprint-Bench](https://arxiv.org/abs/2509.25229) | photos→plan, 50 flats | most models ≤ random | Claude 4 Opus tested | agents "no meaningful improvement" |

**Failure modes named in the literature:** misread door swings, windows confused with openings/façade lines, hallucinated fixtures, missed instances in dense regions ([AECV](https://arxiv.org/pdf/2601.04819)); scale mis-estimation and trusting an erroneous dimension label ([Staley](https://kerrickstaley.com/2026/07/01/floor-plan-area-micro-eval)); zero-shot Claude 3.5 Sonnet had the highest hallucination rate on GD&T extraction, and a fine-tuned 0.23B Florence-2 cut hallucination by 43 % and raised F1 by 52 % ([arXiv 2411.03707](https://arxiv.org/abs/2411.03707)); Anthropic's own docs warn counts are approximate "especially with large numbers of small objects" ([Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)).

**Resolution ceiling (arithmetic, from vendor docs):** Claude downsizes to a 1568 px long edge on standard-tier models, 2576 px on Claude 4.7+ ([Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)); an A3 sheet (420 mm) therefore lands at 3.7 or 6.1 px/mm, so 2 mm dimension text becomes ~7–12 px tall. Gemini scales PDF pages to max 3072×3072 at 258 tokens/page ([Gemini docs](https://ai.google.dev/gemini-api/docs/document-processing)). "Native PDF" input in Claude means each page is rasterised to an image plus extracted text — no vector geometry reaches the model ([PDF support docs](https://platform.claude.com/docs/en/build-with-claude/pdf-support)). Measured native-PDF-vs-image gains on floor plans: **not found**.

**Techniques with measured gains:**

| Technique | Evidence | Gain |
|---|---|---|
| One learned high-res crop + global view | [CropVLM](https://arxiv.org/html/2511.19820) | Qwen2.5-VL-3B: DocVQA 69.5→84.4, InfoVQA 44.0→56.0, TextVQA 68.2→75.7 |
| Multi-turn zoom-in agent (RL) | [Mini-o3](https://arxiv.org/html/2509.07969v1) | 7B: V* 75.5→88.2, HR-Bench-8K 68.2→77.5; accuracy keeps rising from 4 to 32 turns |
| SVG primitives + PNG to the LMM | [SVG decomposition](https://arxiv.org/html/2511.03478v1) | GPT-4o room count 0.75→0.96; Claude 3.7 path-finding 54.7→72.6 %; Llama 3.2 11B degrades |
| Detector + LLM chain-of-thought counting | [arXiv 2509.17283](https://arxiv.org/html/2509.17283) | Co-DETR + GPT-5: toilet enumeration 79.3→85.7 (FloorPlanCAD), 58.0→71.6 (SydneyHouse) |
| CV primitives + tool-using agents (crop/zoom/pan/count) | [Handoff-H1](https://arxiv.org/html/2608.15032) | 81.6 % vs 61.4 % for best frontier agent (Claude Fable-5); drywall trade 85 % vs 52 % |
| Self-consistency voting on counts | — | **not found** for drawings; generic multimodal self-consistency ≤ +7.7 pp ([survey](https://www.emergentmind.com/topics/self-consistency-sampling)) |
| Structured outputs | [Let Me Speak Freely](https://arxiv.org/pdf/2408.02442), [ExtractBench](https://arxiv.org/abs/2602.12247) | Format constraints degrade reasoning; 0 % valid output on a 369-field schema for GPT-5.2/Gemini-3/Claude 4.5 — keep schemas narrow |

## 2. Specialised models

| Model | Input | Benchmark → metric | Weights |
|---|---|---|---|
| [CubiCasa5K](https://ar5iv.labs.arxiv.org/html/1904.01920) (2019) | raster | rooms mIoU 57.5 %; doors 69.2, windows 53.6 IoU | [yes](https://github.com/CubiCasa/CubiCasa5k) |
| CAB2 ([arXiv 2408.01526](https://arxiv.org/html/2408.01526v1)) | raster, refined CubiCasa | walls 0.83, doors 0.70, windows 0.82 IoU (baseline 0.73/0.53/0.66) | not stated |
| [Raster-to-Vector](https://github.com/art-programmer/FloorplanTransformation) (2017) | raster | "~90 % precision/recall" | yes |
| HEAT / RoomFormer / PolyRoom / SLIBO-Net ([PolyRoom tables](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/06708.pdf)) | **point-cloud density maps** | Structured3D room-F1 95.4 / 97.3 / 98.3 / 98.4; SceneCAD room IoU 84.9 / 91.7 / 92.8 | [RoomFormer](https://github.com/ywyue/RoomFormer), [PolyRoom](https://github.com/3dv-casia/PolyRoom/) yes |
| [Raster2Seq](https://github.com/Cornell-VAILab/Raster2Seq) (SIGGRAPH 2026) | raster 256/512 px | Room-F1: Structured3D 99.6, CubiCasa5K 88.7, Raster2Graph 98.1; WAFFLE in-the-wild interior IoU 73.9 % | yes (HF `haopt/Raster2Seq`) |
| [FloorplanVLM](https://arxiv.org/html/2602.06507v1) (Qwen2.5-VL-3B, 1024²) | raster | FPBench-2K: ext-wall IoU 0.925, room IoU 0.892, opening F1 0.733; validity 96.1 % | not confirmed; cannot read text/dimensions |
| [VectorFloorSeg](https://openaccess.thecvf.com/content/CVPR2023/papers/Yang_VectorFloorSeg_Two-Stream_Graph_Attention_Network_for_Vectorized_Roughcast_Floorplan_Segmentation_CVPR_2023_paper.pdf) (CVPR 2023) | **vector SVG**, roughcast | CubiCasa-5k test mIoU 62.5 vs OCRNet 57.1 / DeepLabV3+ 58.2; room integrity 67.5 vs 41.9 | [code](https://github.com/DrZiji/VecFloorSeg) |
| FloorPlanCAD spotting: [CADSpotting](https://arxiv.org/abs/2412.07377), [DPSS/ArchCAD-400K](https://www.alphaxiv.org/overview/2503.22346v1) | vector primitives (DWG) | PQ 87.4 / 86.2 (SymPointV2 83.2); ArchCAD-400K = 5,538 drawings, PQ 70.6 | dataset open |
| [FloorYOLO](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1911589/abstract) (YOLOv8n, 3.0 M) | raster | SESYD synthetic mAP@0.5 0.995; **CVC-FP real scans 0.824 (mAP@0.5:0.95 0.48)** | not stated |
| ArchNetv2 ([AutCon 2024](https://www.sciencedirect.com/science/article/pii/S092658052400222X)); [SkeySpot](https://arxiv.org/abs/2508.10449) | raster | 13 classes mAP 93.5 %; 34 electrical symbol classes mAP 82.5 % on 45 scanned plans | SkeySpot open-source |
| SAM for rooms ([ICIAP 2025](https://link.springer.com/chapter/10.1007/978-3-032-10185-3_33)) | raster, point prompts | "consistently outperforms" semantic-seg SOTA on R3D + private set; numbers paywalled | — |
| [FloorSAM](https://arxiv.org/abs/2509.15750) | LiDAR density maps | not applicable to drawings | yes |
| [FGSSNet](https://arxiv.org/html/2507.10343) walls | raster | CubiCasa5K wall IoU 78.3 (U-Net 78.2); 10 real user plans: +3.5–4.4 IoU | not stated |
| MonoFloor | — | **not found** (an industrial-flooring consultancy) | — |
| SAM3 on floor plans | — | **not found** | — |

**Designer sheets vs clean plans:** the only published drop is Raster2Seq's 88.7 (CubiCasa) → 73.9 (WAFFLE, 20K Wikimedia plans, [WACV 2025](https://arxiv.org/abs/2412.00955)); FloorYOLO's 0.995→0.824 synthetic→real scans is the detector-side analogue. Furniture/hatching-specific numbers: **not found**.

## 3. Vector-first approaches

- **Tooling:** PyMuPDF `get_drawings()` returns lines/rects/curves with stroke/fill; `cluster_drawings()` groups nearby paths ([docs](https://pymupdf.readthedocs.io/en/latest/recipes-drawing-and-graphics.html)). One engineering blog's main pitfall is clip-path-defined geometry, which needed a PyMuPDF feature request ([elevait](https://www.elevait.de/blog/extraction-pdf-plan)).
- **Room polygons from lines:** a 2025 method finds all faces enclosed by simple closed curves in CAD layers in O(N·M), "in seconds"; **no accuracy reported** ([NTNU/Results in Engineering](https://scholar.lib.ntnu.edu.tw/en/publications/automated-process-for-analyzing-2d-cad-floor-plan-drawings-and-ge/)). VectorFloorSeg does the learned version and needs clean roughcast line segments ([CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/papers/Yang_VectorFloorSeg_Two-Stream_Graph_Attention_Network_for_Vectorized_Roughcast_Floorplan_Segmentation_CVPR_2023_paper.pdf)).
- **Production practice:** Bluebeam Snap-to-Content "can work only with vector-based content" ([novedge](https://novedge.com/blogs/design-news/bluebeam-tip-enable-snap-to-content-for-faster-more-accurate-takeoffs)); Togal calls vector PDFs "optimal", scans merely "adequate" ([Togal blog](https://www.togal.ai/blog/ai-blueprint-reading-accuracy)); Kreo names room polygons only when the PDF has a text layer ([Kreo help](https://help-takeoff.kreo.net/en/articles/9722231-auto-measure-20)).
- **Benchmarks for PDF→rooms:** **not found**; FloorPlanCAD-family data is DWG-derived, so the closest evidence is VectorFloorSeg (+4–5 mIoU, +25 room-integrity over raster) and the SVG+PNG LMM result (+21 pp).

## 4. Room polygon → perimeter/area

- **Conventions:** finishes are measured "net in contact with base", to the internal face ([GCU/NRM2 notes](https://edshare.gcu.ac.uk/4066/2/index.html)); NRM2 ignores voids ≤ 1.00 m² for most finishes and ≤ 0.50 m² for masonry ([Exayard SMM](https://exayard.com/learn/standard-methods-of-measurement), [RICS NRM2](https://www.rics.org/content/dam/ricsglobal/documents/standards/NRM-2_Oct2022_Update.pdf)); IPMS 2 residential measures to the *Internal Dominant Face* (>50 % of the lowest 2.75 m) ([isurv](https://www.isurv.com/info/390/features_archive/10662/ipms_residential_valuation)). **Flag:** `CLAUDE.md` states "openings < 0.5 m² not deducted (NRM2)"; the finishes threshold appears to be 1.00 m² — verify against NRM2 §28.
- **Error arithmetic (mine):** a 4.0 × 3.0 m room bounded by 100 mm partitions measured to centreline instead of face reads 12.00 vs 11.31 m² (+6 %) and 14.0 vs 13.6 m perimeter (+3 %); 15 mm plaster each side alone is −1.7 % area; one 0.9 × 2.1 m door is 5 % of a 37.8 m² wall. These convention errors are the same order as the AI errors below.
- **Where systems err:** Togal underestimated 12/15 area items vs the contractor (ceilings −3.4 to −11.3 %, floors −1.2 to −8.1 %, Wilcoxon p = .027) ([Sadeh et al.](https://easychair.org/publications/paper/pkrRp/open)); Handoff-H1 says continuous trades (wall lengths, roof foreshortening) error higher than counts ([Handoff-H1](https://arxiv.org/html/2608.15032)); Kreo auto-derives per-wall thickness ([Kreo help](https://help-takeoff.kreo.net/en/articles/9722231-auto-measure-20)). Which face Togal/Kreo measure to: **not documented**.

## 5. Published end-to-end numbers

| Study | Scope | Result |
|---|---|---|
| [KU et al. 2025 (Togal vs OST)](https://www.togal.ai/case-study/peer-reviewed-study-togal-ai-vs-on-screen-takeoff) | 9 drawing sets, areas/linear/counts | ~70 % time saving; within 5 % after manual adjustment |
| [Sadeh, Geloso, Todorov](https://easychair.org/publications/paper/pkrRp/open) | 1 commercial project, 29 finish items vs contractor | exterior −1.7…+13.4 %, floors −1.2…−8.1 %, ceilings −3.4…−11.3 %; counts n.s.; finish type matters (H = 8.42, p = .015); cites Zhao 2025: −51.3 % time, +20.4 % accuracy in a classroom |
| [Handoff-H1](https://arxiv.org/html/2608.15032) | 10 residential sets, 2,009 items | 81.6 % composite vs humans 77.6 % (humans more precise: P@25 87.9 vs 78.8, less coverage 65.5 vs 86.1) |
| Vendor claims | — | Togal "98 %" ([site](https://www.togal.ai/)) vs a GC reporting 85 % residential / 60 % retail podium ([review](https://www.bidicontracting.com/blog/togal-ai-review-2026)); Kreo 98.5 %, Beam ±1 % with human QA — unverified |
| Time-to-verify | — | vendor-only: 30 s/page, "2–3 h head start" ([ConstructConnect](https://www.constructconnect.com/blog/are-ai-takeoffs-accurate-in-2026)); independent: **not found** |

## 6. Recommendations for Pathon (Claude-vision + deterministic formulas)

| # | Change | Evidence | Expected gain | Effort |
|---|---|---|---|---|
| 1 | **Vector-first room polygons**: PyMuPDF path layer → wall segments → closed faces; snap Vision/flood-fill polygons to vector edges; Raster2Seq only for flattened rasters | VectorFloorSeg +4–5 mIoU/+25 RI; SVG+PNG +21 pp; every vendor's "accurate path" is vector | Removes pixel-quantisation and mis-marking (<30 % of error today); perimeter error then equals convention error | 1–2 wk; clip-path/hatch cleanup is the risk |
| 2 | **Dimension-string constraint**: fit scale from ≥3 text-layer dimension strings; reject polygons whose sides disagree >2 % with the nearest chain; show the string used | Scale = >70 % of area error; Handoff-H1's agents "zoom to read a dimension string"; OCR is the strong skill (0.70–0.95) | Largest single lever on area/perimeter | ~1 wk |
| 3 | **Crop loop at ≥300 dpi** (≈11.8 px/mm) for remaining visual reads (openings, legends); per-question crops, not whole A3 (3.7–6.1 px/mm after resize) | CropVLM +7.5…+14.9 pp; Mini-o3 +12.7 pp; Claude resize limits | Unmeasured on LT sheets — gate on the the contractor-validated fixture | days |
| 4 | **Detector + VLM verify for doors/windows**: fine-tune YOLOv8n/RF-DETR on ~200 labelled LT sheets, VLM only adjudicates | AECV: symbol counting "unreliable… without custom trained models"; FloorYOLO 0.82 mAP@0.5 on real scans; detector+GPT-5 +2…+14 pp | Door/window exact-match from ~0.2–0.4 (whole-sheet VLM) toward detector-level | 2–3 wk incl. labelling; correction UI already exists |
| 5 | **Explicit convention + evidence**: measure to internal finished face, NRM2 opening threshold, per-room crop showing polygon + dimension strings; narrow JSON schemas per call | Sadeh underestimation bias; ArchSIBench perception gap; ExtractBench schema-breadth collapse | Makes remaining error visible and checkable in minutes | small |

Do **not** invest in RoomFormer/PolyRoom/FloorSAM (point-cloud inputs) or in SAM3 for rooms (no floor-plan evidence found).
