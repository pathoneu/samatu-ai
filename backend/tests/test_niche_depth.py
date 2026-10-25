"""v3 W5-E E3 — niche depth input (nisos_gylis_m) and the §1.5 term behind SAMATU_NICHE_DEPTH (default off)."""
import json

from extractor import niche_depth as nd
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def _parsed(depth_room=None, depth_project=None, second_depth=None):
    rooms = []
    for nr, name, m, d in (("1", "Svetainė", 4.0, depth_room), ("2", "Miegamasis", 3.0, second_depth)):
        r = {"nr": nr, "pavadinimas": name, "paskirtis": "svetaine", "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys",
             "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "n_doors": 1, "n_windows": 1}
        r.update(calc_room_quantities(r))
        r["nisu_metrai"] = m
        r["elementai"] = [{"tipas": "nisa_LED", "ilgis_m": m}]
        if d is not None:
            r[nd.KEY] = d
        rooms.append(r)
    blob = {"patalpos": rooms, "santrauka": {}}
    if depth_project is not None:
        blob["_overrides"] = {nd.KEY: depth_project}
    return json.loads(json.dumps(blob))


def _rows(monkeypatch, flag, **kw):
    if flag is None:
        monkeypatch.delenv(nd.FLAG_ENV, raising=False)
    else:
        monkeypatch.setenv(nd.FLAG_ENV, flag)
    return _build_pozicijos_from_rooms(_parsed(**kw))["pozicijos"]


# the builder folds „LED nišų glaistymas" + „LED nišų dažymas" into one row (_consolidate_led_niche_pozicijos)
FIN = "LED nišų glaistymas/dažymas"


def _niche_rows(poz):
    return {p["aprasymas"]: (p["vnt"], p["kiekis"]) for p in poz if "nišų" in str(p.get("aprasymas", "")).lower()}


def test_depth_input():
    assert nd.room_depth({nd.KEY: "0,15"}, None) == 0.15
    assert nd.room_depth({}, {nd.KEY: 0.2}) == 0.2
    assert nd.room_depth({nd.KEY: 0.1}, {nd.KEY: 0.2}) == 0.1            # the room's own wins
    assert nd.room_depth({nd.KEY: 5}, None) is None                       # a typing slip is no depth
    assert nd.room_depth({}, None) is None


def test_flag_off_identical(monkeypatch):
    a = _rows(monkeypatch, None, depth_project=0.15)
    b = _rows(monkeypatch, "0", depth_project=0.15)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    # v4 3b: per-room niche lengths are Pass-1's — without a legend length the row is blank
    assert _niche_rows(a)[FIN] == ("m", None)




