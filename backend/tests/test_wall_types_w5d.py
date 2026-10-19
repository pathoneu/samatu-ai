"""D9 (Pathon v3 W5-D): wall and partition types the drawing's legends name — a fact beside the walls, with its
crop; never a quantity. Corpus (no client data here): objektas_b p1 „Naujai statomos pertvaros…" (nauja) and
„Esamos … sienos" (esama); objektas_h p8's wall legend is in a broken font — pointed at, never quoted."""
from __future__ import annotations

from extractor.room_facts import attach_crop_urls, build_room_facts, wall_type_evidence
from extractor.wall_types import kind_of, readable, wall_type_sentence


def test_kinds_and_readability():
    assert kind_of("Naujai statomos pertvaros/sienos") == "nauja"
    assert kind_of("Esamos vidinės ir išorės sienos") == "esama"
    assert kind_of("Griaunamos sienos") == "griaunama"
    assert kind_of("GK pertvara 100 mm") is None
    assert readable("Naujai statomos pertvaros/sienos/sienutės")
    assert not readable("Naðjai ¦ÐÞmðÐjama siena i¿i ÂðųȈ")


def _project(**meta):
    return {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}],
            "patalpos": [{"nr": "1", "puslapio_nr": 1, "paskirtis": "kambarys", "plotas_m2": 12, "perimetras_m": 14}],
            "_meta": meta}


def test_the_walls_fact_carries_the_types_with_their_crops():
    rec = {"eilutes": [{"page": 1, "tekstas": "Naujai statomos pertvaros/sienos/sienutės", "rusis": "nauja",
                        "spalva": "#cd6928", "rect_pct": [0.08, 0.82, 0.21, 0.84]}],
           "neperskaityta": [8]}
    project = _project(sienu_tipai=rec)
    ev = wall_type_evidence(project)
    assert ev[0]["sentence"] == wall_type_sentence(rec["eilutes"][0])
    assert "(nauja)" in ev[0]["sentence"] and ev[0]["rect_pct"] == [0.08, 0.82, 0.21, 0.84]
    assert ev[1]["page"] == 8 and ev[1]["rect_pct"] is None and "perskaityti" in ev[1]["sentence"]
    payload = build_room_facts(project, "1")
    holders = [f for f in payload["facts"] if f.get("sienu_tipai")]
    assert len(holders) == 1 and holders[0]["key"] in ("pertvaros", "apdaila")
    attach_crop_urls(payload, "demo-x")
    assert all(e["crop_url"] for e in holders[0]["sienu_tipai"])
    # evidence only: the fact's value is what it was without it
    plain = next(f for f in build_room_facts(_project(), "1")["facts"] if f["key"] == holders[0]["key"])
    assert plain["value"] == holders[0]["value"] and "sienu_tipai" not in plain
