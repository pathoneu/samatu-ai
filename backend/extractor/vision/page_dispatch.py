"""Page-type dispatcher — given a page_classifier result, decide which
secondary Vision extractors to run.

This is the wiring layer between ``page_classifier.py`` (which already
labels pages as floor_plan / wall_elevation / electrical / plumbing /
ceiling_plan / finish_schedule / etc.) and the new pass-specific
extractors built in this session:

   ceiling_plan   → niche_locator        → elementai[nisa_LED] additions
   wall_elevation → elevation_extractor  → tile_calculator overrides
   electrical /
   rozeciu plan   → symbol_detector      → annotator symbol overlay
   schedule page  → schedule_extractor   → opening dims + exterior flags

Integration policy (intentionally not wired into the live ``extract_interior``
pipeline yet):

  • Each secondary pass costs $0.30-0.50 per page and adds latency.
  • Some pages overlap (the floor-plan page itself can carry the
    eksplikacija that's used as a schedule).
  • Until N≥3 contractor-validated projects exist, we can't tell if
    the secondary passes net-improve accuracy or net-add noise.

This module provides ``dispatch_secondary_passes(pages, *, …)`` so the
production pipeline can opt in once the data exists. For now it's
import-and-test-only — `extract_interior` is unchanged. Wiring it into
prod is a config-flag flip away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .niche_locator import extract_niches, NicheList
from .elevation_extractor import extract_elevation_zones, ElevationPayload
from .symbol_detector import detect_symbols, SymbolPayload
from .schedule_extractor import extract_schedule, Schedule


# Map page_classifier tipas → secondary extractor function.
# Keys must match the canonical labels in extractor.page_classifier.
SECONDARY_EXTRACTORS: dict[str, Callable[..., Any]] = {
    "ceiling_plan":    extract_niches,
    "wall_elevation":  extract_elevation_zones,
    "electrical":      detect_symbols,
    "plumbing":        detect_symbols,
    "finish_schedule": extract_schedule,
}


@dataclass
class SecondaryResults:
    niches:     list[NicheList]        = field(default_factory=list)
    elevations: list[ElevationPayload] = field(default_factory=list)
    symbols:    list[SymbolPayload]    = field(default_factory=list)
    schedules:  list[Schedule]         = field(default_factory=list)
    skipped:    list[dict[str, Any]]   = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "n_niche_passes": len(self.niches),
            "total_niches": sum(len(n.niches) for n in self.niches),
            "n_elevation_passes": len(self.elevations),
            "total_panels": sum(len(e.panels) for e in self.elevations),
            "n_symbol_passes": len(self.symbols),
            "total_symbols": sum(len(s.symbols) for s in self.symbols),
            "n_schedule_passes": len(self.schedules),
            "total_doors": sum(len(s.durys) for s in self.schedules),
            "total_windows": sum(len(s.langai) for s in self.schedules),
            "skipped_pages": self.skipped,
        }


def dispatch_secondary_passes(
    pages: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    *,
    enabled: set[str] | None = None,
    model: str = "claude-opus-4-7",
) -> SecondaryResults:
    """Run each enabled secondary extractor on its matching pages.

    Parameters
    ----------
    pages : list of {page_index, image_b64} dicts (as produced by
        ``pdf_to_b64_images``).
    classifications : list of {nr, tipas, ...} dicts (one per page in the
        same order as `pages`).
    enabled : set of secondary kinds to run (subset of ``SECONDARY_EXTRACTORS``
        keys). When None, all are enabled.
    model : Anthropic model id (passed straight through).
    """
    enabled_set = enabled if enabled is not None else set(SECONDARY_EXTRACTORS.keys())
    out = SecondaryResults()
    n = min(len(pages), len(classifications))

    for i in range(n):
        page = pages[i]
        cls = classifications[i]
        tipas = (cls.get("tipas") or "").lower()
        if tipas not in enabled_set:
            continue
        image_b64 = page.get("image_b64")
        if not image_b64:
            out.skipped.append({"page_nr": page.get("page_index"), "tipas": tipas,
                                "reason": "no_image"})
            continue

        # Call by module-level name (not via dict lookup) so unittest.mock.patch
        # at the module level intercepts correctly. The dict above stays as a
        # discoverability index for callers.
        try:
            if tipas == "ceiling_plan":
                out.niches.append(extract_niches(image_b64=image_b64, model=model))
            elif tipas == "wall_elevation":
                out.elevations.append(extract_elevation_zones(image_b64=image_b64, model=model))
            elif tipas in ("electrical", "plumbing"):
                out.symbols.append(detect_symbols(image_b64=image_b64, model=model))
            elif tipas == "finish_schedule":
                out.schedules.append(extract_schedule(image_b64=image_b64, model=model))
            else:
                out.skipped.append({"page_nr": page.get("page_index"), "tipas": tipas,
                                    "reason": "no_extractor"})
        except Exception as exc:                                          # noqa: BLE001
            out.skipped.append({
                "page_nr": page.get("page_index"),
                "tipas": tipas,
                "reason": f"{type(exc).__name__}: {exc}",
            })

    return out
