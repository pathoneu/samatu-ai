"""The geometry lane on the real (untracked) drawings, from the cached
extractions: what it reads today must still be read tomorrow. The lists in
fixtures_geometry_gate.json only ever GROW — raise them when a change reads
more, never lower them to make a change pass."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from extractor import geometry_lane as gl  # noqa: E402

GATE = json.loads((Path(__file__).parent / "fixtures_geometry_gate.json").read_text(encoding="utf-8"))


def _fixture(slug: str):
    folder = ROOT / "ground_truth" / slug
    truth, extract = folder / "truth.json", folder / "ai_extract.json"
    if not truth.exists() or not extract.exists():
        return None
    pdf = Path(json.loads(truth.read_text(encoding="utf-8")).get("pdf_path") or "")
    pdf = pdf if pdf.is_absolute() else ROOT / pdf
    if not pdf.is_file():
        return None
    return pdf.read_bytes(), json.loads(extract.read_text(encoding="utf-8"))


@pytest.mark.parametrize("slug", sorted(GATE))
def test_geometry_gate(slug):
    fx = _fixture(slug)
    if fx is None:
        pytest.skip(f"{slug}: drawing not on this machine")
    pdf, extract = fx
    want = GATE[slug]
    parsed = copy.deepcopy(extract)
    out = gl.apply_geometry(parsed, pdf)
    rooms = {str(r["nr"]): r for r in parsed["patalpos"]}
    print(f"{slug}: {out['seconds']} s | kontūrai {out['konturai']} | atviros {out['atviros_erdves']} | "
          f"sudėti {out['perimetrai_sudeti']} | tušti {out['perimetrai_tusti']} | {out['konturu_priezastys']}")
    assert set(want["konturai"]) <= set(out["konturai"]), out["konturu_priezastys"]
    assert all(g in out["atviros_erdves"] for g in want["atviros_erdves"])
    for nr, metres in want["perimetrai_sudeti"].items():
        assert rooms[nr].get("perimetras_saltinis") == "matmenu_eilutes", (nr, rooms[nr].get("_perimetras_priezastis"))
        assert abs(rooms[nr]["perimetras_m"] - metres) <= 0.02, (nr, rooms[nr]["perimetras_m"])
        assert rooms[nr]["_perimetras_suma"]["sutampa"] is True
    for nr, metres in want["atviru_erdviu_iverciai"].items():
        assert rooms[nr]["perimetras_m"] is None and rooms[nr]["_perimetras_ivertis_saltinis"] == "atviros_erdves_konturas"
        assert abs(rooms[nr]["_perimetras_ivertis_m"] - metres) <= 0.05, (nr, rooms[nr]["_perimetras_ivertis_m"])
    blanks = [r for r in rooms.values() if r.get("perimetras_m") is None]
    assert len(blanks) >= want["min_tusti_su_iverciu"]
    # a blank is never a silent one: it carries the reason and the estimate to accept
    assert all(r.get("_perimetras_priezastis") and r.get("_perimetras_ivertis_m") for r in blanks)
    # nothing the table, the plan's pairs or a person stated was touched
    for nr, before in ((str(r["nr"]), r) for r in extract["patalpos"]):
        if before.get("perimetras_saltinis") in ("plano_matmenys", "eksplikacija", "user_override", "manual"):
            assert rooms[nr]["perimetras_m"] == before["perimetras_m"]
    assert out["seconds"] < 20
