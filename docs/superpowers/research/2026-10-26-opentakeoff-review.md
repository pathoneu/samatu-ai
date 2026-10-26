# OpenTakeoff (Kentucky-ai) — what to take, what not (2026-10-26)

Source: github.com/Kentucky-ai/opentakeoff — browser-only takeoff canvas (pdf.js, feet/inches, US finish-flooring bids) + an MCP server (58 tools) for agents. Read: README, FEATURES.md, docs/design/ONE_CLICK_GATE.md.

**License: AGPL-3.0-only (relicensed from Apache-2.0 in their PR 530).** Pathon is a hosted service → copying code would oblige publishing Pathon's source. Ideas only. (Pre-relicense history is Apache-2.0 with attribution, but their engine is not something to build on — see next.)

**Their room detection is gated off** ("re-validated against a wider plan corpus"; "a quantity that reads as right is the worst failure"). Same conclusion as our raster track, same cause. On vector plans our lane is ahead (outlines, perimeters from strings, openings as drawn); they trace by hand.

## Take (ideas), ranked by our blockers
1. **Hatch classification by stroke periodicity** (per-stroke lattice periodicity → hatch/poché regions separate from linework) → finish zones on išklotinės. Passed to the finishes worker.
2. **PDF layer roles**: read named layers (OCGs) of CAD-exported PDFs to know wall / door / furniture ink instead of inferring. Cheap check: which corpus PDFs carry OCGs (pymupdf); objektas_a has furniture layers. Best untried anti-furniture measure for the vector lane.
3. **Door-gap rules** if raster returns: scale-pinned minimum passage (< ~0,15 m never joins rooms, thresholds in page points so render scale cannot move a measurement); door swings (bezier or tessellated arcs) close doorways to the wall plane; a gap-sealing ladder (distance-transform dilation, never-ascending growback, room-size + real-boundary gates), every seal on provenance.
4. **Eval metrics**: correct-refusal rate, cross-resolution determinism gates, refusal/leak rates, next to IoU (their `npm run bench` gates every engine change — like our four passes).
5. **UX**: a calibrated ruler guide bar drawn on the sheet after a scale is accepted (a 2×-off scale is obvious); „check a dimension" → % error verdict + one-tap recalibrate (our ScaleCheckCard can adopt the verdict); edge-insert ghost on a selected shape's edge; 45° angle lock.
6. **Provenance model**: every shape records scale, method (vector flood / raster trace / hand / agent), human-corrected flag, and the machine's original boundary frozen beside the correction — the labelled training pair. Ours: `_kilme` + the corrections table; worth adding the frozen original on correction.

## Leave
MCP/agent layer, feet-inches, client-only architecture, the US schedule importer (our finish-table reader covers the LT format), roll-goods seam layout, materials buy list (we have Medžiagos).

## Measured 2026-10-26: named layers (OCGs) in our drawings
| drawing | layers | examples |
|---|---|---|
| objektas_a (and the founder's fresh upload of it) | 387 | -BALDAI, -ISKLOTINES, -JUNGIKLIAI, -LUBOS, -ROZETES, -SVIESTUVAI, -TEKSTAS, A-DETL, G-ANNO-SCHD |
| objektas_i (both uploads) | 102 | SIENOS, Langai, SANTECHNIKA, a_baldai, TEKSTAS, Int_linija |
| objektas_g | 18 | Interior - Furniture, MEP - Elektros planai, Structural - Bearing, _02_Pertvarų planai, _01 Santechnikos planas, _00_LUBOS |
| objektas_h, objektas_d | 0 | flattened exports |

Consequence: on 4 of 6 corpus drawings and on the contractor's, a path's layer says wall / window / furniture / light / socket / išklotinė / text. Next engine step after finishes: a layer-roles reader in the vector lane (walls = SIENOS/Structural, furniture excluded, lights counted per layer, text layer for OCR-free labels). **License:** the listing above used pymupdf (AGPL) in a scratch venv — never in the backend; production reads layer membership through PDFium marked content (pypdfium2 raw API) or pikepdf (MPL).
