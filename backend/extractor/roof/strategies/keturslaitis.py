"""Keturšlaitis (4-pitch hip) roof strategy — 4-row template."""

from extractor.roof import geometry
from extractor.roof.strategies.base import (
    RoofStrategy, RoofInput, RoofOutput, LineItem,
)


class KeturslaitisStrategy(RoofStrategy):
    """4-pitch hip roof: produces 4 line items (perdanga, stogas, latakai, kraigai)."""

    def supports(self, input_: RoofInput) -> bool:
        return input_.roof_type == "keturslaitis"

    def compute(self, input_: RoofInput) -> RoofOutput:
        if not self.supports(input_):
            raise ValueError(f"KeturslaitisStrategy received roof_type={input_.roof_type}")
        # slopes_deg = [long_slope, short_slope] (asymmetric supported)
        slope_long = input_.slopes_deg[0]
        slope_short = input_.slopes_deg[1] if len(input_.slopes_deg) > 1 else input_.slopes_deg[0]
        q = geometry.keturslaitis_quantities(
            footprint_outer_w=input_.building_width_m,
            footprint_outer_l=input_.building_length_m,
            eaves_overhang_m=input_.eaves_overhang_m,
            slope_long_deg=slope_long,
            slope_short_deg=slope_short,
            wall_thickness_m=input_.wall_thickness_m,
            waste_factor=input_.waste_factor,
        )
        items = [
            LineItem("Perdanga", round(q.perdanga_m2, 1), "m²"),
            LineItem("Stogas (danga)", round(q.stogas_m2, 1), "m²"),
            LineItem("Latakai", round(q.latakai_m, 1), "m"),
            LineItem("Kraigai", round(q.kraigai_m, 1), "m"),
        ]
        return RoofOutput(roof_type="keturslaitis", line_items=items)
