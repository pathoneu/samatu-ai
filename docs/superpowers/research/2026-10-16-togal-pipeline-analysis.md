# Togal.AI end to end — how a PDF becomes priced quantities (2026-10-16)

Reverse-engineering of the shipped Togal.AI web client plus its public help center and two granted
US patents, written to decide what Pathon should copy, skip or do differently. Companion to
`2026-09-17-tyrimas-togal-kreo.md` (UX walkthrough) and `2026-04-29-phase-c-competitor-tech.md`
(stack guesses from 2026-04, several of which this note corrects).

## Evidence and its limits

| Source | What it gives | Limit |
|---|---|---|
| Shipped frontend at app.togal.ai, 124 Vite/rolldown chunks, 14 MB, fetched 2026-10-16 | API contracts, state machines, feature keys, UI strings, bundled libraries | Minified; source maps unavailable |
| REA `analyze_web_bundle` over the live login page via headless Chrome CDP (Evidence `ev_8a6478382ca8c108bde3d2a371c82ee8c099627336be5708b9aab7934a135444`): 85 scripts parsed, 0 parse failures, 172 endpoint strings, 25 routes, completeness `partial` | Confirms the chunk graph and endpoint inventory used below | Static only; REA's JS graph analyzer could not run on this Mac (Swift toolchain), so code reading was done by direct extraction |
| help.togal.ai articles (file types, scale, Togal button, area/wall detection, editing, image search, re-Togaling, autoclassify, drawing links, naming) | Documented behaviour and wording | Marketing-adjacent |
| US 11,475,174 B2 and US 12,124,772 B2 | The method: rasterize, segment, regionize, dominance rules, vertex simplification, retraining loop | Patents describe what is claimed, not what ships |

Not observed: backend code, model weights, live traffic (no account), raster-input behaviour. Every
server-side statement below is inferred from the client contract, the realtime state names and the
patents. Each step is tagged **PDF parsing**, **AI model** or **rules** and ends with where it breaks.

## 0. The shape of the system

Togal is a **raster-first, server-side AI pipeline with a vector editing front end**.
The PDF is parsed once for structure (pages, text), rasterized into an image pyramid, and the
neural networks run on pixels on Togal's servers. Results come back as GeoJSON polygons, lines and
points, drawn over the image tiles in a deck.gl (WebGL) canvas, where the estimator edits and
classifies them. Quantities are computed client side from that geometry.

```
upload ─► page/file/process ─► per page: tiles ({prefix}/{z}/{x}/{y}.png, 3 levels)
                                          geojson_text (text runs + bboxes), text_ready
                                          cv_type / cv_discipline / cv_name / cv_number
                                          predicted_scale_{drawing,real,type,units}
          user confirms or sets scale (scale_drawing / scale_real / scale_type per page)
          green Togal ─► POST togal/scale/{view_id} (v2) with the feature list
                        SCALING_* ─► VECTORIZATION_TEXT ─► ROOMS ─► REGIONS ─► COUNTS
                        ─► WALLS / WALL_POLYGONS ─► ROOMS_GIA / CLASSIFICATION ─► TOGAL_COMPLETE
          predicted_geojson_{rooms,walls,counts,regions} stored on the page
          deck.gl editor: reclassify, drag vertices, split/merge, Re-Togal
          Quantities Panel (turf / JSTS) ─► assemblies, formulas ─► Excel / CSV / PDF
```

## 1. Intake: vector lines, image model, or both?

**Both, for different jobs. The AI never sees PDF line data.**

- **PDF parsing (client).** MuPDF compiled to WebAssembly is bundled (`mupdf-wasm-*.wasm`) and used
  to count pages and split a multi-page PDF into single-page PDFs before upload (`graftPage`,
  `saveToBuffer`; `page/file/process` takes `removedPageIndexes` and `pageNames`). pdf.js is bundled
  separately for the spec viewer in Togal.CHAT. Neither renders the takeoff canvas.
- **PDF parsing (server).** Every page gets `geojson_text`: text runs with `str`, a bounding box, a
  `text`/`para` kind and a `document_type` feature; `text_ready` says when it exists. A page whose
  document type is `text` is a `textDocument` (spec, schedule) and the Togal button refuses it.
  Sheet metadata `cv_type` (for example `non-drawing…`), `cv_discipline`, `cv_phase_of_construction`,
  `cv_name`, `cv_number` is written by a classifier. **Rules + model**: the text layer is parsing; the
  sheet classification is a model (the `cv_` prefix and the "non-drawing" bucket say computer vision).
- **Raster (server).** Pages carry `url_width`, `url_height`, `url_dpi` (default 72) and a tile
  `prefix`. The canvas's `TilesLayer` builds a quad tree of PNGs at `${prefix}/${level}/${x}/${y}.png`
  with three levels; high-resolution tiles are requested on demand (`tiling/request`, priority) and
  announced by `HIGH_RES_IMAGE_PROCESSING_COMPLETED` over a realtime channel (Ably). A fragment shader
  implements "Clear background" by thresholding brightness: the drawing on screen is pixels.
- **Patents** state that vector input (PDF, DWG, DXF) is converted to a raster image, scaled into
  the pixel range the model expects (small images upsampled with noise, large ones downsampled),
  before segmentation.
- **Vector vs raster at the product level.** The help center says vector PDFs are "ideal because
  they contain line data" and enable snap-to-corner; raster PDFs lose zoom clarity and snapping.
  In the shipped client every snapping mode (`Snap to points`, `Snap to alignment`, `Snap to lines`,
  `Snap to lines Percent`, `Snap to lines Distance`, `Snap to closed edges`) targets **existing takeoff
  geometry** through JSTS; no PDF vector path layer exists in the front end. What "snap-to-corner on
  vector PDFs" binds to is **unknown**; the only candidate is the server's `corner_detection` output.

**Where it breaks.** Scans and photos get no text layer, so everything downstream that reads text
(scale, names, room labels, links) degrades to OCR or nothing. Pages classified `non-drawing` are
skipped by the AI even if a plan is on them. Raster resolution is fixed by the server's DPI choice,
so hairline walls on dense A0 sheets can vanish before the model sees them.

## 2. Scale: detect, then make a human confirm

1. **Rules on the text layer.** The server predicts `predicted_scale_drawing`, `predicted_scale_real`,
   `predicted_scale_type` (`architectural` | `metric` | `civil`) and `predicted_scale_units` by
   reading the printed scale string (`1/8" = 1'-0"`, `1:100`). The help center calls it OCR and
   warns it "does NOT test the correctness of the scale". It reads, it does not measure.
2. **Rules in the client.** The pair `[drawing, real]` is matched against a standard scale table
   (`3/64" = 1'0"` … `1" = 1'0"`; metric and civil lists) and shown as `Scale: <label>`; no match
   gives `Scale not set` and a warning. A hint flow (`isHintConfirmed`) asks the user to confirm.
3. **Human.** Manual options: *Draw Line* (two clicks + known distance, optional "Snap to standard
   scales" with `% different` shown), *Enter Number*, *No Scale Needed*. Scale is **per page**; the
   help center forbids applying one scale to a set.
4. **Storage and use.** `scale_type`, `scale_real`, `scale_drawing` on the page; the client derives
   `referenceInchesPerPixels` from them plus the raster size, and every length and area is pixels times
   that factor. Matches the patents' "count pixels and apply the scale to the bitmap".
5. **Gate.** The green button reads `Set scale` and is disabled until both values exist. A run
   starts with `SCALING_START` → `SCALING_SUCCESS` (5–10 % progress), so the backend re-applies
   the scale to the raster before detection; the focused detectors answer `scaling_in_progress` if
   called early.
6. **Verification.** The Measure Tool against a known dimension.

**Where it breaks.** A sheet printed at another size than drawn (A1 on A3, "fit to page") carries a
true scale string that is wrong for the pixels; Togal reads the string and has no check against
dimension strings. A title block with several scales (plan 1:100, details 1:20) yields one guess
per page with no evidence of which drawing it belongs to. Pathon's dimension-string lane already
measures the scale instead of reading it (`plan_dimensions.py`, `laneScaleOriginOf`), which is
strictly stronger here.

## 3. Rooms, walls, openings, symbols

**Trigger.** Pressing Togal posts a feature selection to `togal/scale/{view_id}` (API v2): **All
Features**, **Custom** (checkboxes) or **Focused** (organizations with the labelling flag). Progress
arrives as realtime states and is mapped to a progress bar:

| Server state | Progress | Reading |
|---|---|---|
| `SCALING_START` / `SCALING_SUCCESS` | 5–10 % | scale applied to raster |
| `VECTORIZATION_START` / `PENDING` / `TEXT_COMPLETE` | 20 % | text layer attached |
| `VECTORIZATION_ROOMS_COMPLETE` | 40 % | room segmentation |
| `VECTORIZATION_REGIONS_COMPLETE` | 50 % | region / footprint polygons |
| `VECTORIZATION_COUNTS_COMPLETE` | 60 % | symbol detection |
| `VECTORIZATION_WALLS_COMPLETE` / `WALL_POLYGONS_COMPLETE` | 80 % | wall polygons and centerlines |
| `VECTORIZATION_ROOMS_GIA_COMPLETE` / `CLASSIFICATION_COMPLETE` | 95 % | gross internal area, classification |
| `VECTORIZATION_SUCCESS` / `TOGAL_COMPLETE` | 100 % | button becomes **Re-Togal** |
| `VECTORIZATION_AREA_NAMING_COMPLETE` | after | room names from text |

"Vectorization" means converting pixel predictions into GeoJSON. Outputs land on the page as
`predicted_geojson_rooms`, `predicted_geojson_walls`, `predicted_geojson_counts`,
`predicted_geojson_regions`, separate from the user's own `geojson`.

**AI model (patents + help).** A deep-learning segmentation network predicts wall boundaries and
classifies exterior walls, interior walls, doorways, windows, fixtures and text. Doors and windows
are then replaced with wall-consistent segments so rooms close; text is removed or kept as context.
Rooms are the enclosed regions, split with Hough-type and watershed steps where they touch. Room
type is suggested by a classifier: each feature carries `ml_classification[]`, and the client
turns the first entry into a `suggestion` (`area_<class>` or `wall_<class>`); a polygon without its
own class inherits the suggestion of an overlapping polygon (overlap > 0.2). Wall type (Exterior,
Shaft, Corridor, Interior, Demising, Bathroom) comes from `view/{id}/tag_recognition` (reads wall
tags on the sheet) chained with `view/{id}/corner_detection`; door type from
`view/{id}/door_classification`, with explicit failure messages (`no_walls_found`,
`no_doors_found`). Training data per the patents: tens of thousands of human-labelled plans.

**Rules.** The help center's "parallel lines that represent walls" is a wall polygon → centerline
extraction. Opening widths become `doors_area` by multiplication with a classification height
("Height as 7 ft"). Room names are joined from the text layer to the polygon they stand in.

**Symbols.** The Togal run itself counts plumbing fixtures (toilet, sink, shower, urinal, bathtub),
door types, furniture and appliances (`predicted_geojson_counts`). Separately, **AI Image Search**
posts a user-drawn bounding box to `togal/symbols` and returns matches across the set, which the
user converts into a Count classification; searched symbols are kept (`symbol_id`) for reuse.
Pattern Search (`togal/patterns`) is the same for hatches. These are image-similarity models, not
template matching.

**Where it breaks.** Dense furniture, hatching and dimension lines fragment room fills (the same
failure Pathon measured on objektas_g with raster flood fill). Open plans without a wall produce
one region for two rooms. Symbols drawn in a legend are counted (the help center tells users to
exclude legends by hand). G2 reviews cite "captures more items than intended". Detection is
"architectural floor plans" only; the modal says structural, elevation and site plans are manual.
The independent review Pathon already cited puts sheet-level accuracy at 60–95 %, not the marketed
98 %.

## 4. From geometry to areas, lengths, counts

**Rules, mostly client side.** Feature keys: `footprint`, `gross_area`, `gross_area_internal`,
`net_area`, `walls_area`, `walls_centerline`, `walls_perimeter`, `doors_area`, `doors_centerline`,
`count`, plus `wall_classification*`, `door_classification` and trade bundles `flooring`, `painting`.
Net Area is finish area excluding walls; Gross Area is centerline to centerline; Wall Perimeter
traces faces; Doors Centerline traces each opening. The patents describe how shared walls are split
between rooms: a **dominance hierarchy** (stairwell beats office; equal ranks split 50/50), then a
refinement that reduces vertices and merges collinear segments. The client recomputes every number
from the GeoJSON with turf.js, JSTS and polygon-clipping on each edit; custom formulas and
assemblies (components with formulas, waste factors, material cost, cost codes incl. MasterFormat)
sit on top.

**Where it breaks.** Everything downstream inherits the scale error multiplicatively (areas
squared). Gross vs net depends on the wall polygon being right on both sides. Heights are a typed
classification property, not read from sections, so every vertical quantity is perimeter × a number
the estimator typed. No opening deduction rule like NRM2's 0.5 m² floor is visible; openings are
"backed out" by the user through formulas.

## 5. Showing results and flagging uncertainty

- **Display.** Each AI result is a classified feature on the canvas with the classification's
  colour, fill pattern and line style, listed in the Quantities Panel. Layers can be toggled.
- **Uncertainty.** There is **no per-polygon confidence in the takeoff UI**. The only "Confidence"
  column in the bundle belongs to the AI Assemblies suggestions table (`Name, Description,
  Confidence, Project, Created On`). The help center positions results as "a starting point" to
  review. Rooms are not flagged; nothing says "this one is doubtful".
- **What is flagged.** Hard failures only: `no_walls_found`, `no_doors_found`, `scaling_in_progress`,
  `Error while Togaling drawing`, and the `textDocument` / `non-drawing` refusal.
- **Pathon's position.** Pathon's 🟢🟡🔴 per-fact confidence with a reason sentence and the
  evidence crop is something Togal does not have. Kreo has an AI-confidence slider; Togal does not.

## 6. Fixing wrong or missed items

**Client rules in a deck.gl editable layer.** Drag a vertex; hover an edge to add one; double-click
to delete; drag a shape to move it; Lasso; Split, Merge, Cut/Subtract, Merge Lines, Arc; "Move
lines as connected"; rotate / flip / group. Reclassify by right-click in the Quantities Panel.
Snapping settings: Automatic snapping (angle or distance), Snap to points, Snap distance (px), and
the six snap modes above; Shift disables snapping, Ctrl+click snaps to a point.

**Bulk fixes.** *Auto Classify* applies the per-feature `suggestion` (`ml_classification[0]`) to a
selection in one click; features whose suggested class is not in the project's classification map
are skipped and logged. *Re-Togal* reruns detection; reassigned classifications are kept and their
originals regenerated (so a Net Area used for flooring can be Togaled again for ceilings).
*Outline from a click* and *split-space* equivalents do not exist in Togal; its answer is Re-Togal
plus manual vertex work.

**Missed items.** Draw them by hand with the same tools, or run Image Search on an example.

**Where it breaks.** Vertex editing of a room does not re-run anything about its neighbours; the
shared-wall allocation is frozen in the exported polygons. Corrections are per view, so a second
estimator's view of the same page starts from the raw prediction again (`view/{id}/copy` exists to
duplicate). No "what changed downstream" is shown after an edit (confirmed in the 09-17 research).

## 7. Do corrections train the model?

**Documented intent, two visible mechanisms, no visible estimator-level feedback.**

- The patents say corrections are logged and fed back as training data, and that "expert teams"
  review outputs and resubmit corrected drawings for retraining.
- The client contains an internal **labelling workflow**: organizations of type `labeling`, user
  roles `labeler` and `reviewer`, per-page statuses `none → undone → done → accepted | rejected`
  with colours, `view/{id}/accept` and `view/{id}/reject`, a `LABELER_FEATURES` preset (Net Area
  only), and `LabellingIndicator` dots on sheets and sets. This is a human labelling pipeline for
  Togal's own staff or contractors, not a customer feature.
- For ordinary users the only feedback channels are Togal.CHAT thumbs up/down
  (`TOGAL_CHAT_RATE_UP/DOWN`), AI Assemblies suggestion accept/reject events, and product analytics
  (Amplitude). Ordinary vertex edits are saved as the user's `geojson`; whether they are harvested
  server side cannot be seen from the client.

**Where it breaks.** Learning is offline and global; an estimator's drafting conventions do not
change what the model does on their next sheet. Pathon's `scripts/build_ground_truth.py` approach
(corrected polygons and verified quantities **are** the corpus) is the per-account version of this.

## 8. Organizing and exporting for pricing

**Rules.** The unit of organization is the **classification** (name, colour, unit, folder), with
optional **breakdowns** (tier / item / subitem tags per feature) and **assemblies** (components
with formulas, unit of measure, waste factor, material cost, labour and equipment resources, cost
codes with MasterFormat or custom fields). Export modes: *Screen View* (Excel, aggregated and grouped
as on screen, up to four groupings), *Full Export* (Excel, one flat row per feature with every
parameter as a column), and a customer-specific CSV template (`Coastal Template`). Excel is produced
in the browser with exceljs. PDF export with overlays and legend goes through
`view/export_multipage`; a draw-log export (`export_draw_log`) records who drew what.
Integrations: Procore, ServiceTitan, Stripe billing, an OAuth consent flow for third parties
(eTakeoff Dimension and DESTINI Estimator use it), and Togal.CHAT over `external/openai/prompt`.

**Where it breaks.** Pricing lives outside Togal unless an assembly carries material cost; there is
no national price book. Quantities exported are whatever the classification holds; the same room
can be in flooring, ceiling and paint classifications with no reconciliation between them.

## 9. Summary table

| Step | PDF parsing | AI model | Rules | Most likely error |
|---|---|---|---|---|
| Split, count pages | MuPDF in browser | | | none |
| Rasterize, tiles | PDF render | | tile pyramid | hairlines lost at fixed DPI |
| Text layer | PDF text (OCR on scans, inferred) | | | scans: no text |
| Sheet naming, discipline | text layer | `cv_*` classifier | | plan classified as non-drawing |
| Scale | printed string (OCR) | | match to standard list | sheet printed at another size; wrong string picked |
| Rooms, walls, openings | | segmentation + regionization | gap bridging, dominance split | furniture/hatching fragments, open plans merged |
| Wall and door types | | tag recognition, corner detection, door classifier | | tags missing on sheet |
| Room names | text layer | | point-in-polygon | label outside polygon |
| Symbols | | detection + image similarity | | legend counted, lookalikes |
| Areas, lengths, counts | | | turf/JSTS from GeoJSON, typed heights | scale error squared, height typed not read |
| Uncertainty | | | none per feature | user cannot tell which polygon to check |
| Correction | | | vertex/split/merge editor, Auto Classify | neighbours not updated, per-view |
| Learning | | offline retraining via labelling org | | no per-account adaptation |
| Export | | | classifications, breakdowns, assemblies, Excel/CSV/PDF | no reconciliation across classifications |

## 10. What this means for Pathon

Already matched or exceeded: scale from measured dimension strings with provenance
(`durableScale.js`, `scaleLabel.js`); vector-wall room outlines, openings and dimension-string
perimeters (`vector_rooms.py`, `geometry_lane.py`, `drawn_openings.py`); per-fact confidence with
evidence crops; outline-from-click and split-space; corrections as the ground-truth corpus.

Real gaps, in order of value for the estimator and risk to accuracy:

1. **Snap to the drawing's geometry** in the measure and calibrate tools (wall-fill corners and
   edges from `pdf_vectors.wall_fills`), plus Togal's "snap to standard scale, show % difference"
   in `CalibrateDialog`. Zero accuracy-engine risk; makes manual calibration and measurement exact
   on vector PDFs.
2. **Whole-sheet geometry layer** (wall solid, every room outline, openings) as a Layers toggle,
   reusing the same page-geometry endpoint; today this is visible only per room in `CheckLayer`.
3. **Vertex editing of AI outlines** in `TakeoffViewer` (drag / add / delete) wired to
   `/recompute-interior` with `polygon_source = corrected`. Highest value, highest risk: it touches
   billed quantities and must be measured with `eval_harness.py --gate` before and after.

Not worth copying: confidence-free display (Pathon's per-fact dots are better), typed heights
(Pathon reads height markers), classification-centric quantities (Pathon's sąmata rows with
ledgers are the product), rasterizing before geometry (Pathon's vector lanes are the stronger path
where the PDF is vector).
