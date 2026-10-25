"""v4 Phase 3c-2 (2026-10-25): counts from the legends, the last model readers reduced to text.

  · the guard: no module under backend/extractor or backend/text sends an image (or a whole PDF) to a model except
    the two marked paths of the reading — Pass-1 and the zoom (vision_call `_run_pass1_once`, `_vision_zoom_room`,
    their content builders in prompt.py) — and the roof module, which is hidden from the launch UI and not part
    of the interior reading. The text readers import no image renderer and no model client;
  · text/schema_llm.py: every value must stand in the input text, else refused; the request carries text only;
  · legend counts: the family vocabulary, his confirmed count beats the proposal, the blank sentence;
  · vector_symbols: a run of touching round symbols is split into its copies, a slot or a ring with petals is not;
  · sheet kinds from the title text; door types from the text; the plumbing rows from the legend only; the
    finish breakdown a model estimated comes off; the zoom picks only rooms the drawing does not measure;
  · on the corpus (skipped without the fixture PDFs): objektas_h's legend counts and sheet kinds.

No Anthropic call anywhere: every client here is a stub.
"""
from __future__ import annotations

import ast
import io
import json
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
H_PDF = REPO / "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_h/project.pdf"

_BLOCK = re.compile(r"[\"']type[\"']\s*:\s*[\"'](image|document)[\"']")
_CALL = re.compile(r"\.messages\.(create|stream)\b")
# the marked paths: (file, innermost function) — Pass-1 and the zoom, and the roof module (hidden, not interior)
ALLOWED_CALLS = {("extractor/vision_call.py", "_run_pass1_once"), ("extractor/vision_call.py", "_vision_zoom_room"),
                 ("text/schema_llm.py", "structure")}
ALLOWED_BLOCKS = {("extractor/prompt.py", "build_user_content"), ("extractor/prompt.py", "build_zoom_user_content"),
                  ("extractor/prompt.py", "build_user_content_pdf_native")}
HIDDEN_MODULES = {"extractor/roof/vision_extractor.py"}   # facade / roof: hidden from the launch UI (CLAUDE.md)


def _innermost_hits(path: Path, rx: re.Pattern) -> set[str]:
    src = path.read_text()
    tree = ast.parse(src)
    lines = src.splitlines()
    hits: set[str] = set()

    def visit(node, fn: str | None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
            else:
                seg = "\n".join(lines[child.lineno - 1:child.end_lineno]) if hasattr(child, "lineno") else ""
                if seg and rx.search(seg) and not any(isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
                                                      for c in ast.walk(child)):
                    hits.add(fn or "<module>")
                else:
                    visit(child, fn)
    visit(tree, None)
    return hits


def _modules():
    for root in ("extractor", "text"):
        for p in sorted((BACKEND / root).rglob("*.py")):
            rel = p.relative_to(BACKEND).as_posix()
            if rel not in HIDDEN_MODULES:
                yield rel, p


def test_no_module_sends_pixels_to_a_model_except_the_marked_paths():
    calls, blocks = set(), set()
    for rel, p in _modules():
        src = p.read_text()
        if _CALL.search(src):
            calls |= {(rel, fn) for fn in _innermost_hits(p, _CALL)}
        if _BLOCK.search(src):
            blocks |= {(rel, fn) for fn in _innermost_hits(p, _BLOCK)}
    assert calls <= ALLOWED_CALLS, sorted(calls - ALLOWED_CALLS)
    assert blocks <= ALLOWED_BLOCKS, sorted(blocks - ALLOWED_BLOCKS)


@pytest.mark.parametrize("rel", ["extractor/apdailos_reader.py", "extractor/door_type_reader.py",
                                 "extractor/eksplikacija_reader.py", "extractor/material_specs.py",
                                 "extractor/wall_elevation.py", "extractor/page_classifier.py",
                                 "extractor/legend_counts.py", "text/page_kind.py", "text/schema_llm.py"])
def test_the_text_readers_import_no_renderer_and_no_client(rel):
    src = (BACKEND / rel).read_text()
    for banned in ("import anthropic", "from anthropic", "convert_from_bytes", "pdf_to_b64_images", "_render_page_b64",
                   "anthropic.Anthropic("):
        assert banned not in src, (rel, banned)


@pytest.mark.parametrize("gone", ["extractor/doors_reader.py", "extractor/sanitary_fixture_reader.py",
                                  "extractor/vision/schedule_extractor.py", "extractor/vision/_image_json.py"])
def test_the_pixel_readers_are_deleted(gone):
    assert not (BACKEND / gone).exists()


# ── text/schema_llm.py ──────────────────────────────────────────────────────────────────────────────────────

TABLE = "PATALPŲ EKSPLIKACIJA\nNr. Pavadinimas Plotas\n101 Tambūras 11,01 m²\n102 Svetainė 37,86 m²\n"


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        text = json.dumps(self.payload, ensure_ascii=False)
        block = type("B", (), {"type": "text", "text": text})()
        usage = type("U", (), {"input_tokens": 10, "output_tokens": 5})()
        return type("R", (), {"content": [block], "stop_reason": "end_turn", "usage": usage, "stop_details": None})()


def test_schema_llm_keeps_values_that_stand_in_the_text_and_refuses_the_rest():
    from text.schema_llm import structure
    payload = {"items": [
        {"nr": {"value": "101", "source_text": "101 Tambūras"}, "plotas_m2": {"value": 11.01, "source_text": "11,01 m²"}},
        {"nr": {"value": "102", "source_text": "102 Svetainė"}, "plotas_m2": {"value": 38.0, "source_text": "37,86 m²"}},
        {"nr": {"value": "103", "source_text": "103 Vonia"}, "plotas_m2": {"value": 5.0, "source_text": "5 m²"}},
    ]}
    client = _Client(payload)
    out = structure(TABLE, fields={"nr": "text", "plotas_m2": "number"}, key="nr", instruction="x", client=client)
    assert [it["nr"] for it in out["items"]] == ["101", "102"]
    assert out["items"][0]["plotas_m2"] == 11.01 and "plotas_m2" not in out["items"][1]   # 38,0 is not written
    whys = {(r["index"], r["field"]): r["kodel"] for r in out["refused"]}
    assert whys[(1, "plotas_m2")] == "skaičiaus šaltinio tekste nėra"
    assert whys[(2, "nr")] == "šaltinio teksto tekste nėra"                # 103 is not in the text → item dropped
    # the request carried text blocks only — never an image or a document
    for call in client.calls:
        for m in call["messages"]:
            assert all(b["type"] == "text" for b in m["content"])


def test_schema_llm_without_a_client_or_text_asks_nothing():
    from text.schema_llm import structure
    assert structure(TABLE, fields={"nr": "text"}, instruction="x")["status"] == "no_client"
    assert structure("  ", fields={"nr": "text"}, instruction="x", client=_Client({}))["status"] == "empty"


def test_schema_llm_numbers_are_read_as_written():
    from text.schema_llm import check_value, numbers_in
    assert numbers_in("2 400 mm; 12,30 m²; H=2820") == [2400.0, 12.3, 2820.0]
    assert check_value("number", 2400, "2 400 mm", "plotis 2 400 mm") is None
    assert check_value(["a", "b"], "c", "a", "a") == "reikšmė ne iš leistinų"
    assert check_value("text", "Vonia", "103 Vonia", "103 vonia 5") is None


# ── legend counts ───────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,fam", [
    ("Pavir š inis š viestuvas", "sviestuvai"), ("Pakabinamas lubinis šviestuvas", "sviestuvai_pakabinami"),
    ("Sieninis šviestuvas", "sviestuvai_sieniniai"), ("BRA šviestuvo išvadas sienoje", "sviestuvai_sieniniai"),
    ("Elektros išvadas virštinkiniams šv. montuojamiems prie lubų", "sviestuvai"),
    ("Termostato vieta (per jungiklių grupės centrą), h=1400 mm", "termostatai"),
    ("Kištukinis lizdas", "rozetes"), ("Dvigubas jungiklis", "jungikliai"), ("Gaisro daviklis", "davikliai"),
    ("Potinkinis tualeto/bide bakelis", "wc_remai"), ("Dušo nuotekos/trapo vieta", "trapai"),
    ("Laidas šviestuvui / LED juostai pajungti", None), ("Tuščia rozetė skirta vamzdeliui pravesti", None),
    ("Šviestuvai vienoje linijoje", None), ("iki perdangos, ne daugiau 15cm. Voniose 8 cm gylio.", None),
    ("Elektros išvadas", None),
])
def test_family_of_a_legend_row(text, fam):
    from extractor.legend_counts import family_of
    assert family_of(text) == fam


def _proposal(**fams):
    return {"_meta": {"legendos_siulymai": {"status": "ok", "lapai_su_legenda": [3],
                                            "seimos": {k: {"kiekis": n, "tekstas": k, "lapai": [3],
                                                           "saltinis": "vektoriai"} for k, n in fams.items()}}}}


def test_his_confirmed_count_beats_the_proposal_for_every_family_of_that_kind():
    from extractor.legend_counts import counts_for_rows
    p = _proposal(sviestuvai=25, sviestuvai_pakabinami=5, jungikliai=27)
    c = counts_for_rows(p)
    assert c["sviestuvai"]["n"] == 25 and not c["sviestuvai"]["patvirtinta"]
    assert "Patvirtinkite" in c["sviestuvai"]["sakinys"]
    p["_legendos_kiekiai"] = {"sviestuvai": {"kiekis": 20, "tekstas": "Šviestuvas"}}
    c = counts_for_rows(p)
    assert c["sviestuvai"] == {**c["sviestuvai"], "n": 20, "patvirtinta": True}
    assert "sviestuvai_pakabinami" not in c and c["jungikliai"]["n"] == 27


def test_the_blank_row_says_whether_there_is_a_legend():
    from extractor.legend_counts import no_count_reason
    assert "nėra legendos" in no_count_reason({}, "rozečių")
    assert "legendoje rozečių ženklo neradau" in no_count_reason(_proposal(), "rozečių")


def test_the_electrical_rows_take_the_legend_count_or_stay_blank_with_the_reason():
    from extractor.vision_call import _build_pozicijos_from_rooms
    room = {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamasis", "plotas_m2": 20.0}
    p = {**_proposal(sviestuvai=12, jungikliai=4, rozetes=6), "patalpos": [dict(room)], "santrauka": {}}
    p["_meta"]["lapu_rusys_is_teksto"] = {"rusys": {"3": "electrical"}}
    rows = {r["aprasymas"]: r for r in _build_pozicijos_from_rooms(json.loads(json.dumps(p)))["pozicijos"]}
    assert rows["Lubinių priglaistomų šviestuvų montavimas"]["kiekis"] == 12
    assert rows["Lubinių priglaistomų šviestuvų montavimas"]["_kilme"] == "drawing"
    assert rows["Rozetės / jungiklio pajungimas"]["kiekis"] == 10
    assert rows["Pakabinamų šviestuvų montavimas"]["kiekis"] is None
    assert rows["Pakabinamų šviestuvų montavimas"]["_kilme"] == "blank"
    # a model's glance at the glyphs is no count
    q = {"patalpos": [dict(room)], "santrauka": {}, "detected_symbols_summary": {"sviestuvai": 40}}
    rows = {r["aprasymas"]: r for r in _build_pozicijos_from_rooms(q)["pozicijos"]}
    assert rows["Lubinių priglaistomų šviestuvų montavimas"]["kiekis"] is None


def test_the_plumbing_reading_is_the_legend_never_the_old_model_count():
    from extractor.vision_call import plumbing_reading
    legacy = {"_meta": {"fixtures_status": "ok", "fixtures_counts": {"klozetai": 2}},
              "detected_symbols_summary": {"klozetai": 2, "praustuves": 3}}
    assert plumbing_reading(legacy) is None
    got = plumbing_reading(_proposal(klozetai=2, vonios_kubilai=1))
    assert got["klozetai"] == 2 and got["vonios"] == 1 and got["praustuves"] == 0


# ── vector symbols: touching copies ─────────────────────────────────────────────────────────────────────────

def _ring(x, y, d=6.4):
    return {"x0": x, "x1": x + d, "top": y, "bottom": y + d}


def test_a_run_of_touching_rings_is_split_into_its_copies():
    from extractor.vector_symbols import _side_by_side
    two = [_ring(0, 0), _ring(1.8, 1.8, 2.8), _ring(6.4, 0), _ring(8.2, 1.8, 2.8)]
    assert len(_side_by_side(two)) == 2
    three_vertical = [_ring(0, 0), _ring(0, 6.4), _ring(0, 12.8)]
    assert len(_side_by_side(three_vertical)) == 3


def test_a_slot_or_a_ring_with_petals_stays_one_symbol():
    from extractor.vector_symbols import _side_by_side
    slot = [{"x0": 0, "x1": 20, "top": 0, "bottom": 0.4}, {"x0": 0, "x1": 20, "top": 1.6, "bottom": 2.0}]
    assert _side_by_side(slot) is None
    petals = [_ring(2, 2, 6), {"x0": 0, "x1": 2, "top": 4, "bottom": 6}, {"x0": 8, "x1": 10, "top": 4, "bottom": 6}]
    assert _side_by_side(petals) is None


# ── sheet kinds from the title text ─────────────────────────────────────────────────────────────────────────

def _sheet_pdf(pages: list[list[tuple[float, float, str]]]) -> bytes:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    W, H = landscape(A3)
    c = canvas.Canvas(buf, pagesize=(W, H))
    font = "Helvetica"
    for cand in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(cand).exists():
            pdfmetrics.registerFont(TTFont("LT", cand))
            font = "LT"
            break
    for items in pages:
        c.setFont(font, 9)
        for fx, fy, text in items:
            c.drawString(fx * W, (1 - fy) * H, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_the_title_block_decides_the_sheet_kind_and_a_note_does_not():
    from text.page_kind import apply_text_page_kinds, page_kinds
    pdf = _sheet_pdf([
        [(0.80, 0.93, "LUBŲ PLANAS M1:50"), (0.2, 0.3, "Žr. išklotinėse")],
        [(0.80, 0.93, "SANTECHNIKOS PLANAS"), (0.3, 0.5, "Vandens įvadas skalbimo mašinai")],
        [(0.80, 0.93, "sanalp sokinhcetnaS")],
        [(0.3, 0.3, "kažkoks tekstas be pavadinimo")],
    ])
    kinds = page_kinds(pdf)
    assert [k["tipas"] for k in kinds] == ["ceiling_plan", "plumbing", "plumbing", "unknown"]
    assert kinds[0]["saltinis"] == "antspaudas"
    parsed = {"puslapiai": [{"nr": 1, "tipas": "wall_elevation"}]}
    assert apply_text_page_kinds(parsed, pdf) == 3
    assert parsed["puslapiai"][0] == {**parsed["puslapiai"][0], "tipas": "ceiling_plan",
                                      "tipas_modelio": "wall_elevation", "tipas_saltinis": "antspaudas"}
    assert parsed["_meta"]["lapu_rusys_is_teksto"]["rusys"]["4"] == "unknown"


def test_door_types_are_read_from_the_text():
    from extractor.door_type_reader import read_door_types
    pdf = _sheet_pdf([[(0.80, 0.93, "PERTVARŲ PLANAS"), (0.2, 0.2, "D-1 Durų anga skirta beapvadinėms durims"),
                       (0.4, 0.4, "D-2 skirta beapvadinėms durims"), (0.5, 0.6, "Stumdomos durys"),
                       (0.1, 0.8, "Visos vidaus durys beapvadinės")]])
    out = read_door_types(pdf, [])
    assert out["status"] == "ok" and out["beapvadines_count"] == 2 and out["stumdomos_count"] == 1
    assert out["bendras_tipas"] == "beapvadines" and out["_meta"]["model"] is None


def test_a_door_type_count_only_from_the_text_keeps_the_frameless_row():
    from extractor.vision_call import _gate_frameless
    row = {"aprasymas": "Durų angų paruošimas beapvadinėms durims", "kiekis": 12.0}
    _gate_frameless([row], {"_door_types": {"reader_beapvadines": 3, "saltinis": "tekstas"}})
    assert row["_kilme"] == "drawing"
    old = {"aprasymas": "Durų angų paruošimas beapvadinėms durims", "kiekis": 12.0}
    _gate_frameless([old], {"_door_types": {"reader_beapvadines": 3}})        # a model's reading of the image
    assert old["_kilme"] == "blank" and old["kiekis"] is None


def test_a_finish_breakdown_a_model_estimated_comes_off():
    from extractor.vision_call import apply_apdailos
    parsed = {"patalpos": [{"nr": "1", "pavadinimas": "Vonia", "sienu_apdailos_breakdown": {"plyteles_share": 0.8}},
                           {"nr": "2", "sienu_apdailos_breakdown": {"dazymas_share": 1.0}, "_apdailos_saltinis": "tekstas"}]}
    apply_apdailos(parsed, None)
    assert "sienu_apdailos_breakdown" not in parsed["patalpos"][0]
    assert parsed["patalpos"][0]["_apdailos_modelio"] == {"plyteles_share": 0.8}
    assert parsed["patalpos"][1]["sienu_apdailos_breakdown"] == {"dazymas_share": 1.0}
    assert parsed["_meta"]["apdailos_modelio_nuimta"] == 1


def test_the_finish_kinds_a_rooms_own_sheet_writes():
    from extractor.apdailos_reader import read_apdailos_finishes
    pdf = _sheet_pdf([[(0.8, 0.93, "101 VONIOS KAMBARIO IŠKLOTINĖS"), (0.2, 0.3, "Plytelės 60x120 iki lubų")],
                      [(0.8, 0.93, "MIEGAMASIS IŠKLOTINĖS"), (0.2, 0.3, "Sienos dažomos"), (0.2, 0.4, "Tapetai")],
                      [(0.8, 0.93, "101, 102 IŠKLOTINĖS"), (0.2, 0.3, "Mikrocementas")]])
    rooms = [{"nr": "101", "pavadinimas": "Vonios kambarys"}, {"nr": "102", "pavadinimas": "Miegamasis"}]
    out = read_apdailos_finishes(pdf, rooms)
    by = {r["nr"]: r for r in out["patalpos"]}
    assert by["101"]["sienu_apdaila"] == {"plyteles_share": 1.0}
    assert by["102"]["apdailos_rusys"] == ["dazymas", "tapetai"] and "sienu_apdaila" not in by["102"]
    assert "kita_danga" not in by["101"]["apdailos_rusys"]     # a sheet naming two rooms decides neither


def test_the_zoom_picks_only_rooms_the_drawing_does_not_measure():
    from extractor.vision_call import zoom_wanted
    assert not zoom_wanted({"plotas_saltinis": "eksplikacija"})
    assert not zoom_wanted({"plotas_saltinis": "vision", "polygon_source": "vektoriniai_konturai"})
    assert zoom_wanted({"plotas_saltinis": "vision"})


def test_the_unused_height_helpers_are_gone():
    import extractor.vision_call as vc
    assert not hasattr(vc, "_apply_per_room_heights") and not hasattr(vc, "_model_height_resolved")


# ── the corpus (skipped without the fixture PDFs) ────────────────────────────────────────────────────────────

@pytest.mark.skipif(not H_PDF.is_file(), reason="fixture PDF not present")
def test_objektas_h_sheet_kinds_and_legend_counts():
    from extractor.legend_counts import auto_legend_counts
    from text.page_kind import page_kinds
    pdf = H_PDF.read_bytes()
    assert [k["tipas"] for k in page_kinds(pdf)] == ["floor_plan", "electrical", "electrical", "plumbing",
                                                     "ceiling_plan", "floor_plan", "floor_plan", "floor_plan"]
    got = auto_legend_counts(pdf)
    fams = {k: v["kiekis"] for k, v in got["seimos"].items()}
    # eye-checked: 9 diffusers (3 + 4 + 2), 27 switches; his sąmata bills 20 ceiling lights (we propose 25 — the
    # proposal he confirms), 5 pendant outlets
    assert fams["difuzoriai"] == 9 and fams["jungikliai"] == 27
    assert fams["sviestuvai_pakabinami"] == 5 and fams["sviestuvai"] == 25
