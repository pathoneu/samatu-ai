"""What the eval's numbers claim (audit 2026-09-29: testing-eval-1, -2, -12).

- objektas_g/h are in-sample; nothing the harness prints claims a project the
  engine was never tuned on, and every run says there is no blind project.
- The headline is his billed lines — paint, corners, reveals, GKP ceilings,
  Rotband, tiles — Σ of his rows against Σ of ours through the frozen concept
  table of the row scorecard. A metric whose truth and our value are one
  printed figure is listed as copied and kept out of the new averages.
- The row-scorecard holdout says loudly when it scored nothing.
- A `blind: true` project is skipped by the normal eval and scored only by
  --blind-once, which prints one line and appends one line to its log.

Zero network: an autouse fixture fails the test if anything opens a socket or
constructs an Anthropic client. Made-up sąmatas only — no corpus file is read
except the tracked registry.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _refuse(*_a, **_k):
        raise AssertionError("a €0 eval test tried to reach the network")
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    import anthropic
    monkeypatch.setattr(anthropic.Anthropic, "__init__", _refuse)
    monkeypatch.setattr(anthropic.AsyncAnthropic, "__init__", _refuse)


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location(
        "eval_harness_honesty", REPO_ROOT / "eval_harness.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_honesty"] = mod
    spec.loader.exec_module(mod)
    return mod


# A made-up sąmata in his words, and our rows for the same flat.
_HIS = [
    {"nr": "1", "name": "Sienų, lubų glaistymas/dažymas", "unit": "m2", "quantity": 100.0},
    {"nr": "2", "name": "Dažymo kampų montavimas", "unit": "m", "quantity": 50.0},
    {"nr": "3", "name": "Angokraščių apdirbimas GKP", "unit": "m", "quantity": 20.0},
    {"nr": "4", "name": "Langų rėmų sandarinimas perimetru", "unit": "m", "quantity": 30.0},
    {"nr": "5", "name": "GKP ant lubų", "unit": "m2", "quantity": 40.0},
    {"nr": "6", "name": "Sienų lyginimas Rotband", "unit": "m2", "quantity": 30.0},
    {"nr": "7", "name": "Plytelių klijavimas", "unit": "m2", "quantity": 10.0},
    {"nr": "8", "name": "Didžiaformačių plytelių klijavimas", "unit": "m2", "quantity": 5.0},
]
_OURS = [
    {"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų glaistymas/dažymas", "vnt": "m2", "kiekis": 70.0},
    {"skyrius": "Lubų glaistymas dažymas", "aprasymas": "Lubų glaistymas/dažymas", "vnt": "m2", "kiekis": 40.0},
    {"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Dažymo kampų montavimas", "vnt": "m", "kiekis": 45.0},
    {"skyrius": "GKP montavimas", "aprasymas": "Angokraščių apdirbimas GKP", "vnt": "m", "kiekis": 22.0},
    {"skyrius": "GKP montavimas", "aprasymas": "GKP lubų montavimas (standartinis aukštis)", "vnt": "m2", "kiekis": 40.0},
    {"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų lyginimas Knauf Rotband", "vnt": "m2", "kiekis": 21.0},
    {"skyrius": "Plytelių klijavimas", "aprasymas": "Sienų plytelių klijavimas", "vnt": "m2", "kiekis": 16.0},
]
_PAINT = "Dažymas (sienos+lubos)"


def _families(harness, his, ours):
    from extractor.row_scorecard import score_rows
    return {f["family"]: f for f in harness.billed_line_families(score_rows(his, ours))}


def _write_registry(path: Path, entries: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "projects": entries},
                                   allow_unicode=True), encoding="utf-8")


# ── testing-eval-1: no out-of-sample claim ────────────────────────────────────

def test_no_registry_project_is_out_of_sample():
    reg = yaml.safe_load((REPO_ROOT / "ground_truth" / "registry.yaml").read_text(encoding="utf-8"))
    entries = {e["slug"]: e for e in reg["projects"]}
    assert [s for s, e in entries.items() if e.get("out_of_sample")] == []
    for slug in ("objektas_g", "objektas_h"):
        assert entries[slug].get("blind_until") == "2026-09-05"
        assert not entries[slug].get("blind")


def test_no_string_in_the_harness_claims_a_project_never_tuned_on():
    tree = ast.parse((REPO_ROOT / "eval_harness.py").read_text(encoding="utf-8"))
    texts = [n.value for n in ast.walk(tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [t for t in texts if "never tuned on" in t.lower()] == []
    assert [t for t in texts if "OUT-OF-SAMPLE" in t] == []


def test_every_run_says_whether_a_blind_project_exists(harness, capsys):
    harness._print_blindness_banner([])
    out = capsys.readouterr().out
    assert "NO BLIND PROJECT" in out and "developed against" in out
    harness._print_blindness_banner(["objektas_zz"])
    out = capsys.readouterr().out
    assert "NO BLIND PROJECT" not in out
    assert "--blind-once" in out and "developed against" in out


def test_the_legacy_table_is_labelled_pools_as_before_and_stars_copied_cells(harness, capsys):
    rows = [
        {"slug": "objektas_a", "status": "ok", "recomputed": True, "mae_pct": 3.06,
         "metrics_scored": 4, "legacy_copied_points": 1,
         "metrics": [{"label": "Lubų dažomas plotas", "pct_error": 0.0},
                     {"label": "Sienų dažomas plotas", "pct_error": -11.228}],
         "copied": [{"label": "Lubų dažomas plotas"}]},
        {"slug": "objektas_g", "status": "ok", "recomputed": True, "mae_pct": 8.104,
         "metrics_scored": 1, "blind_until": "2026-09-05",
         "metrics": [{"label": "Sienų dažomas plotas", "pct_error": -8.104}]},
    ]
    harness._print_summary_table(rows, 3.06, formerly_blind_mae=8.104)
    out = capsys.readouterr().out
    assert "LEGACY" in out and "OOS" not in out
    assert "+0.00%*" in out and "-11.23%" in out and "-11.23%*" not in out
    assert "Legacy totals MAE   3.06%  (objektas_a: n=4 obs., 1 copied;" in out
    assert "Legacy totals MAE   8.10%  (objektas_g: n=1 obs., 0 copied; blind until 2026-09-05" in out


# ── testing-eval-2: the headline is his billed lines ──────────────────────────

def test_every_family_names_concepts_of_the_frozen_table(harness):
    from extractor.row_scorecard import load_concepts
    keys = {c.key for c in load_concepts()}
    named = [k for _label, _short, ks in harness.BILLED_FAMILIES for k in ks]
    assert [k for k in named if k not in keys] == []
    assert len(named) == len(set(named)), "a concept may sit in one family only"


def test_billed_families_pool_his_rows_per_family(harness):
    f = _families(harness, _HIS, _OURS)
    assert list(f) == [_PAINT, "Dažymo kampai", "Angokraščiai", "GKP lubos", "Rotband", "Plytelės"]
    assert (f[_PAINT]["his"], f[_PAINT]["ours"], f[_PAINT]["pct_error"]) == (100.0, 110.0, 10.0)
    assert f["Dažymo kampai"]["pct_error"] == -10.0
    # Sealing the window frame is not a reveal: his 30 m of it stay out.
    assert (f["Angokraščiai"]["his"], f["Angokraščiai"]["pct_error"]) == (20.0, 10.0)
    assert f["GKP lubos"]["pct_error"] == 0.0 and f["Rotband"]["pct_error"] == -30.0
    # His large-format row joins his other tiles; our tile rows hold every format.
    assert (f["Plytelės"]["his"], f["Plytelės"]["ours"]) == (15.0, 16.0)
    assert {x["status"] for x in f.values()} == {"measured"}


def test_a_billed_family_we_do_not_produce_is_minus_100_never_dropped(harness):
    ours = [r for r in _OURS if "kampų" not in r["aprasymas"]]
    f = _families(harness, _HIS, ours)["Dažymo kampai"]
    assert (f["status"], f["pct_error"], f["ours"]) == ("not_produced", -100.0, None)
    assert "not_produced" in harness.BILLED_POOLED_STATUSES


def test_a_family_he_does_not_bill_is_not_an_observation(harness):
    his = [r for r in _HIS if "Rotband" not in r["name"]]
    assert "Rotband" not in _families(harness, his, _OURS)


def test_his_rows_in_two_units_are_never_summed(harness):
    his = [r for r in _HIS if r["nr"] != "7"] + [
        {"nr": "9", "name": "Plytelių klijavimas", "unit": "vnt", "quantity": 3.0}]
    f = _families(harness, his, _OURS)["Plytelės"]
    assert f["status"] == "unit_mismatch" and f["pct_error"] is None
    assert "unit_mismatch" not in harness.BILLED_POOLED_STATUSES


def test_copied_needs_both_sides_on_the_printed_figure(harness):
    table = [("table", "drawing: Iš viso", 165.61)]
    assert harness.copied_source(165.61, 165.64, table) == ("drawing: Iš viso", 165.61)
    assert harness.copied_source(165.6, 154.97, table) is None, "ours measured, his on the table"
    legend = [("walls_legend", "drawing: legenda", 220.0)]
    assert harness.copied_source(239.4, 220.0, legend) is None, "ours on the legend, his act differs"
    assert harness.copied_source(None, 165.61, table) is None


def test_copied_sources_are_the_figures_the_engine_takes_as_printed(harness):
    parsed = {"_ceiling_anchor": {"total_area_m2": 143.27, "label": "BENDRAS PLOTAS"},
              "bendras_plotas_m2": 143.27,
              "_walls_anchor": {"total_area_m2": 320.0, "label": "sienų apdailos plano legenda"},
              "_floor_anchors": {"laminatas": {"total": 76.65, "label": "grindų plano legenda"}}}
    assert [(k, v) for k, _label, v in harness.copied_sources(parsed)] == [
        ("table", 143.27), ("table", 143.27), ("walls_legend", 320.0), ("floor_legend", 76.65)]
    assert harness.copied_sources({}) == []


def test_a_copied_family_is_listed_and_kept_out_of_the_project_mae(harness):
    from extractor.row_scorecard import score_rows
    parsed = {"_ceiling_anchor": {"total_area_m2": 40.0, "label": "Iš viso"}, "pozicijos": _OURS}
    out = harness.score_billed_lines(parsed, score_rows(_HIS, _OURS), _HIS)
    by = {f["family"]: f for f in out["billed_families"]}
    assert by["GKP lubos"]["status"] == "copied"        # his 40 = ours 40 = the table's 40
    assert by["GKP lubos"]["copied_from"] == {"source": "drawing: Iš viso", "value": 40.0}
    measured = [abs(f["pct_error"]) for f in out["billed_families"]
                if f["status"] in harness.BILLED_POOLED_STATUSES]
    assert out["billed_scored"] == 5 == len(measured)
    assert out["billed_mae_pct"] == round(sum(measured) / 5, 3)
    # Our Lubų rows are that same table figure, inside his combined paint row.
    assert out["ceilings_copied"] is True


def test_walls_billed_at_the_legend_show_the_engines_own_walls_beside_them(harness):
    his = [{"nr": "1", "name": "Sienų glaistymas/ dažymas", "unit": "m2", "quantity": 240.0}]
    ours = [{"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų glaistymas/dažymas",
             "vnt": "m2", "kiekis": 220.0},
            {"skyrius": "Lubų glaistymas dažymas", "aprasymas": "Lubų glaistymas/dažymas",
             "vnt": "m2", "kiekis": 100.0}]
    parsed = {"_walls_anchor": {"total_area_m2": 220.0, "label": "legenda"}, "pozicijos": ours,
              "patalpos": [{"walls_paintable_m2": 180.0}, {"walls_paintable_m2": 108.0}]}
    assert harness.anchored_walls_note(parsed, his) == {
        "legend": 220.0, "billed": 220.0, "engine": 288.0, "paint_pct_with_engine_walls": 20.0}
    assert ours[0]["kiekis"] == 220.0, "read-only: the rows are copied, never edited"
    assert harness.anchored_walls_note({**parsed, "_walls_anchor": {}}, his) is None


def test_copied_legacy_metrics_are_found_by_value(harness):
    R = harness.MetricResult
    results = [
        R("ceiling_paint_total_m2", "Lubų dažomas plotas", "m²", "headline",
          143.27, "derived", 143.27, 0.0, 0.0, "ok"),
        R("walls_paint_total_m2", "Sienų dažomas plotas", "m²", "headline",
          269.61, "derived", 320.0, 50.39, 18.69, "fail"),
    ]
    parsed = {"_ceiling_anchor": {"total_area_m2": 143.27, "label": "BENDRAS PLOTAS"},
              "_walls_anchor": {"total_area_m2": 320.0}}
    out = harness.copied_legacy_metrics(results, parsed)
    assert [c["truth_key"] for c in out] == ["ceiling_paint_total_m2"]


def test_the_headline_table_marks_copied_and_not_produced(harness, capsys):
    s = {"slug": "objektas_a", "status": "ok", "billed_mae_pct": 55.0, "billed_scored": 2,
         "billed_families": [
             {"family": _PAINT, "status": "measured", "pct_error": 10.0, "his": 100.0,
              "ours": 110.0, "concepts": ["dazymas"]},
             {"family": "Dažymo kampai", "status": "not_produced", "pct_error": -100.0,
              "his": 50.0, "ours": None, "concepts": ["dazymo_kampai"]},
             {"family": "GKP lubos", "status": "copied", "pct_error": 0.0, "his": 40.0,
              "ours": 40.0, "concepts": ["gkp_lubos"],
              "copied_from": {"source": "drawing: Iš viso", "value": 40.0}}],
         "walls_anchor_note": {"legend": 220.0, "billed": 220.0, "engine": 288.0,
                               "paint_pct_with_engine_walls": 20.0},
         "ceilings_copied": True, "copied": []}
    harness._print_billed_headline([s], 55.0, 2, recomputed=True)
    out = capsys.readouterr().out
    assert "HEADLINE — his billed lines (live engine)" in out
    assert "+10.00%" in out and "-100.00%" in out and "copied" in out and "55.00%" in out
    assert "counted as −100 %" in out and "288.00 m²" in out and "+20.00%" in out
    assert "room-table total (a copy) on: objektas_a" in out
    harness._print_copied_block([s])
    assert "billed · GKP lubos" in capsys.readouterr().out


# ── testing-eval-12: an empty holdout says so ─────────────────────────────────

def test_an_empty_holdout_says_so_loudly(harness, capsys):
    from extractor.row_scorecard import score_rows
    sc = score_rows(_HIS, _OURS)
    hold = harness.ROW_SCORECARD_HOLDOUT
    harness._print_rows_block([("objektas_a", sc)], [(hold, None, "no extract")], recomputed=True)
    out = capsys.readouterr().out
    assert "HOLDOUT IS EMPTY" in out and "nothing held out" in out and "(no extract)" in out
    assert f"{hold} held out" not in out
    harness._print_rows_block([("objektas_a", sc)], [(hold, sc, "HOLDOUT — never in the mean")],
                              recomputed=True)
    out = capsys.readouterr().out
    assert "HOLDOUT IS EMPTY" not in out and f"{hold} held out" in out


def test_the_rows_mean_also_prints_the_pre_relabel_figure(harness, capsys):
    from extractor.row_scorecard import score_rows
    sc = score_rows(_HIS, _OURS)
    harness._print_rows_block([("objektas_a", sc), ("objektas_g", sc)], [], recomputed=True,
                              formerly_blind=frozenset({"objektas_g"}))
    out = capsys.readouterr().out
    assert "n=2 projects" in out and "pre-2026-10-05 mean, without objektas_g" in out


# ── The blind batch ───────────────────────────────────────────────────────────

def test_the_normal_eval_skips_a_blind_project_without_reading_it(harness, tmp_path,
                                                                  monkeypatch, capsys):
    monkeypatch.setattr(harness, "EVAL_RUNS_ROOT", tmp_path / "runs")
    reg = tmp_path / "registry.yaml"
    # No truth_path and no files anywhere: reading anything of it would raise.
    _write_registry(reg, [{"slug": "objektas_zz", "name": "Z", "blind": True}])
    collected: dict = {}
    harness.run_totals_only_multi(reg, recompute=True, collect=collected)
    [p] = collected["projects"]
    assert p["status"] == "excluded_blind" and p["metrics"] == []
    assert harness.gate_numbers_totals(collected["projects"]) == {}
    out = capsys.readouterr().out
    assert "1 BLIND project(s)" in out and "NO BLIND PROJECT" not in out
    assert "objektas_zz" in out and "scored only by --blind-once" in out


def test_rows_mode_skips_a_blind_project(harness, tmp_path, capsys):
    reg = tmp_path / "registry.yaml"
    _write_registry(reg, [{"slug": "objektas_zz", "name": "Z", "blind": True}])
    collected: dict = {}
    assert harness.run_rows_scorecard(reg, recompute=True, collect=collected) == 0
    assert collected["scorecards"] == []
    out = capsys.readouterr().out
    assert "1 BLIND project(s)" in out and "scored only by --blind-once" in out


def test_the_registry_merge_records_a_blind_slug_without_a_truth_path(harness, tmp_path,
                                                                     monkeypatch):
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(
        {"projects": [{"slug": "objektas_zz", "blind": True}]}), encoding="utf-8")
    monkeypatch.setattr(harness, "GROUND_TRUTH_ROOT", tmp_path)
    monkeypatch.setattr(harness, "BLIND_SLUGS", set())
    harness._merge_registry_yaml()
    assert harness.BLIND_SLUGS == {"objektas_zz"} and "objektas_zz" not in harness.REGISTRY


def test_single_project_modes_refuse_a_blind_slug(harness, tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "BLIND_SLUGS", {"objektas_zz"})
    run = tmp_path / "run"
    run.mkdir()
    (run / "parsed.json").write_text("{}", encoding="utf-8")
    for argv in (["--project", "objektas_zz", "--use-gt-inputs"],
                 ["--debug-project", "objektas_zz"],
                 ["--rescore", str(run), "--project", "objektas_zz"]):
        monkeypatch.setattr(sys, "argv", ["eval_harness.py", *argv])
        with pytest.raises(SystemExit, match="BLIND"):
            harness.main()


def test_blind_once_refuses_a_non_default_pipeline(harness, monkeypatch):
    # main() sets these module globals; monkeypatch puts them back afterwards.
    monkeypatch.setattr(harness, "GEOMETRY_LANE", False)
    monkeypatch.setattr(harness, "REPLAY_GEOMETRY", False, raising=False)
    monkeypatch.setattr(sys, "argv", ["eval_harness.py", "--blind-once", "--geometry"])
    with pytest.raises(SystemExit, match="default pipeline"):
        harness.main()


def _blind_project(root: Path, slug: str) -> None:
    folder = root / slug
    folder.mkdir(parents=True)
    room = {"nr": "1", "pavadinimas": "Kambarys", "plotas_m2": 12.0, "perimetras_m": 14.0,
            "lubu_aukstis_m": 2.7, "paskirtis": "kambarys", "lubu_tipas": "gkp",
            "elementai": []}
    (folder / "ai_extract.json").write_text(json.dumps({"patalpos": [room]}), encoding="utf-8")
    items = [{"nr": "1", "name": "Sienų, lubų glaistymas/dažymas", "unit": "m2", "quantity": 52.0},
             {"nr": "2", "name": "Dažymo kampų montavimas", "unit": "m", "quantity": 20.0},
             {"nr": "3", "name": "Eilutė, kurios niekas neturi matyti", "unit": "vnt", "quantity": 1}]
    (folder / "contractor_samata_parsed.json").write_text(
        json.dumps({"line_items": items}, ensure_ascii=False), encoding="utf-8")


def test_blind_once_prints_one_line_logs_one_line_and_scores_a_commit_once(harness, tmp_path,
                                                                           capsys):
    reg = tmp_path / "registry.yaml"
    _write_registry(reg, [{"slug": "objektas_zz", "name": "Z", "blind": True}])
    root, log, sha = tmp_path / "blind", tmp_path / "blind_log.jsonl", "a" * 40
    _blind_project(root, "objektas_zz")

    assert harness.run_blind_once(reg, blind_dir=root, log_path=log,
                                  git_state=(sha, False, "code-1")) == 0
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == 1, "one line: the batch, nothing per project"
    assert "objektas_zz" not in out and "niekas" not in out and "Kambarys" not in out
    [line] = log.read_text(encoding="utf-8").splitlines()
    entry = json.loads(line)
    assert (entry["commit"], entry["code"], entry["n_projects"],
            entry["n_billed_observations"]) == (sha, "code-1", 1, 2)
    project = entry["projects"]["objektas_zz"]
    assert set(project) == {"billed_mae_pct", "n_billed_observations", "rows_within_10_share",
                            "rows_scored", "pdf_lanes", "read_sha256"}
    assert project["pdf_lanes"] is False and project["rows_scored"] == 3
    assert len(project["read_sha256"]) == 12
    assert entry["billed_lines_mae_pct"] == project["billed_mae_pct"]

    # Once per release candidate: the same commit is refused and nothing is added…
    assert harness.run_blind_once(reg, blind_dir=root, log_path=log,
                                  git_state=(sha, False, "code-1")) == 2
    assert "already scored" in capsys.readouterr().out
    # …and so is the commit that only adds the log line: same code, new sha.
    assert harness.run_blind_once(reg, blind_dir=root, log_path=log,
                                  git_state=("b" * 40, False, "code-1")) == 2
    assert "already scored" in capsys.readouterr().out
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1
    # New code is a new release candidate.
    assert harness.run_blind_once(reg, blind_dir=root, log_path=log,
                                  git_state=("c" * 40, False, "code-2")) == 0
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_the_code_fingerprint_ignores_only_the_blind_log(harness, monkeypatch):
    import subprocess
    log_rel = harness.BLIND_LOG_PATH.relative_to(harness.REPO_ROOT).as_posix()
    tree = ["100644 blob 1111\teval_harness.py", "100644 blob 2222\tbackend/main.py"]
    answers = {}

    def fake(cmd, **_kw):
        return answers[cmd[1]]
    monkeypatch.setattr(subprocess, "check_output", fake)
    answers.update({"rev-parse": "a" * 40 + "\n", "status": "", "ls-tree": "\n".join(tree)})
    sha, dirty, code = harness._git_state()
    assert (sha, dirty, len(code)) == ("a" * 40, False, 16)
    answers["ls-tree"] = "\n".join(tree + [f"100644 blob 3333\t{log_rel}"])
    assert harness._git_state()[2] == code, "adding the log line is the same code"
    answers["ls-tree"] = "\n".join(["100644 blob 9999\teval_harness.py", tree[1]])
    assert harness._git_state()[2] != code
    answers["status"] = " M eval_harness.py"
    assert harness._git_state()[1] is True


def test_blind_once_refuses_without_scoring_or_logging(harness, tmp_path, capsys):
    reg, log, sha = tmp_path / "registry.yaml", tmp_path / "blind_log.jsonl", "c" * 40
    _blind_project(tmp_path / "blind", "objektas_zz")
    clean = (sha, False, "code-1")
    cases = [
        ([{"slug": "objektas_a", "truth_path": "x"}], tmp_path / "blind", clean,
         "No blind project"),
        ([{"slug": "objektas_zz", "blind": True}], tmp_path / "blind", (sha, True, "code-1"),
         "commit first"),
        ([{"slug": "objektas_zz", "blind": True}], tmp_path / "blind", (None, True, None),
         "commit first"),
        ([{"slug": "objektas_zz", "blind": True}], tmp_path / "nowhere", clean,
         "scored whole or not at all"),
        ([{"slug": "kitas_pavadinimas", "blind": True}], tmp_path / "blind", clean,
         "must be a codename"),
    ]
    for entries, root, state, said in cases:
        _write_registry(reg, entries)
        assert harness.run_blind_once(reg, blind_dir=root, log_path=log, git_state=state) == 2
        assert said in capsys.readouterr().out
    assert not log.exists()
    # An unreadable log cannot prove a commit was not scored: refuse.
    log.write_text("not json\n", encoding="utf-8")
    _write_registry(reg, [{"slug": "objektas_zz", "blind": True}])
    assert harness.run_blind_once(reg, blind_dir=tmp_path / "blind", log_path=log,
                                  git_state=clean) == 2
    assert "not JSON" in capsys.readouterr().out
    assert log.read_text(encoding="utf-8") == "not json\n"
