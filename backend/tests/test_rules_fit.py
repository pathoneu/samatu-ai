"""rules/fit.py — the search logic, on a fake scorer (the real fit replays the corpus and is run by hand)."""
from __future__ import annotations

from rules import fit


class _FakeScorer:
    """Share = 50 when kampai is 'vertikalus' on project p1, else 10; aperture 3,0 adds 5 everywhere."""
    snaps = {"p1": {}, "p2": {}, "p3": {}}

    def share(self, slug, config, apimtis=None):
        s = 10.0
        if slug == "p1" and config["kampai"] == "vertikalus":
            s = 50.0
        if config["aperture_no_deduct_max_m2"] == 3.0:
            s += 5.0
        return s

    def mean(self, slugs, config):
        return sum(self.share(s, config) for s in slugs) / len(slugs)


def test_descent_moves_only_on_a_real_gain_and_keeps_defaults_on_ties():
    sc = _FakeScorer()
    cfg = fit.descend(sc, ["p1", "p2", "p3"])
    assert cfg["kampai"] == "vertikalus" and cfg["aperture_no_deduct_max_m2"] == 3.0
    assert cfg["skirting_door_deduct_m"] == fit.DEFAULTS["skirting_door_deduct_m"]     # no gain → default
    assert cfg["reveals_scope"] == fit.DEFAULTS["reveals_scope"]
    loo = fit.descend(sc, ["p2", "p3"])                                                 # p1 held out
    assert loo["kampai"] == "visi", "a project's own quirk must not be chosen when it is the held-out one"


def test_overrides_route_profile_keys_and_the_rotband_share():
    ov = fit.overrides_for({**fit.DEFAULTS, "rotband_dalis": 50})
    assert ov["apimtis"] == {"rotband": "dalis", "rotband_dalis": 50}
    assert "rotband_dalis" not in ov["profilis"] and ov["profilis"]["kampai"] == "visi"
    assert "apimtis" not in fit.overrides_for(fit.DEFAULTS)


def test_usable_projects_are_codenames_only():
    assert all(s.startswith("objektas_") for s in fit.USABLE)
