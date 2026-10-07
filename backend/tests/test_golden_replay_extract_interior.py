"""Golden replay: production's `extract_interior` on objektas_h, every model call
answered from what the paid run of 2026-09-05 stored (audit 2026-09-29,
testing-eval-3).

The eval's `--recompute` re-runs a copy of production's tail on a frozen
extract; nothing ran production's happy path itself, so a reader dying quietly
or the copy drifting from the original went unseen. Here the real function
runs on the fixture PDF with production's defaults (native PDF Pass-1, three
voting rounds, every reader) and the harness's rules; the Anthropic client is
`tests/golden_replay.StubAnthropic`, which answers each reader from the stored
run and says which answers are stored verbatim (adjacency, niches, zoom),
rebuilt from the stored extract (Pass-1 rounds, doors, door types, fixtures)
or synthetic (`golden_replay.OBJEKTAS_H_SYNTHETIC`). No call leaves the
machine: the real client class and every socket refuse while the stub is in.

(a) Nothing fails quietly — no "failed" / "MISSING" / Traceback line on stdout,
    no error progress event, no warning logged, no room whose calculation
    failed, no build-failure row. Two steps report „skipped", as on the stored
    run: the positioned-marker lane (the drawing prints no altitudes) and the
    apdailos reader (it has no finish sheet).
(b) Every reader ran on its stub — 3 Pass-1 rounds, 1 adjacency, 9 zoom,
    1 doors, 3 door-type, 3 fixtures, 2 niche calls; none unexpected, none
    left over — its answer reached the extract, and the billed calls the run
    records (`_meta.extra_calls`, `voting_models`) are the stored run's, call
    for call.
(c) The totals are the eval's:
    · `--recompute --replay-geometry` on the frozen extract gives every metric
      the eval scores, every santrauka total, every row and every room exactly
      as production — all but two notes no quantity reads, which the frozen
      extract is older than and the eval never writes (`ROOM_KEYS_NOT_REPLAYED`,
      `VOTE_KEYS_NOT_REPLAYED`). That includes the shower attribution
      (`vision_call.mark_shower_rooms`, 2026-10-03): production runs it at the
      fixture-reader step and the frozen extract is older, so the eval's tail
      runs it on the stored plumbing list (2026-10-05). Before that, room 07
      (the plumbing plan lists a bathtub there, no shower) kept the shower zone
      — „Hidroizoliacinė medžiaga" 97,44 kg in the eval against production's
      70,38; the test without the step holds that difference exactly.
    · plain `--recompute` does not run the drawing lanes (audit round 13):
      exactly the metrics in `LANES_MOVE` differ — on 2026-10-05 e.g. combined
      paint 473,18 → 441,26 m², angokraščiai 47,40 → 76,91 m — and the rest
      (walls and ceilings are anchored to the designer's legend and table) agree.
    · run on production's own output, the eval (plain or with the replay)
      changes nothing: its tail reproduces production's numbers.

Skips when the fixture PDF or the stored answers are not on this machine; the
PDF path can be pointed elsewhere with SAMATU_GOLDEN_REPLAY_PDF.
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import logging
import os
import re
import sys
from pathlib import Path

import pytest

from tests import golden_replay as gr

pytestmark = pytest.mark.integration          # the real drawing; ~30 s

REPO_ROOT = Path(__file__).resolve().parents[2]
SLUG = "objektas_h"
DEFAULT_PDF = REPO_ROOT / "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_h/project.pdf"

EXPECTED_CALLS = {"pass1": 3, "adjacency": 1, "zoom": 9, "doors": 1, "door_type": 3, "fixtures": 3, "niche": 2}
EXPECTED_SKIPPED = {"positioned_marker_lane_skipped", "apdailos_skipped"}
# The metrics plain --recompute gets wrong on objektas_h because it does not run the
# drawing lanes (perimeters added from the strings, outlines, openings as drawn, floor
# coverings). When a lane starts or stops moving one, update this set — and say why.
# 2026-10-06: `led_nisos_m` left it — the lanes moved the LED metres only through the
# room-type estimate (perimeter × a ratio), which is no longer billed until he accepts it
# (niche_inference.LED_ESTIMATE_OPT_IN); the read niche metres do not depend on a lane.
LANES_MOVE = {
    "dazymo_walls_plus_ceilings_combined_m2", "plyteles_grindys_total_m2",
    "plyteles_sienos_total_m2", "kampu_metrai_m", "rotband_lyginimas_m2",
    "plyteles_sienos_grindys_combined_m2", "pvc_grindys_m2", "grindjuostes_total_m",
    "plyteliu_grindjuostes_m", "pasleptu_duru_staktos_m", "angokrasciu_m",
}
# Written by production's per-room height step (Step 2.45) for the check sheet; read by
# nothing, and not a step the eval runs.
ROOM_KEYS_NOT_REPLAYED = {"_lubu_aukstis_sklaida"}
# The voter's per-element record (`_vote.elementai`, 2026-09-30) is newer than the frozen
# extract; the eval never votes again. Provenance only — the voted values are compared.
VOTE_KEYS_NOT_REPLAYED = {"elementai"}
_FAILURE_LINE = re.compile(r"\bfailed\b|MISSING|Traceback|\bException\b", re.IGNORECASE)


def _pdf_path() -> Path:
    return Path(os.environ.get("SAMATU_GOLDEN_REPLAY_PDF") or DEFAULT_PDF)


def _harness():
    spec = importlib.util.spec_from_file_location("eval_harness_golden_replay", REPO_ROOT / "eval_harness.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_golden_replay"] = mod
    spec.loader.exec_module(mod)
    return mod


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """One stubbed production run, shared by the tests below."""
    pdf = _pdf_path()
    if not pdf.is_file():
        pytest.skip(f"{SLUG}: the drawing is not on this machine ({pdf})")
    missing = gr.objektas_h_material_missing()
    if missing:
        pytest.skip(f"{SLUG}: the stored answers are not on this machine — {missing}")
    frozen = json.loads(gr.OBJEKTAS_H_EXTRACT.read_text(encoding="utf-8"))
    meta_log = json.loads(gr.OBJEKTAS_H_META.read_text(encoding="utf-8"))
    eh = _harness()

    from extractor import feature_flags, pdf_page_cache, vision_call as vc

    client = gr.StubAnthropic(gr.objektas_h_answers(frozen, meta_log))
    events: list[dict] = []
    out = io.StringIO()
    logs = _Records()
    with pytest.MonkeyPatch.context() as mp:
        # production's defaults, not the suite's (conftest pins the raster Pass-1)
        for env in (*feature_flags._FLAG_ENV_NAMES.values(), "SAMATU_PDF_NATIVE", "SAMATU_ZOOM_AGENTIC",
                    "SAMATU_VOTING_MODELS", "MODEL_OVERRIDE", "VOTING_N", "PARALLEL_VOTING_WARM",
                    "WALL_ELEVATION_EXTRACT", "ENABLE_LEGACY_HALF_SUBTRACT"):
            mp.delenv(env, raising=False)
        gr.install(mp, client, tmp_path_factory.mktemp("vision_cache"))
        pdf_page_cache.clear()
        logging.getLogger().addHandler(logs)
        try:
            with contextlib.redirect_stdout(out):
                result = vc.extract_interior(pdf.read_bytes(), rules_override=eh._harness_rules_override(frozen),
                                             progress_cb=events.append)
        finally:
            logging.getLogger().removeHandler(logs)
            pdf_page_cache.clear()
    return {"result": result, "client": client, "events": events, "stdout": out.getvalue(),
            "logs": logs.records, "frozen": frozen, "meta_log": meta_log, "eh": eh, "pdf": pdf}


def _eval_tail(run, parsed: dict, *, replay: bool) -> dict:
    """What the eval's --recompute [--replay-geometry] makes of `parsed`."""
    eh = run["eh"]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(eh, "REPLAY_GEOMETRY", replay)
        mp.setitem(eh.REGISTRY[SLUG], "pdf_path", str(run["pdf"]))
        with contextlib.redirect_stdout(io.StringIO()):
            return eh._rerun_deterministic_tail(copy.deepcopy(parsed), SLUG)


def _metrics(run, parsed: dict) -> dict:
    return {key: m["accessor"](parsed) for key, m in run["eh"].METRICS.items()}


def _rows(parsed: dict) -> list[tuple]:
    return [(r.get("skyrius"), r.get("aprasymas"), r.get("vnt"), r.get("kiekis")) for r in parsed.get("pozicijos") or []]


def _room_diffs(a: dict, b: dict) -> dict[str, list[str]]:
    """Room by room, the keys whose values differ (all keys but the two not replayed)."""
    def comparable(room: dict) -> dict:
        out = {k: v for k, v in room.items() if k not in ROOM_KEYS_NOT_REPLAYED}
        if isinstance(out.get("_vote"), dict):
            out["_vote"] = {k: v for k, v in out["_vote"].items() if k not in VOTE_KEYS_NOT_REPLAYED}
        return out

    assert [r.get("nr") for r in a["patalpos"]] == [r.get("nr") for r in b["patalpos"]]
    out = {}
    for ra, rb in zip(a["patalpos"], b["patalpos"]):
        ca, cb = comparable(ra), comparable(rb)
        keys = sorted(k for k in set(ca) | set(cb) if ca.get(k) != cb.get(k))
        if keys:
            out[str(ra.get("nr"))] = keys
    return out


# ── (a) ──────────────────────────────────────────────────────────────────────
def test_no_reader_fails_quietly(run):
    result = run["result"]
    assert result.get("status") == "ok", result.get("_error")
    failures = [line for line in run["stdout"].splitlines() if _FAILURE_LINE.search(line)]
    assert not failures, failures
    events = [e.get("event") for e in run["events"]]
    assert not [e for e in events if "error" in str(e) or "failed" in str(e)], events
    assert {e for e in events if str(e).endswith("_skipped")} == EXPECTED_SKIPPED, events
    assert not [f"{r.name}: {r.getMessage()}" for r in run["logs"]]
    assert not [r["nr"] for r in result["patalpos"] if r.get("_calc_failed")]
    codes = {w.get("code") or w.get("source") for w in result.get("warnings") or [] if isinstance(w, dict)}
    assert not codes & {"room_calc_failed", "pozicijos_build_failure", "doors_page_unread", "doors_unattributed",
                        "adjacency_unread"}
    assert result["_meta"]["adjacency"]["status"] == "applied"
    assert result["pozicijos"]


# ── (b) ──────────────────────────────────────────────────────────────────────
def test_every_reader_ran_on_its_stored_answer(run):
    client, result, frozen = run["client"], run["result"], run["frozen"]
    assert dict(client.calls) == EXPECTED_CALLS
    assert client.unexpected == [] and client.leftover() == {}
    assert {kw.get("max_retries") for kw in client.constructed} == {1}
    meta = result["_meta"]
    stored = frozen["_meta"]

    def billed(calls):
        return [(c.get("reader"), c.get("input_tokens"), c.get("output_tokens"),
                 c.get("cache_read_tokens"), c.get("cache_write_tokens")) for c in calls]

    assert billed(meta["extra_calls"]) == billed(stored["extra_calls"])
    assert [(r["input_tokens"], r["output_tokens"]) for r in meta["voting_models"]] == \
        [(r["input_tokens"], r["output_tokens"]) for r in stored["voting_models"]]
    # each reader's answer reached the extract
    assert result["_voting"]["n_runs"] == 3
    assert result["_voting"]["low_confidence_fields"] == frozen["_voting"]["low_confidence_fields"]
    assert [r.get("_vote", {}).get(f) for r in result["patalpos"] for f in ("perimetras_m", "plotas_m2")] == \
        [r.get("_vote", {}).get(f) for r in frozen["patalpos"] for f in ("perimetras_m", "plotas_m2")]
    assert [r.get("n_partition_walls") for r in result["patalpos"]] == [r.get("n_partition_walls") for r in frozen["patalpos"]]
    assert [r.get("_adjacency") for r in result["patalpos"]] == [r.get("_adjacency") for r in frozen["patalpos"]]
    assert meta["zoom_attempted"] == stored["zoom_attempted"] == 9
    assert [r.get("_zoom") for r in result["patalpos"]] == [r.get("_zoom") for r in frozen["patalpos"]]
    assert (meta["doors_total_count"], meta["doors_exterior_count"]) == (stored["doors_total_count"], stored["doors_exterior_count"])
    assert result["_door_types"]["count"] == frozen["_door_types"]["count"]
    assert result["_door_types"]["_vote"] == frozen["_door_types"]["_vote"]
    assert meta["fixtures_status"] == "ok" and meta["fixtures_raised"] == stored["fixtures_raised"]
    assert result["_sanitary_prietaisai"] == frozen["_sanitary_prietaisai"]
    assert result["detected_symbols_summary"] == frozen["detected_symbols_summary"]
    assert (meta["niche_locator_pages"], meta["niche_locator_count"]) == (stored["niche_locator_pages"], stored["niche_locator_count"])
    assert meta["niche_inference_rooms"] == stored["niche_inference_rooms"]


# ── (c) ──────────────────────────────────────────────────────────────────────
def test_totals_equal_the_eval_replay(run):
    prod, frozen = run["result"], run["frozen"]
    assert not [r["nr"] for r in frozen["patalpos"] if "_dusas" in r], "the frozen extract predates the attribution"
    replayed = _eval_tail(run, frozen, replay=True)
    assert _metrics(run, replayed) == _metrics(run, prod)
    assert replayed["santrauka"] == prod["santrauka"]
    assert _rows(replayed) == _rows(prod)
    assert _room_diffs(replayed, prod) == {}
    # the shower attribution is the eval's step too: room 07 (the plumbing plan lists
    # a bathtub there, no shower) loses the shower zone, as in production
    by_nr = {r["nr"]: r for r in replayed["patalpos"]}
    assert (by_nr["04"]["_dusas"], by_nr["07"]["_dusas"], by_nr["08"]["_dusas"]) == (False, False, True)


def test_without_the_shower_attribution_the_eval_scored_the_type_default(run, monkeypatch):
    """What closed the gap (2026-10-05): before the eval's tail ran
    `mark_shower_rooms`, every wet room kept its type's shower zone — room 07's
    waterproofing larger and „Hidroizoliacinė medžiaga" 97,44 kg against
    production's 70,38. The only difference was that one step."""
    from extractor import vision_call as vc

    prod = run["result"]
    monkeypatch.setattr(vc, "mark_shower_rooms", lambda parsed: 0)
    unmarked = _eval_tail(run, run["frozen"], replay=True)
    assert _metrics(run, unmarked) == _metrics(run, prod)
    assert _room_diffs(unmarked, prod) == {"04": ["_dusas"], "07": ["_dusas", "hidroizoliacija_m2"], "08": ["_dusas"]}
    assert [r for r in _rows(unmarked) if r not in _rows(prod)] == \
        [r for r in _rows(unmarked) if r[1] == "Hidroizoliacinė medžiaga (2 sluoksniai)"]
    eval_07 = next(r for r in unmarked["patalpos"] if r["nr"] == "07")
    assert next(r for r in prod["patalpos"] if r["nr"] == "07")["hidroizoliacija_m2"] < eval_07["hidroizoliacija_m2"]


def test_plain_recompute_misses_exactly_the_drawing_lanes(run):
    prod = run["result"]
    plain = _metrics(run, _eval_tail(run, run["frozen"], replay=False))
    ours = _metrics(run, prod)
    assert {k for k in ours if plain[k] != ours[k]} == LANES_MOVE


def test_the_eval_reproduces_production_on_its_own_output(run):
    prod = run["result"]
    for replay in (False, True):
        again = _eval_tail(run, prod, replay=replay)
        assert _metrics(run, again) == _metrics(run, prod), replay
        assert again["santrauka"] == prod["santrauka"], replay
        assert _rows(again) == _rows(prod), replay
        assert _room_diffs(again, prod) == {}, replay


# ── (d) the model's own warnings, in his numbers (2026-10-06) ───────────────
def test_the_models_warnings_reach_the_list_in_his_numbers(run):
    """Step 3.9 runs on production's path: the warnings the model wrote (the
    stored ones, answered back by the stub) come out with decimal commas and
    without the prompt's English words („naudotas fallback 2.82 m" → „naudotas
    numatytasis 2,82 m", 2026-10-07), and the list the screen reads shows them
    so (extractor/model_warnings.py)."""
    from extractor.model_warnings import plain_numbers, plain_words, room_identifiers

    result = run["result"]
    rooms = result["patalpos"]
    said = [w["message"] for w in gr._vision_warnings(run["frozen"])]
    want = [plain_numbers(plain_words(m, rooms), room_identifiers(rooms), rooms) for m in said]
    assert any("numatytasis 2,82 m" in m for m in want), want
    assert want != said, "no stored warning carries a number to rewrite — nothing is tested"
    stored = [w.get("message") for w in result.get("warnings") or [] if isinstance(w, dict)]
    shown = [w.get("message") for w in (result.get("lt_sanity") or {}).get("warnings") or []]
    for before, after in zip(said, want):
        assert after in stored and after in shown, after
        if before != after:
            assert before not in stored and before not in shown, before
