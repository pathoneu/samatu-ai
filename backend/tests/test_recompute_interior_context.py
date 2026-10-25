"""/recompute-interior must not lose the project-level context on the way in.

F4, 2026-09-02 final review. `RecomputePayload` listed only patalpos, overrides
and two scalars, so pydantic dropped everything else the caller sent. Two
casualties:

  · `_ceiling_anchor` — the eksplikacijos "Iš viso" the Lubų quantity is billed
    off. One round trip through this endpoint un-anchored the row: the billed
    number fell back to the per-room sum and the provenance line saying where it
    came from vanished. Reachable from the UI today (ConfidenceBadge
    "✓ patvirtinti" → projectStore `samatu:project-recompute` → InteriorProject
    handleRoomsChange → POST here), and also from updateRoomPolygon and the
    rooms-grid edit.
  · the reader context `/api/recompute-quantities` already accepts
    (`_door_types`, `detected_symbols_summary`, `_plyteliu_specs`,
    `_symbol_legend`). `_build_pozicijos_from_rooms` reads all of them, so a
    rebuild here silently dropped the door/fixture/tile lines.

The pydantic detail that caused it: a field NAMED `_ceiling_anchor` is a private
attribute in v2, never a request field. The model carries `ceiling_anchor` with
that alias instead.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client(monkeypatch):
    # Bypass auth/billing — the wiring under test sits after both.
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _room(nr: str, **kw) -> dict:
    r = {"nr": nr, "pavadinimas": f"Kambarys {nr}", "paskirtis": "gyvenamoji",
         "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
         "elementai": []}
    r.update(kw)
    return r


ROOMS = [_room("101"), _room("102")]          # 40 m² of floor, 40 m² of ceiling
ANCHOR = {"total_area_m2": 40.5, "label": "Iš viso", "page": 2}


def _lubos(body: dict) -> list[dict]:
    return [p for p in body["pozicijos"]
            if str(p.get("aprasymas", "")).startswith("Lubų glaistymas/dažymas")]


# ── the model ────────────────────────────────────────────────────────────────

def test_the_anchor_reaches_the_model_under_its_underscored_key():
    p = main.RecomputePayload(**{"patalpos": ROOMS, "_ceiling_anchor": ANCHOR})
    assert p.ceiling_anchor == ANCHOR
    # …and survives a dump/reload, which is what a saved blob does to it.
    again = main.RecomputePayload(**p.model_dump(by_alias=True))
    assert again.ceiling_anchor == ANCHOR


def test_the_plain_field_name_also_works():
    """populate_by_name — direct callers and tests should not have to know
    about the alias."""
    p = main.RecomputePayload(patalpos=ROOMS, ceiling_anchor=ANCHOR)
    assert p.ceiling_anchor == ANCHOR


def test_an_absent_anchor_is_none_not_an_error():
    assert main.RecomputePayload(patalpos=ROOMS).ceiling_anchor is None
    assert main.RecomputePayload(patalpos=ROOMS).context == {}


# ── the round trip ───────────────────────────────────────────────────────────

def test_the_anchored_ceiling_quantity_survives_the_round_trip(client):
    r = client.post("/recompute-interior",
                    json={"patalpos": ROOMS, "_ceiling_anchor": ANCHOR})
    assert r.status_code == 200, r.text
    body = r.json()

    lubos = _lubos(body)
    assert len(lubos) == 1, [p["aprasymas"] for p in body["pozicijos"]]
    assert lubos[0]["kiekis"] == pytest.approx(40.5)
    assert "Iš eksplikacijos lentelės" in lubos[0]["_confidence_reason"]
    # The anchor itself comes back too, so the frontend blob keeps it and the
    # NEXT round trip can send it again.
    assert body["_ceiling_anchor"] == ANCHOR


def test_without_the_anchor_the_per_room_sum_is_billed(client):
    """The control: the difference the anchor makes has to be visible, or the
    test above would pass on a number that was never anchored."""
    r = client.post("/recompute-interior", json={"patalpos": ROOMS})
    assert r.status_code == 200, r.text
    lubos = _lubos(r.json())
    assert len(lubos) == 1
    assert lubos[0]["kiekis"] == pytest.approx(40.0)
    assert "eksplikacijos" not in (lubos[0].get("_confidence_reason") or "")


def test_an_implausible_anchor_is_still_refused_end_to_end(client):
    """The guard in `_ceiling_paint_base` must not be bypassed by arriving over
    HTTP: a total 3× our floor area belongs to another storey."""
    r = client.post("/recompute-interior", json={
        "patalpos": ROOMS,
        "_ceiling_anchor": {"total_area_m2": 120.0, "label": "Iš viso"},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert _lubos(body)[0]["kiekis"] == pytest.approx(40.0)
    assert any(w.get("code") == "eksplikacija_total_ignored"
               for w in body.get("warnings", []) if isinstance(w, dict))


# ── the reader context ───────────────────────────────────────────────────────

def test_the_reader_context_reaches_the_positions_builder(client):
    """`detected_symbols_summary` raises the fixture counts above the
    room-derived floor. Without the context forwarded the builder saw {}, so the
    drawing's own count was lost on every recompute and the room-type default
    silently won."""
    rooms = ROOMS + [_room("103", paskirtis="vonia", plotas_m2=6.0,
                           perimetras_m=10.0, perimetras_saltinis="plano_matmenys")]

    def _praustuves(body):
        rows = [p for p in body["pozicijos"]
                if p.get("aprasymas") == "Praustuvės montavimas"]
        assert len(rows) == 1, [p["aprasymas"] for p in body["pozicijos"]]
        return rows[0]["kiekis"]

    with_ctx = client.post("/recompute-interior", json={
        "patalpos": rooms,
        "context": {"detected_symbols_summary": {"praustuves": 3}, "_meta": {"fixtures_status": "ok"}},
    })
    assert with_ctx.status_code == 200, with_ctx.text
    without = client.post("/recompute-interior", json={"patalpos": rooms})
    assert without.status_code == 200, without.text

    assert _praustuves(with_ctx.json()) == 3       # the plumbing reader's count
    assert _praustuves(without.json()) is None      # a room-type count is a blank row (v4 3b)


def test_the_explicit_fields_win_over_a_stale_copy_in_the_context(client):
    """A blob can carry an old `_ceiling_anchor`/`patalpos` inside the context
    it forwards. The named fields are the request; the context is background."""
    r = client.post("/recompute-interior", json={
        "patalpos": ROOMS,
        "_ceiling_anchor": ANCHOR,
        "context": {
            "_ceiling_anchor": {"total_area_m2": 999.0, "label": "Senas"},
            "patalpos": [_room("999", plotas_m2=1.0)],
            "pozicijos": [{"aprasymas": "Šiukšlė", "kiekis": 1}],
        },
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["_ceiling_anchor"] == ANCHOR
    assert [p["nr"] for p in body["patalpos"]] == ["101", "102"]
    assert not [p for p in body["pozicijos"] if p.get("aprasymas") == "Šiukšlė"]
