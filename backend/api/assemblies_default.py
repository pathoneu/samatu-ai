"""The „numatyta" rinkiniai — built from the engine's own constants (togal-v2 W9).

Every norm and waste factor below is IMPORTED from the calculation engine
(`extractor.vision_call`, `extractor.universal_rules`); not one number is
retyped. `tests/test_assemblies_default.py` asserts each default equals the
constant it came from, so the two can never drift: change a constant and the
default follows; the assemblies never feed a value back into the engine.

A default assembly explains rows the engine already wrote: its material
components name the „Medžiagos" rows the builder emits for that work
(`susijes_darbas`), and the „Sudėtis" route (api/sudetis.py) shows a norm only
where norma × kiekis × (1 + atliekos) reproduces that row within rounding.

`taikoma.aprasymas` is the engine's exact work label; `{vieta}` stands for the
variable part of a templated label („{vieta} plytelių klijavimas" →
„Vonios sienų"), and the same `{vieta}` in a component name is filled from it.
Labels are text, not numbers — they are what binds a default to a row.

Paint materials depend on two project choices (putty Q-level, paint class);
`build_default_assemblies(q_level, paint_class)` takes them, defaulting to the
engine's own defaults, and the Sudėtis route passes the project's.
"""
from __future__ import annotations

from typing import Any

from extractor import vision_call as _vc
from extractor.universal_rules import GKP_SHEET_WASTE, UNIVERSAL_RULES

DEFAULT_PREFIX = "numatyta-"
DEFAULT_NOTE = "numatyta — iš skaičiavimo taisyklių"

# ── Kodai: the cost-code column („kodas") in the LT sąmata structure ─────────
#
# Pathon's own two-level scheme, NOT a national classifier (Lithuania has none
# for interior finishing that a sąmata must follow; the normatyvai codes belong
# to their publishers). Level 1 = the section, in the order the sąmata prints
# its sections; level 2 = the family inside it, from the default assembly.
# A row with no matching assembly gets its section's code alone. He can type
# his own on any row; nothing computes from a code.
SKYRIUS_KODAI: dict[str, tuple[str, str]] = {
    # skyrius_enum → (kodas, section name as printed)
    "paint": ("01", "Glaistymo ir dažymo darbai"),
    "gkp": ("02", "GKP montavimas"),
    "tile": ("03", "Plytelių klijavimas"),
    "waterproof": ("04", "Hidroizoliacija"),
    "floor": ("05", "Grindys"),
    "plumbing": ("06", "Santechnikos darbai"),
    "electrical": ("07", "Elektros instaliacijos darbai"),
    "extras": ("08", "Pridėtiniai ir kiti darbai"),
    "materials": ("09", "Medžiagos"),
    "out_of_scope": ("99", "Ne mūsų darbai"),
}


def kodas_for_enum(skyrius_enum: str | None) -> str | None:
    hit = SKYRIUS_KODAI.get(str(skyrius_enum or ""))
    return hit[0] if hit else None


def _paint_norms(q_level: str, paint_class: int) -> dict[str, float]:
    q = q_level if q_level in _vc._Q_GLAISTAS_KG_PER_M2_MM else "Q2"
    prof = (_vc._PAINT_CLASS_PROFILES.get(int(paint_class))
            or _vc._PAINT_CLASS_PROFILES[_vc._PAINT_CLASS_DEFAULT])
    return {
        "glaistas": _vc._Q_GLAISTAS_THICKNESS_MM[q] * _vc._Q_GLAISTAS_KG_PER_M2_MM[q],
        "gruntas": 1.0 / _vc.PRIMER_COVERAGE_M2_PER_L,
        "dazai": prof["absorption_factor"] / prof["coverage_m2_per_l"],
    }


def _waste_proc(factor: float) -> float:
    """×1,08 → 8 %. Rounded to 4 places so 1.1 − 1 reads 10, not 10.000000000000009."""
    return round((float(factor) - 1.0) * 100.0, 4)


def _m(pavadinimas: str, norma: float, vnt: str, *, atliekos: float = 0.0,
       apvalinimas: str | None = None, minimumas: float | None = None,
       saltinis: str) -> dict[str, Any]:
    """A material component. `saltinis` names the engine constant(s) — shown in
    the Rinkiniai page and asserted by the drift test."""
    return {"rusis": "medziaga", "pavadinimas": pavadinimas, "norma": norma,
            "vnt": vnt, "atliekos_proc": atliekos, "kaina": None,
            "apvalinimas": apvalinimas, "minimumas": minimumas,
            "saltinis": saltinis}


def _darbas(pavadinimas: str, vnt: str) -> dict[str, Any]:
    """The labour itself: one unit of work per unit of the row."""
    return {"rusis": "darbas", "pavadinimas": pavadinimas, "norma": 1.0, "vnt": vnt,
            "atliekos_proc": 0.0, "kaina": None, "apvalinimas": None,
            "minimumas": None, "saltinis": "eilutės kiekis"}


def _a(slug: str, name: str, skyrius: str, enum: str, nr: int, label: str, vnt: str,
       komponentai: list[dict]) -> dict[str, Any]:
    sk = SKYRIUS_KODAI[enum][0]
    return {
        "id": DEFAULT_PREFIX + slug,
        "name": name,
        "skyrius": skyrius,
        "taikoma": {"aprasymas": label, "vnt": vnt, "eilutes_id": []},
        "vnt": vnt,
        "komponentai": [_darbas(name, vnt), *komponentai],
        "kodas": f"{sk}.{nr:02d}",
        "is_default": True,
        "pastaba": DEFAULT_NOTE,
    }


def build_default_assemblies(q_level: str = "Q2",
                             paint_class: int | None = None) -> list[dict[str, Any]]:
    """The default set, one assembly per work family that has materials."""
    pc = paint_class if paint_class is not None else _vc._PAINT_CLASS_DEFAULT
    pn = _paint_norms(q_level, pc)
    sheet_m2 = UNIVERSAL_RULES["drywall_sheet_area_m2"]
    q = q_level if q_level in _vc._Q_GLAISTAS_KG_PER_M2_MM else "Q2"
    glaistas_src = f"_Q_GLAISTAS_THICKNESS_MM[{q}] × _Q_GLAISTAS_KG_PER_M2_MM[{q}]"
    dazai_src = f"_PAINT_CLASS_PROFILES[{pc}] absorption_factor ÷ coverage_m2_per_l"

    def paint(surface_lt: str, kam: str, slug: str, nr: int) -> dict[str, Any]:
        return _a(slug, f"{surface_lt} glaistymas/dažymas", f"{surface_lt} glaistymas dažymas",
                  "paint", nr, f"{surface_lt} glaistymas/dažymas{{vieta}}", "m2", [
                      _m(f"Glaistas {kam} (pradinis + baigiamasis)", pn["glaistas"], "kg",
                         saltinis=glaistas_src),
                      _m(f"Gruntas {kam}", pn["gruntas"], "l",
                         saltinis="1 ÷ PRIMER_COVERAGE_M2_PER_L"),
                      _m(f"Dažai {kam} (2 sluoksniai)", pn["dazai"], "l", saltinis=dazai_src),
                  ])

    return [
        paint("Sienų", "sienoms", "sienu-dazymas", 1),
        paint("Lubų", "luboms", "lubu-dazymas", 2),
        _a("rotband", "Sienų lyginimas Knauf Rotband", "Sienų glaistymas dažymas", "paint", 3,
           "Sienų lyginimas Knauf Rotband", "m2", [
               _m("Rotband (~10 kg/m² esant 5mm storiui)", _vc.ROTBAND_KG_PER_M2, "kg",
                  saltinis="ROTBAND_KG_PER_M2")]),
        _a("dazymo-kampai", "Dažymo kampų montavimas", "Sienų glaistymas dažymas", "paint", 4,
           "Dažymo kampų montavimas", "m", [
               _m("PVC kampuotės (išoriniai kampai)", _vc.CORNER_BEAD_M_PER_M, "m",
                  saltinis="CORNER_BEAD_M_PER_M")]),
        _a("grindjuostes", "Grindjuosčių sumontavimas", "Sienų glaistymas dažymas", "paint", 5,
           "Grindjuosčių sumontavimas", "m", [
               _m("Grindjuostės (m + 10% atliekų)", 1.0, "m",
                  atliekos=_waste_proc(_vc.SKIRTING_WASTE), saltinis="SKIRTING_WASTE")]),
        _a("karnizas", "Lubų karnizo sumontavimas", "Lubų glaistymas dažymas", "paint", 6,
           "Lubų karnizo sumontavimas", "m", [
               # The +5 % is already in the work length (CORNICE_LENGTH_WASTE):
               # one metre of cornice bought per metre of the row.
               _m("Karnizas (m + 5% atliekų)", 1.0, "m",
                  saltinis="CORNICE_LENGTH_WASTE (jau eilutės ilgyje)")]),
        _a("gkp-lubos", "GKP lubų montavimas", "GKP montavimas", "gkp", 1,
           "GKP lubų montavimas{vieta}", "m2", [
               _m(f"GKP lapai luboms ({UNIVERSAL_RULES['drywall_thickness_ceilings_mm']} mm)",
                  1.0 / sheet_m2, "vnt", atliekos=_waste_proc(GKP_SHEET_WASTE),
                  apvalinimas="aukstyn",
                  saltinis="1 ÷ drywall_sheet_area_m2, GKP_SHEET_WASTE"),
               _m("GKP karkaso CD profiliai (laikantieji)", _vc.GKP_CD_PROFILE_M_PER_M2, "m",
                  saltinis="GKP_CD_PROFILE_M_PER_M2"),
               _m("GKP karkaso UW profiliai (pakraščio)", _vc.GKP_UW_PROFILE_M_PER_M2, "m",
                  saltinis="GKP_UW_PROFILE_M_PER_M2"),
               _m("Savisriegiai GKP montavimui", float(_vc.GKP_SCREWS_PER_M2), "vnt",
                  apvalinimas="zemyn", saltinis="GKP_SCREWS_PER_M2"),
           ]),
        _a("gkp-siules", "GKP siūlių glaistymas + armavimo juostelė", "GKP montavimas", "gkp", 2,
           "GKP siūlių glaistymas + armavimo juostelė", "m", [
               _m("Armavimo juostelė + glaistas siūlėms", 1.0, "m",
                  saltinis="GKP_JOINT_M_PER_M2 (eilutė ir medžiaga — tie patys metrai)")]),
        _a("gkp-nisos", "Nišų formavimas GKP konstrukcijoje", "GKP montavimas", "gkp", 3,
           "Nišų formavimas GKP konstrukcijoje", "m", [
               _m("GKP profiliai + savisriegiai", _vc.NICHE_PROFILE_M_PER_M, "m",
                  saltinis="NICHE_PROFILE_M_PER_M")]),
        _a("gkp-angokrasciai", "Angokraščių apdirbimas GKP", "GKP montavimas", "gkp", 4,
           "Angokraščių apdirbimas GKP (struktūra)", "m", [
               _m("GKP juostelės + savisriegiai", 1.0, "m",
                  saltinis="angokraščių metrai (1 m medžiagos 1 m darbo)")]),
        _a("plyteles-klijavimas", "Plytelių klijavimas", "Plytelių klijavimas", "tile", 1,
           "{vieta} plytelių klijavimas", "m2", [
               _m("{vieta} plytelių klijai (~5 kg/m²)", _vc.TILE_ADHESIVE_KG_PER_M2, "kg",
                  saltinis="TILE_ADHESIVE_KG_PER_M2"),
               _m("{vieta} plytelės", 1.0, "m2", atliekos=_waste_proc(_vc.TILE_WASTE),
                  saltinis="TILE_WASTE"),
           ]),
        _a("plyteles-fugavimas", "Plytelių fugavimas", "Plytelių klijavimas", "tile", 2,
           "{vieta} plytelių fugavimas", "m2", [
               _m("{vieta} plytelių fugavimo masė (~0.3 kg/m²)", _vc.GROUT_KG_PER_M2, "kg",
                  saltinis="GROUT_KG_PER_M2")]),
        _a("silikonas-sanitarinis", "Silikonavimas prie sanitarinės įrangos",
           "Plytelių klijavimas", "tile", 3,
           "Silikonavimas tarp plytelių zonos ir sanitarinės įrangos", "m", [
               _m("Sanitarinis silikonas (~10 m/tūbelę)", 1.0 / _vc.SILICONE_M_PER_TUBE, "vnt",
                  apvalinimas="artimiausias", minimumas=1.0,
                  saltinis="1 ÷ SILICONE_M_PER_TUBE")]),
        _a("silikonas-kampai", "Plytelių vidinių kampų silikonavimas", "Plytelių klijavimas",
           "tile", 4, "Plytelių vidinių kampų silikonavimas", "m", [
               _m("Spalvotas silikonas pagal fugavimo spalvą", 1.0 / _vc.SILICONE_M_PER_TUBE,
                  "vnt", apvalinimas="artimiausias", minimumas=1.0,
                  saltinis="1 ÷ SILICONE_M_PER_TUBE")]),
        _a("isliginamasis", "Grindų išlyginamasis sluoksnis", "Grindys", "floor", 1,
           "Grindų išlyginamasis sluoksnis", "m2", [
               _m("Savaime išsilyginantis mišinys (~2 kg/m²/mm)", _vc.SELF_LEVELLING_KG_PER_M2,
                  "kg", saltinis="SELF_LEVELLING_KG_PER_M2")]),
        _a("grindu-danga", "Parketo / laminato klojimas", "Grindys", "floor", 2,
           "Parketo / laminato klojimas", "m2", [
               _m("Grindų danga (m² + 10% atliekų)", 1.0, "m2",
                  atliekos=_waste_proc(_vc.FLOOR_COVERING_WASTE),
                  saltinis="FLOOR_COVERING_WASTE"),
               _m("Grindų dangos pamušalas", 1.0, "m2",
                  saltinis="grindų dangos plotas (be atliekų)"),
           ]),
        _a("ortakiai", "Ortakių montavimas", "Ventiliacijos darbai", "extras", 1,
           "Ortakių D{vieta} mm montavimas", "m", [
               _m("Cinkuoti spiralinio tipo ortakiai D{vieta}", 1.0, "m",
                  atliekos=_waste_proc(_vc.DUCT_WASTE), saltinis="DUCT_WASTE")]),
    ]


def default_by_id(assembly_id: str, **kw) -> dict[str, Any] | None:
    for a in build_default_assemblies(**kw):
        if a["id"] == assembly_id:
            return a
    return None
