"""One-shot: build totals-only truth.json for the 5 new projects.

Reads each pasiūlymas/sąmata PDF (zero Vision spend), maps the line
items to standard metric keys, writes ``ground_truth/<slug>/truth.json``
mirroring the Beržų schema. gt_dimensions = [] (per-room data not yet
collected; would require Vision).

Mapping is hardcoded per-project because:
  • each sąmata uses slightly different category labels
  • some projects collapse walls+ceiling into one paint line, others split
  • regex parsing would be brittle and harder to audit
  • the cost of writing this once is small and the artefact is traceable

All five sąmatos are from Rangovas A — same contractor
as Beržų. This is a single-contractor cross-project benchmark, NOT a
cross-contractor benchmark.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GT_ROOT = REPO_ROOT / "ground_truth"
FIXTURE_ROOT = REPO_ROOT / "docs/superpowers/fixtures/2026-06-01-batch-5"


def _val(value, source, confidence="green", notes=None):
    out = {"value": value, "confidence": confidence, "source": source}
    if notes:
        out["notes"] = notes
    return out


# ─────────────────────────────────────────────────────────────────────
# Nr. 1 — Objektas B, Kaunas (5-page pasiūlymas, 65-page TP)
# ─────────────────────────────────────────────────────────────────────
BACEVICIAUS = {
    "$schema_version": 1,
    "project_id": "objektas_b",
    "name": "Objektas B (Objektas B)",
    "pdf_path": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 1/TP_Objektas B_2025naujausias.pdf",
    "source": {
        "samata_pdf": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 1/Pasiūlymas 20260413.pdf",
        "contractor": "Rangovas A",
        "date_collected": "2026-04-13",
    },
    "notes_for_evaluator": (
        "gt_dimensions intentionally empty — per-room data not extracted yet. "
        "Totals derived from pasiūlymas 2026-04-13. Largest of the 5 batch projects (65-page TP)."
    ),
    "floor_total_sanity_check_m2": None,
    "gt_dimensions": [],
    "gt_per_room": {},
    "gt_totals": {
        "gkp_lubu_iki_3m_m2": _val(74.91, "pasiūlymas item 1 'GKP ant lubų'"),
        "gkp_lubu_virs_3m_m2": _val(68.28, "pasiūlymas item 2 'GKP ant lubų virš 3m'"),
        "gkp_laidu_apsiuvimas_garaze_m2": _val(26.57, "pasiūlymas item 3"),
        "led_nisos_m": _val(54.98, "pasiūlymas item 4 'Nišų formavimas iš GKP'"),
        "angokrasciu_m": _val(94.02, "pasiūlymas item 14 'Angokraščių apdirbimas GKP'"),
        "rotband_lyginimas_m2": _val(138.69, "pasiūlymas item 15"),
        "dazymo_walls_plus_ceilings_combined_m2": _val(
            493.03, "pasiūlymas items 16+17 sum (424.75 + 68.28) — matches Beržų convention"),
        "dazymo_iki_3m_m2": _val(424.75, "pasiūlymas item 16 'Sienų/ lubų glaistymas/dažymas'"),
        "dazymo_lubu_virs_3m_m2": _val(68.28, "pasiūlymas item 17"),
        "sienu_molio_tinkas_m2": _val(160.0, "pasiūlymas item 18 'Sienų dekoravimas molio tinku'",
                                       confidence="green",
                                       notes="Clay plaster — not in default formula scope but contractor-billed"),
        "doors_atkosai_m": _val(55.52, "pasiūlymas item 19 'Durų angų paruošimas beapvasdinėms durims'"),
        "kampu_metrai_m": _val(580.54, "pasiūlymas item 20 'Dažymo kampų montavimas'"),
        "plyteles_sienos_grindys_1200x1200_m2": _val(157.34, "pasiūlymas item 28"),
        "plyteles_sienos_grindys_1200x600_m2": _val(52.59, "pasiūlymas item 30"),
        "plyteles_didzformaciai_m2": _val(7.52, "pasiūlymas item 31"),
        "parketas_45_eglute_m2": _val(108.08, "pasiūlymas item 101"),
        "ilyginamasis_grindys_m2": _val(143.19, "pasiūlymas item 102"),
        "grindjuostes_isleistos_m": _val(63.0, "pasiūlymas item 103"),
        "grindjuostes_paprastos_m": _val(30.8, "pasiūlymas item 104"),
    },
}

# ─────────────────────────────────────────────────────────────────────
# Nr. 2 — Čiurlių g. 10, Bajorai (2-page pasiūlymas, 3-page A3 planai)
# ─────────────────────────────────────────────────────────────────────
CIURLIU = {
    "$schema_version": 1,
    "project_id": "ciurliu",
    "name": "Čiurlių g. 10, Bajorai",
    "pdf_path": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 2/Techninio projekto planai_20250501 (a3)_2.pdf",
    "source": {
        "samata_pdf": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 2/Pasiūlymas apdailos darbams galutinis 2026.pdf",
        "contractor": "Rangovas A",
        "date_collected": "2026-02-12",
    },
    "notes_for_evaluator": (
        "gt_dimensions intentionally empty. Smallest of the 5 batch projects (3-page A3 planai). "
        "Single-tier ceiling (no virš 3m split)."
    ),
    "floor_total_sanity_check_m2": None,
    "gt_dimensions": [],
    "gt_per_room": {},
    "gt_totals": {
        "gkp_lubu_iki_3m_m2": _val(111.84, "pasiūlymas item 1 'GKP ant lubų'"),
        "led_nisos_m": _val(16.84, "pasiūlymas item 2 'Nišų formavimas iš GKP'"),
        "angokrasciu_m": _val(34.53, "pasiūlymas item 4 'Angokraščių apdirbimas GKP'"),
        "rotband_lyginimas_m2": _val(37.0, "pasiūlymas item 6"),
        "dazymo_walls_plus_ceilings_combined_m2": _val(388.01, "pasiūlymas item 7 'Sienų, lubų glaistymas/dažymas'"),
        "kampu_metrai_m": _val(201.86, "pasiūlymas item 8 'Dažymo kampų montavimas'"),
        "plyteles_sienos_grindys_combined_m2": _val(55.27, "pasiūlymas item 12 'Plytelių klijavimas ant sienų ir grindų'"),
        "plyteles_epoksidinis_glaistas_m2": _val(37.11, "pasiūlymas (unindexed) 'Plytelių glaistymas epoksidiniu'"),
        "pvc_grindys_m2": _val(98.0, "pasiūlymas item 8 (grindų skyrius) 'Pvc grindų įrengimas'"),
        "palanges_m": _val(4.94, "pasiūlymas item 7 (grindų skyrius)"),
    },
}

# ─────────────────────────────────────────────────────────────────────
# Nr. 3 — Romainiai (Deividas Norkaitis), 1-page pasiūlymas, 45-page interior
# ─────────────────────────────────────────────────────────────────────
ROMAINIAI = {
    "$schema_version": 1,
    "project_id": "romainiai",
    "name": "Romainiai (Deividas Norkaitis)",
    "pdf_path": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 3/Deividas Norakitis INTERJERAS 4.1-5.1 punktas.pdf",
    "source": {
        "samata_pdf": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 3/Pasiūlymas apdailos darbams atnaujintas.pdf",
        "contractor": "Rangovas A",
        "date_collected": "2026-01-15",
    },
    "notes_for_evaluator": (
        "gt_dimensions intentionally empty. Interior-only scope — NO plytelės, NO GKP montavimas. "
        "Paint-heavy project. Two separate paint products billed (Benjamin Moore + Supreme Ultimate). "
        "Interior PDF is 4.1-5.1 punktas subset of full project — totals reflect subset only."
    ),
    "floor_total_sanity_check_m2": None,
    "gt_dimensions": [],
    "gt_per_room": {},
    "gt_totals": {
        "rotband_lyginimas_m2": _val(95.0, "pasiūlymas item 1"),
        "dazymo_walls_plus_ceilings_combined_m2": _val(
            420.08, "pasiūlymas items 2+3+5 sum (139.79 + 250.95 + 29.34) — all three are paint",
            confidence="incomplete",
            notes=("Even with all paint items summed, project_pdf is the FULL 45-page "
                   "interior design but pasiūlymas prices only the 4.1-5.1 punktas subset. "
                   "AI will over-extract vs this number — flagged scope_mismatch in registry.")),
        "dazymo_lubu_only_m2": _val(139.79, "pasiūlymas item 2 'Lubų glaistymas/dažymas (Benjamin Moore)'"),
        "dazymo_walls_plus_ceilings_combined_subset_m2": _val(
            250.95, "pasiūlymas item 3 'Sienų/ lubų glaistymas/dažymas (Benjamin Moore)' — subset only"),
        "stiklo_audinys_lubose_m2": _val(134.79, "pasiūlymas item 4 'Stiklo audinio klijavimas'",
                                          confidence="green",
                                          notes="Fiberglass on cooled ceilings — separate from paint line"),
        "dazymo_supreme_zone_m2": _val(29.34, "pasiūlymas item 5 'Supreme Ultimate dažais'"),
        "doors_atkosai_m": _val(23.92, "pasiūlymas item 6 'Durų angų paruošimas beapvadinėms durims'"),
        "pasleptu_duru_staktos_m": _val(5.0, "pasiūlymas item 7"),
        "duru_varcios_dazymas_vnt": _val(1.0, "pasiūlymas item 8"),
        "angokrasciu_m": _val(23.8, "pasiūlymas item 9 'Angokraščių glaistymas/dažymas'"),
        "moldingu_dazymas_m": _val(27.1, "pasiūlymas item 10"),
        "kampu_metrai_m": _val(329.77, "pasiūlymas item 11"),
        "led_profiliai_apdirbimas_m": _val(5.5, "pasiūlymas item 12"),
        "led_nisos_m": _val(34.54, "pasiūlymas item 14 'Nišų iš GKP'"),
    },
}

# ─────────────────────────────────────────────────────────────────────
# Nr. 4 — Šernų g. 18B, Kaunas (2-page sąmata, electrical+tile plans only)
# ─────────────────────────────────────────────────────────────────────
SERNU = {
    "$schema_version": 1,
    "project_id": "sernu",
    "name": "Šernų g. 18B, Kaunas",
    "pdf_path": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 4/I109_Šernu_plyteles_2025 04 02.pdf",
    "source": {
        "samata_pdf": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 4/Sąmata.pdf",
        "contractor": "Rangovas A",
        "date_collected": "2025-07-16",
    },
    "notes_for_evaluator": (
        "gt_dimensions intentionally empty. ⚠ No general floor plan PDF in the supplied bundle — "
        "only electrical + tile specialty drawings. The 'pdf_path' field points at the tile "
        "drawing, which is NOT the architectural source for paint/wall extraction. Marked "
        "blocked_for_vision_extraction until missing PDFs are supplied."
    ),
    "floor_total_sanity_check_m2": None,
    "gt_dimensions": [],
    "gt_per_room": {},
    "gt_totals": {
        "rotband_lyginimas_m2": _val(132.36, "sąmata item 1"),
        "dazymo_walls_plus_ceilings_combined_m2": _val(461.31, "sąmata item 2 'Sienų, lubų glaistymas/dažymas'"),
        "papildomas_sienu_glaistymas_m2": _val(395.19, "sąmata item 3"),
        "doors_atkosai_m": _val(33.97, "sąmata item 4 'Durų angų paruošimas'"),
        "kampu_metrai_m": _val(303.25, "sąmata item 5"),
        "angokrasciu_m": _val(85.45, "sąmata item 9 'Angokraščių apdirbimas gipso kartonu'"),
        "stoglangiai_vnt": _val(6.0, "sąmata item 10"),
        "plyteles_sienos_grindys_combined_m2": _val(101.57, "sąmata item 16"),
        "plyteles_angokrasciai_m": _val(25.74, "sąmata item 17 'Angokraščių ir nišų'"),
    },
    "blocked_for_vision_extraction": True,
    "blocked_reason": "Missing architectural floor plan PDF in bundle — only specialty (elektra, plytelės) drawings present.",
}

# ─────────────────────────────────────────────────────────────────────
# Nr. 5 — Lazūnų g. 6 (Butas, oldest 2024 project)
# ─────────────────────────────────────────────────────────────────────
LAZUNU = {
    "$schema_version": 1,
    "project_id": "lazunu",
    "name": "Lazūnų g. 6 (Butas)",
    "pdf_path": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 5/Apmatavimai-Layout4.pdf",
    "source": {
        "samata_pdf": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 5/Galutinė sąmata.pdf",
        "contractor": "Rangovas A",
        "date_collected": "2024-06-26",
    },
    "notes_for_evaluator": (
        "gt_dimensions intentionally empty. APARTMENT (butas) not house — smallest scope. "
        "Project drawings split across 10 separate single-page AutoCAD Layout4 PDFs. "
        "Vision-extraction path needs PDF bundling logic before it can run."
    ),
    "floor_total_sanity_check_m2": None,
    "gt_dimensions": [],
    "gt_per_room": {},
    "gt_totals": {
        "gkp_lubu_iki_3m_m2": _val(41.28, "sąmata item 1"),
        "gkp_pertvaros_4_sluoksniai_m2": _val(11.14, "sąmata item 2"),
        "gkp_dezuciu_montavimas_m": _val(9.94, "sąmata item 3"),
        "led_nisos_m": _val(10.58, "sąmata item 4 'Nišų formavimas'"),
        "pasleptu_duru_staktos_m": _val(10.22, "sąmata item 6"),
        "angokrasciu_m": _val(31.8, "sąmata item 10 'Angokraščių apdirbimas GKP'"),
        "rotband_lyginimas_m2": _val(32.41, "sąmata item 12"),
        "dazymo_walls_plus_ceilings_combined_m2": _val(150.57, "sąmata item 13 'Sienų, lubų glaistymas/dažymas'"),
        "kampu_metrai_m": _val(123.59, "sąmata item 14"),
        "doors_atkosai_m": _val(10.22, "sąmata item 18 'Durų angų paruošimas'"),
        "led_nisos_glaistymas_m": _val(10.68, "sąmata item 19"),
        "plyteles_sienos_grindys_combined_m2": _val(32.97, "sąmata item 20 'Plytelių klijavimas (iki 120x60)'"),
        "pvc_grindys_m2": _val(36.99, "sąmata item 44"),
        "grindjuostes_paprastos_m": _val(23.07, "sąmata item 45"),
    },
}


PROJECTS = [BACEVICIAUS, CIURLIU, ROMAINIAI, SERNU, LAZUNU]


def main() -> int:
    written = []
    for proj in PROJECTS:
        out_dir = GT_ROOT / proj["project_id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "truth.json"
        out_path.write_text(
            json.dumps(proj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append((proj["project_id"], out_path, len(proj["gt_totals"])))

    print("Truth files written:")
    for pid, path, n_metrics in written:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {pid:<15} {n_metrics:>3} metrics  → {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
