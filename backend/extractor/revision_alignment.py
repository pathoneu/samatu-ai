"""A second edition of the drawing laid over the first (togal-v2 W10, Togal's comparison overlay).

The designer sends a revised PDF; the estimator wants to see what moved. For every sheet of the NEW
edition this finds the sheet of the OLD one (the project's drawing) that draws the same plan, and how
to lay one over the other — with sheet_alignment's own rule: the wall solid, laid as printed, box onto
box (a re-printed scale), or one wall-box corner onto the same corner (`_best_fit`).

Different from sheet_alignment in one respect: a revision MOVES walls — that is what he wants to see —
so a sheet is accepted at REVISION_SAME overlap instead of SAME_WALLS. Two storeys drawn alike look
the same to walls: when the same page number's overlap is within LOOKALIKE of the best old sheet's,
the same page number wins, and both scores stay on the record so the screen can say so. A sheet with
too few wall fills (a scan, an elevation) or no old sheet good enough falls back to the same page
number, page box onto page box ('lapo_krastai') — the screen says that this alignment is by the
sheet's edges, not by its walls.

Everything is in pdf_vectors' DISPLAY frame (PDF points, origin top-left, y down, /Rotate applied).
Convention as sheet_alignment.to_base with the OLD page as the base: old = k · new + (dx, dy).
"""
from __future__ import annotations

from typing import Sequence

from .sheet_alignment import _best_fit, _signature

REVISION_SAME = 0.60
LOOKALIKE = 0.05


def _page_sizes(pdf_bytes: bytes) -> dict[int, tuple[float, float]]:
    """{page: (width, height)} in the display frame (pdf_vectors' reading, /Rotate applied)."""
    import pypdfium2 as pdfium
    from .pdf_vectors import page_geometry
    from .pdfium_guard import PDFIUM_LOCK

    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            n = len(doc)
        finally:
            doc.close()
    out: dict[int, tuple[float, float]] = {}
    for p in range(1, n + 1):
        w, h, _ = page_geometry(pdf_bytes, p)
        if w > 0 and h > 0:
            out[p] = (float(w), float(h))
    return out


def _edges(new_size: tuple[float, float], old_size: tuple[float, float]) -> tuple[float, float, float]:
    """(k, dx, dy): the new sheet's box onto the old sheet's, keeping its aspect, centred."""
    nw, nh = new_size
    ow, oh = old_size
    if nw <= 0 or nh <= 0 or ow <= 0 or oh <= 0:
        return 1.0, 0.0, 0.0
    k = min(ow / nw, oh / nh)
    return k, (ow - k * nw) / 2, (oh - k * nh) / 2


def match_revision(old_pdf: bytes, new_pdf: bytes, old_pages: Sequence[int] | None = None,
                   new_pages: Sequence[int] | None = None) -> dict[int, dict]:
    """{new page: {old_page, k, dx, dy, sutapimas, budas, tas_pats_nr, sutapimas_to_paties}}.

    `budas` 'sienos' — laid by the wall solid; 'lapo_krastai' — by the sheet's edges only.
    `sutapimas` is the wall overlap (0–1) of the chosen fit, None for 'lapo_krastai'. When another old
    sheet fitted better but the same page number was within LOOKALIKE, `geriausias` names it."""
    old_sizes, new_sizes = _page_sizes(old_pdf), _page_sizes(new_pdf)
    olds = [int(p) for p in (old_pages or sorted(old_sizes)) if int(p) in old_sizes]
    news = [int(p) for p in (new_pages or sorted(new_sizes)) if int(p) in new_sizes]
    old_sigs = {p: _signature(old_pdf, p) for p in olds}
    out: dict[int, dict] = {}
    for n in news:
        sig = _signature(new_pdf, n)
        fits: dict[int, tuple[float, float, float, float]] = {}
        if sig is not None:
            for o in olds:
                if old_sigs.get(o) is None:
                    continue
                best = _best_fit(sig, old_sigs[o])
                if best is not None:
                    fits[o] = best
        best_old = max(fits, key=lambda o: (fits[o][0], o == n)) if fits else None
        chosen = best_old
        if best_old is not None and n in fits and best_old != n and fits[best_old][0] - fits[n][0] <= LOOKALIKE:
            chosen = n                                  # a look-alike storey: keep the sheet's own number
        if chosen is not None and fits[chosen][0] >= REVISION_SAME:
            same, k, dx, dy = fits[chosen]
            rec = {"old_page": chosen, "k": k, "dx": dx, "dy": dy, "sutapimas": round(same, 3), "budas": "sienos"}
            if best_old != chosen:
                rec["geriausias"] = {"old_page": best_old, "sutapimas": round(fits[best_old][0], 3)}
            out[n] = rec
            continue
        old_page = n if n in old_sizes else (olds[0] if olds else n)
        k, dx, dy = _edges(new_sizes[n], old_sizes.get(old_page, new_sizes[n]))
        out[n] = {"old_page": old_page, "k": k, "dx": dx, "dy": dy, "sutapimas": None, "budas": "lapo_krastai",
                  **({"geriausias": {"old_page": best_old, "sutapimas": round(fits[best_old][0], 3)}}
                     if best_old is not None else {})}
    return out


def to_old(lapas: dict, x: float, y: float) -> tuple[float, float]:
    """A point of the new sheet, on the old sheet."""
    return lapas["k"] * x + lapas["dx"], lapas["k"] * y + lapas["dy"]


def from_old(lapas: dict, x: float, y: float) -> tuple[float, float]:
    """A point of the old sheet, on the new sheet."""
    k = lapas["k"] or 1.0
    return (x - lapas["dx"]) / k, (y - lapas["dy"]) / k
