"""Dvišlaitis (2-pitch gable) roof strategy — 8-row template."""

from extractor.roof import geometry
from extractor.roof.strategies.base import (
    RoofStrategy, RoofInput, RoofOutput, LineItem,
)


class DvislaitisStrategy(RoofStrategy):
    """2-pitch gable roof: produces 8 line items per LT roofer convention."""

    def supports(self, input_: RoofInput) -> bool:
        return input_.roof_type == "dvislaitis"

    def compute(self, input_: RoofInput) -> RoofOutput:
        if not self.supports(input_):
            raise ValueError(
                f"DvislaitisStrategy received roof_type={input_.roof_type}"
            )
        slope = input_.slopes_deg[0]
        q = geometry.dvislaitis_quantities(
            building_length_m=input_.building_length_m,
            building_width_m=input_.building_width_m,
            eaves_overhang_m=input_.eaves_overhang_m,
            slope_deg=slope,
            wall_thickness_m=input_.wall_thickness_m,
            eaves_to_ground_m=input_.eaves_to_ground_m,
            soflitas_depth_m=input_.soflitas_depth_m,
            waste_factor=input_.waste_factor,
        )
        items = [
            LineItem("Stogas (danga)", round(q.stogas_m2, 1), "m²"),
            LineItem("Sienos (gablai + soflitas)", round(q.sienos_m2, 1), "m²"),
            LineItem("Vėjalentės", round(q.vejalentes_m, 1), "m"),
            LineItem("Kraigas", round(q.kraigai_m, 1), "m"),
            LineItem("Latakai", round(q.latakai_m, 1), "m"),
            LineItem("Apsauginė tvorelė", round(q.apsaugine_tvorele_m, 1), "m"),
            LineItem("Langų apdirbimas", input_.windows_count, "vnt"),
            LineItem("Kaminėlis", input_.chimney_count, "vnt"),
        ]
        return RoofOutput(roof_type="dvislaitis", line_items=items)
