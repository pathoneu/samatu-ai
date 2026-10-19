# DWG intake — spike (Pathon v3 W5-D, D14)

2026-10-19 · desk spike, nothing installed, no file uploaded anywhere. A new dependency needs the founder's OK.

## Question

Can a contractor drop a `.dwg` into „Naujas projektas" and get the same €0 reading a vector PDF gets today
(text layer, wall paths, dimension strings, legends)? Every reader in `backend/extractor/` reads a PDF through
PDFium / pdfplumber, so the realistic path is **DWG → PDF (vector) on our server**, then the existing pipeline.

## Options

| Option | What it is | Licence | Size / runtime | Fit |
|---|---|---|---|---|
| ODA File Converter | free CLI from the Open Design Alliance, DWG ↔ DXF (all versions up to 2018+ format) | proprietary freeware; redistribution / server use needs ODA's terms checked (membership for commercial SDK use) | ~100–150 MB install, Qt GUI binary run headless (`xvfb` on Linux) | best format coverage; licence is the open question |
| LibreDWG (`dwg2dxf`, `dwgread`) | GNU C library + CLI | GPL-3.0 (CLI run as a separate process; we would not link it) | few MB | incomplete on newer DWG versions and on some entities (hatches, dimensions, proxy objects) — would silently lose what our readers need |
| ODA Drawings SDK (Teigha) | C++ SDK, can export PDF directly | paid ODA membership | large | most complete; cost |
| ezdxf (+ its `drawing` add-on) | Python, reads/writes **DXF** and renders to PDF / SVG through matplotlib or PyMuPDF | MIT | pure Python | needs DXF first (one of the above); renders text as paths unless fonts are mapped — the text layer our readers depend on must be checked |
| Cloud converters (Autodesk APS Model Derivative, CloudConvert …) | upload, convert, download | per-call fees | — | **ruled out**: project drawings never go to a third-party service (programme non-negotiable 7) |

## What would have to be true

1. The converted PDF keeps **text as text** (room numbers, areas, dimension strings, legend rows) — otherwise
   plan_area_annotations, plan_dimensions, legend_rows and table_reader read nothing, and the project becomes a
   raster-like Vision-only run. ezdxf's PDF backend can emit text with embedded fonts; SHX fonts (common in LT
   CAD) map to TrueType substitutes — measure on a real DWG before promising anything.
2. Layouts / paper space: a DWG holds model space and several layouts; a contractor's „lapas" is a layout. The
   converter must emit one PDF page per layout at the layout's scale (the scale chip and every length rely on it).
3. Size and time: a 20–40 MB DWG with xrefs; xrefs missing from the upload must be reported, not drawn empty.

## Recommendation

Not now. Ask the architect for PDFs (every LT studio exports them for the permit set). If DWG becomes a sales
blocker: a one-day measured spike with **ODA File Converter → DXF → ezdxf → PDF** on two real DWGs, checking
(1)–(3) above, after the founder clears ODA's licence for server use and approves two new dependencies (ODA
converter binary, ezdxf). Until then the intake refuses `.dwg` with a plain sentence („DWG brėžinį pirmiausia
išsaugokite kaip PDF") — `backend/extractor/intake.py`.
