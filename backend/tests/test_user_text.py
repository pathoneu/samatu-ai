"""The runtime prose guard (extractor/user_text.py) — old stored prose must not
reach the screen, current guidance must pass through untouched."""
import json
import os

import pytest

from extractor import user_text
from extractor.confidence import CLASS_RULES, _OVERBILLING_RULES

OLD = ("Formulė kalibruota pagal 1 rangovo samatą (Kliento) — apima ginčytiną pusinių "
       "kampų ir perimetro dedamąją; tikslumas nepatvirtintas (reikia daugiau etalonų); "
       "Ekstrakcijos paleidimai nesutarė dėl 1 patalpų geometrijos; Gretimybės analizė "
       "nerado pertvarų — kampų suma be pusinių kampų (žinomai per maža)")


@pytest.mark.parametrize("reason", [r[2] for r in CLASS_RULES + _OVERBILLING_RULES],
                         ids=[r[0] for r in CLASS_RULES + _OVERBILLING_RULES])
def test_current_rule_reasons_pass_through_untouched(reason):
    assert user_text.scrub_text(reason) == reason


def test_old_confession_is_fully_removed():
    out = user_text.scrub_text(OLD)
    assert not user_text.is_banned(out)
    for tok in ("kalibruota", "rangovo", "etalon", "Ekstrakcij", "Gretimyb", "žinomai"):
        assert tok.lower() not in out.lower()
    assert out  # never empty — falls back to generic guidance


def test_clean_clause_survives_next_to_a_banned_one():
    mixed = "Palyginkite su durų specifikacija. Kalibruota pagal etaloną (2 projektai)."
    assert user_text.scrub_text(mixed) == "Palyginkite su durų specifikacija."


def test_scrub_prose_walks_a_project_blob_and_leaves_labels_alone():
    blob = {
        "darbu_sarasas": [{
            "aprasymas": "Dažymo kampų montavimas", "kiekis": 10,
            "_confidence_reason": OLD,
            "_assumption": "Sprint 4 Block B: patikrink shared-walls correction",
            "roll_up": [{"op": "sum", "label": "Σ", "value": 10, "note": "recall 0.6 vs etalonas"}],
            "contributions": [{"room_nr": "101", "included_because": "Patalpa dažoma"}],
        }],
        "lt_sanity": {"warnings": [{"message": "Sienų plotas per mažas (Vision recall)"}]},
        "_wall_finish_assumptions": ["Sienos dažomos pagal paskirtį", "kalibruota pagal etaloną"],
    }
    out = user_text.scrub_prose(blob)
    row = out["darbu_sarasas"][0]
    assert row["aprasymas"] == "Dažymo kampų montavimas" and row["kiekis"] == 10
    assert not user_text.is_banned(row["_confidence_reason"])
    assert not user_text.is_banned(row["_assumption"])
    assert not user_text.is_banned(row["roll_up"][0]["note"])
    assert row["contributions"][0]["included_because"] == "Patalpa dažoma"
    assert not user_text.is_banned(out["lt_sanity"]["warnings"][0]["message"])
    assert out["_wall_finish_assumptions"][0] == "Sienos dažomos pagal paskirtį"
    assert not user_text.is_banned(out["_wall_finish_assumptions"][1])
    assert json.dumps(blob, ensure_ascii=False).count("kalibruota") == 2  # input untouched


def test_refresh_reasons_prefers_the_current_rule_for_the_label():
    rows = [{"aprasymas": "Dažymo kampų montavimas", "_confidence_reason": OLD},
            {"aprasymas": "Kažkas be taisyklės", "_confidence_reason": OLD},
            {"aprasymas": "Sienų dažymas", "_confidence_reason": "Patikrinkite plotą."}]
    n = user_text.refresh_reasons(rows)
    assert n == 2
    assert rows[0]["_confidence_reason"] == user_text.reason_for_label("Dažymo kampų montavimas")
    assert not user_text.is_banned(rows[1]["_confidence_reason"])
    assert rows[2]["_confidence_reason"] == "Patikrinkite plotą."


def test_confidential_terms_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("SAMATU_CONFIDENTIAL_TERMS", "Slaptas klientas, Kita gatvė 7")
    assert user_text.is_banned("Skaičiuota pagal Slaptas Klientas projektą")
    assert user_text.scrub_text("Skaičiuota pagal Slaptas Klientas projektą. Patikrinkite.") == "Patikrinkite."
    assert not user_text.is_banned("Patikrinkite pagal brėžinį")


def test_scrub_all_projects_rewrites_only_dirty_blobs(tmp_path, monkeypatch):
    import db
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "t.db")
    db.init_schema()
    uid = db.create_user("guard@test.lt", "!test")["id"]
    db.upsert_project("p-dirty", {"darbu_sarasas": [{"aprasymas": "X", "_confidence_reason": OLD}]}, user_id=uid)
    db.upsert_project("p-clean", {"darbu_sarasas": [{"aprasymas": "Y", "_confidence_reason": "Patikrinkite."}]}, user_id=uid)
    assert db.scrub_all_projects() == 1
    assert not user_text.is_banned(db.get_project("p-dirty")["darbu_sarasas"][0]["_confidence_reason"])
    assert db.scrub_all_projects() == 0  # idempotent


def test_scrub_all_projects_runs_once_per_version_and_can_be_forced(tmp_path, monkeypatch):
    """2026-09-16: the pass froze production for ~90 s after every deploy.
    It now runs once per SCRUB_VERSION; a bumped version or force=True re-runs."""
    import db
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "scrub.db")
    db.init_schema()
    db.upsert_project("p1", {"name": "A", "pastabos": ["Pagal metodiką"]})
    assert db.get_state("scrub_all_projects") is None
    db.scrub_all_projects()
    assert db.get_state("scrub_all_projects") == db.SCRUB_VERSION
    # a dirty blob written behind the scrubber's back is left alone by a repeat boot…
    with db._conn() as c:
        c.execute("UPDATE projects SET data = ? WHERE id = ?", ('{"name": "A", "pastabos": ["Pagal metodiką"]}', "p1"))
    assert db.scrub_all_projects() == 0
    # …until the version bumps or the caller forces it
    monkeypatch.setattr(db, "SCRUB_VERSION", "next")
    assert db.scrub_all_projects() >= 0 and db.get_state("scrub_all_projects") == "next"
    assert db.scrub_all_projects(force=True) >= 0
