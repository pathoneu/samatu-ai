"""Sheet references, pure matching (api/sheet_refs.py) — the rules a sheet link is found by.

Fixtures are lines as the text layer gives them: (text, one box per character). The phrases are the
forms seen in the corpus PDFs (2026-10-16 scan): „žiūrėti iškl.", „Rozečių pririšimus tikslinti
išklotinėse", elevation tags a1…h4 on the finishes plan against sheets named „Išklotinės a1-a9",
a document code printed on every sheet of a bundle, „TS-04" listed on a document index."""
from __future__ import annotations

from api.sheet_refs import (
    build_sheet_index, code_aliases, declared_tags, find_callouts, fold, line_text, span_box,
    split_code, title_block_codes,
)


def _line(text: str, x0: float = 100.0, top: float = 200.0, w: float = 5.0):
    """A text line with one 5-pt box per character, spaces as real gaps."""
    chars = []
    x = x0
    for ch in text:
        if ch != " ":
            chars.append({"text": ch, "x0": x, "x1": x + w * 0.9, "top": top, "bottom": top + 6, "size": 6})
        x += w
    return line_text(chars)


SHEETS = [
    {"page": 1, "name": "Interjero projektas", "tipas": "title_page"},
    {"page": 2, "name": "Pertvarų planas", "tipas": "floor_plan"},
    {"page": 3, "name": "Lubų planas", "tipas": "ceiling_plan"},
    {"page": 4, "name": "Išklotinių ir apdailų planas", "tipas": "finish_schedule"},
    {"page": 5, "name": "Išklotinės a1-a9 (Svetainė)", "tipas": "wall_elevation"},
    {"page": 6, "name": "Išklotinės b1-b3, c1-c4 (Darbo kamb.)", "tipas": "wall_elevation"},
    {"page": 7, "name": "SKERSINIS PJŪVIS A-A, M1:25", "tipas": "section"},
    {"page": 8, "name": "IN.1A.-B.08 VONIOS IŠKLOTINĖS M 1:50", "tipas": "wall_elevation"},
]


def _found(page, texts, sheets=SHEETS, codes=None, page_count=8):
    index = build_sheet_index(sheets, codes)
    lines = [_line(t, top=100 + 10 * i) for i, t in enumerate(texts)]
    return [(c.text, c.target_page, c.other_pages, c.confidence, c.kind)
            for c in find_callouts(page, lines, index, page_count)]


def test_fold_drops_case_and_lithuanian_marks():
    assert fold("IŠKLOTINĖS") == "isklotines"
    assert fold("Žiūrėti") == "ziureti"


def test_split_code_reads_the_leading_sheet_number():
    assert split_code("IN.1A.-B.01 1A. BALDŲ PLANAS M 1:50") == ("IN.1A.-B.01", "1A. BALDŲ PLANAS M 1:50")
    assert split_code("IŠDĖSTYMO PLANAS (su patalpų eksplikacija)") == (None, "IŠDĖSTYMO PLANAS (su patalpų eksplikacija)")
    assert split_code("1A. BALDŲ PLANAS") == (None, "1A. BALDŲ PLANAS")


def test_code_aliases_keep_the_short_form():
    assert code_aliases("IN.1A.-B.01") == {"in.1a.-b.01", "b.01"}
    assert code_aliases("LVN-03") == {"lvn-03"}
    assert code_aliases(None) == set()


def test_declared_tags_expand_ranges_and_lists():
    assert declared_tags("Išklotinės b1-b3, c1-c4 (Darbo kamb)") == {"b1", "b2", "b3", "c1", "c2", "c3", "c4"}
    assert declared_tags("Lubų planas") == set()


def test_line_text_inserts_spaces_at_gaps_and_keeps_boxes():
    text, boxes = _line("žr. lapą 3")
    assert text == "žr. lapą 3"
    assert boxes[2] is not None and boxes[3] is None          # the gap is a space without a box
    b = span_box(boxes, 0, len(text))
    assert b[0] == 100.0 and b[2] > 140


def test_explicit_reference_to_a_page_number():
    got = _found(2, ["Durų detalės žr. lapą 3"])
    assert got == [("žr. lapą 3", 3, [], "medium", "nuoroda")]


def test_explicit_reference_to_a_sheet_number_is_high():
    got = _found(2, ["žr. br. B.08"])
    assert got == [("žr. br. B.08", 8, [], "high", "nuoroda")]


def test_bare_sheet_number_links_with_medium_confidence():
    got = _found(3, ["Plytelės — B.08"])
    assert got == [("B.08", 8, [], "medium", "numeris")]


def test_a_number_never_links_its_own_sheet():
    assert _found(8, ["IN.1A.-B.08", "B.08"]) == []


def test_title_block_code_identifies_a_sheet_without_a_coded_name():
    sheets = [{"page": 1, "name": "", "tipas": "unknown"}, {"page": 2, "name": "", "tipas": "unknown"}]
    got = _found(1, ["Techninės specifikacijos TS-04"], sheets=sheets, codes={2: ["TS-04"]}, page_count=2)
    assert got == [("TS-04", 2, [], "medium", "numeris")]


def test_a_code_on_every_sheet_is_the_documents_number_not_a_sheets():
    sheets = [{"page": p, "name": "", "tipas": "wall_elevation"} for p in (1, 2, 3)]
    assert _found(1, ["SA.B-02"], sheets=sheets, codes={1: ["SA.B-02"], 2: ["SA.B-02"], 3: ["SA.B-02"]}, page_count=3) == []


def test_elevation_tags_link_to_the_sheet_whose_name_declares_them():
    got = _found(4, ["a7", "103 Koridorius 9.64 m² h4", "b2 c3"])
    assert ("a7", 5, [], "medium", "zyma") in got
    assert ("b2", 6, [], "medium", "zyma") in got and ("c3", 6, [], "medium", "zyma") in got
    assert not any(t == "h4" for t, *_ in got)                 # no sheet declares h4


def test_tags_keep_their_case_a_paper_size_is_not_a_tag():
    assert _found(4, ["Formatas A1"]) == []


def test_see_word_before_a_kind_of_sheet_links_to_every_sheet_of_that_kind():
    got = _found(2, ["Plytelių išdėstymą žiūrėti iškl."])
    assert got == [("žiūrėti iškl.", 5, [6, 8], "low", "tipas")]


def test_locative_form_is_a_reference_on_its_own():
    got = _found(3, ["Rozečių pririšimus tikslinti išklotinėse."])
    assert got[0][1:] == (5, [6, 8], "low", "tipas")
    assert got[0][0] == "tikslinti išklotinėse"


def test_a_title_naming_its_own_kind_is_not_a_reference():
    # the nominative „Išklotinės" is a heading, not a pointer; and an elevation sheet means itself
    assert _found(2, ["IŠKLOTINĖS"]) == []
    assert _found(5, ["Plytelių išdėstymą žiūrėti iškl."]) == []


def test_ceiling_plan_in_accusative_after_a_see_word():
    got = _found(2, ["Šviestuvų vietas žr. lubų planą"])
    assert got == [("žr. lubų planą", 3, [], "medium", "tipas")]


def test_section_mark_links_to_the_section_sheet():
    got = _found(2, ["A-A"])
    assert got == [("A-A", 7, [], "medium", "pjuvis")]


def test_labelled_section_links_and_unknown_detail_does_not():
    assert _found(2, ["skersinis pjūvis A-A"]) == [("pjūvis A-A", 7, [], "medium", "detale")]
    assert _found(2, ["MAZGAS B, M 1:25"]) == []


def test_another_sheets_full_name_on_the_page():
    got = _found(3, ["Pertvaros pagal: Pertvarų planas"])
    assert ("Pertvarų planas", 2, [], "medium", "pavadinimas") in got


def test_spans_are_claimed_once_strongest_rule_first():
    got = _found(2, ["žr. br. B.08"])
    assert len(got) == 1 and got[0][4] == "nuoroda"


def test_no_other_sheets_no_callouts():
    assert _found(1, ["žr. lapą 2"], sheets=[{"page": 1, "name": "Planas", "tipas": "floor_plan"}], page_count=1) == []


def test_title_block_codes_come_from_the_lower_right_corner():
    W, H = 600.0, 400.0
    lines = [_line("B.01", x0=560, top=380), _line("A-02", x0=20, top=20)]
    assert title_block_codes(lines, W, H) == ["B.01"]
