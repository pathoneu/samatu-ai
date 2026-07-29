"""Deterministic symbol-LEGEND scanner ($0, no Vision call).

WHY (2026-07-29, Beržų g. 24). The Vision symbol reader returned
``difuzoriai: 6`` for a 17-page interior project that draws no ventilation
diffuser anywhere. The word appears exactly once, inside note 3 of the
apšvietimo plan:

    "Rekuperacijos sistemos, kondicionavimo sistemos ir garso sistemos
     projektus derinti kartu su interjero projektuotojais, dėl DIFUZORIŲ
     vietos ir formos parinkimo, kolonėlių dydžio ir vietos..."

— i.e. the diffuser positions are explicitly NOT decided yet, and the sheet's
"Sutartiniai žymėjimai" legend defines no diffuser glyph at all (it lists
šviestuvai, LED juostos, jungikliai, davikliai, termostatas, garso kolonėlės).
The 6 the model returned are crosshair circles that the legend calls
"Pakabinamas lubinis šviestuvas". Those 6 then also fabricated 30 m of Ø125
ortakiai through the HVAC fallback.

THE RULE. A symbol count is only trustworthy when the drawing DEFINES the
symbol. A legend entry is a noun-phrase LABEL and is therefore written in the
nominative ("Priglaistomas padavimo difuzorius", "Priglaistomi apvalūs
difuzoriai"); running prose refers to the things in an oblique case
("dėl difuzorių vietos"). Matching the nominative alone separates the two
without any model call, and it fails SAFE in both directions:

  · legend phrased in the genitive → no anchor found → honest checklist row
    (a TODO for the user), never a wrong number;
  · prose containing a nominative → anchor found → today's behaviour, no worse.

Verified across the benchmark corpus:
    berzas      note-only "difuzorių"          → NOT defined  (contractor 15/21
                                                  comes from the ventilation
                                                  dalis, absent from this PDF)
    objektas_b  legend "…padavimo difuzorius", → defined      (we read 18,
                "…ištraukimo difuzorius"                       contractor 20)
    lazunu      legend "Priglaistomi apvalūs   → defined      (we read 4,
                 difuzoriai gipso kartono                      contractor 6)
                 lubose"
    ciurliu     no mention                     → NOT defined  (we read 0 anyway)
    romainiai   "Difuzorius Liger-22 2000mm"   → defined (KNOWN LIMITATION: that
                 in a lighting price table                  is an LED-profile
                                                            lens, a different
                                                            sense of the word.
                                                            Leaves the existing
                                                            count untouched, so
                                                            it is not a
                                                            regression.)
"""
from __future__ import annotations

import io
import re

# Nominative singular/plural only — see module docstring. `(?<!\w)` / `(?!\w)`
# keep "difuzoriai" from matching inside a longer token.
_DIFFUSER_LABEL_RE = re.compile(r"(?<!\w)dif[uū]zori(?:us|ai)(?!\w)",
                                re.IGNORECASE)

# Below this many characters across the whole document the text layer is a
# scan artefact, not a readable legend. Absence of the word then proves
# nothing, so the scanner reports `text_layer_ok=False` and callers must not
# gate on it.
MIN_TEXT_CHARS = 200


def scan_symbol_legend(pdf_bytes: bytes) -> dict:
    """Scan the PDF text layer for symbol-label anchors.

    Returns:
        {
          "text_layer_ok": bool,        # enough text to reason about absence
          "chars": int,
          "difuzoriai": {
              "defined": bool,          # a nominative diffuser LABEL exists
              "pages": [int, ...],      # 1-indexed pages carrying it
              "samples": [str, ...],    # ≤3 verbatim snippets, for the report
          },
        }

    Never raises: any pdfplumber failure degrades to
    ``text_layer_ok=False`` (= "no signal"), which leaves callers on their
    pre-existing behaviour.
    """
    result = {
        "text_layer_ok": False,
        "chars": 0,
        "difuzoriai": {"defined": False, "pages": [], "samples": []},
    }
    try:
        import pdfplumber
    except ImportError:
        return result

    total_chars = 0
    pages: list[int] = []
    samples: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    continue
                total_chars += len(text)
                m = _DIFFUSER_LABEL_RE.search(text)
                if m:
                    pages.append(idx)
                    if len(samples) < 3:
                        lo = max(0, m.start() - 60)
                        hi = min(len(text), m.end() + 60)
                        samples.append(
                            " ".join(text[lo:hi].split()))
    except Exception:
        return result

    result["chars"] = total_chars
    result["text_layer_ok"] = total_chars >= MIN_TEXT_CHARS
    result["difuzoriai"] = {
        "defined": bool(pages),
        "pages": pages,
        "samples": samples,
    }
    return result


def diffuser_count_is_anchored(parsed: dict) -> bool:
    """Should a Vision `difuzoriai` count be believed for this project?

    True unless the scanner positively established BOTH that the text layer is
    readable AND that no diffuser label appears in it. Absent scan results
    (older extract, PDF not on disk, scanned drawing) → True, i.e. unchanged
    behaviour. The gate can only ever turn an unanchored number into a
    checklist TODO; it never invents one.
    """
    legend = parsed.get("_symbol_legend")
    if not isinstance(legend, dict) or not legend.get("text_layer_ok"):
        return True
    dif = legend.get("difuzoriai")
    if not isinstance(dif, dict):
        return True
    return bool(dif.get("defined"))
