"""rules.fit — fit the `lt_rangovas` profile against the contractor's own sąmatos (R5).

    venv/bin/python backend/rules/fit.py [--mode replay|plain] [--out <dir>] [--rounds 2] [--no-scope]

For every profile parameter (`rules/conventions.py` LT_RANGOVAS, plus the two scope
defaults the fit can reach — the Rotband share and the reveals scope) this searches the
value that maximises HIS rows reproduced within ±10 % (`extractor/row_scorecard.py`, the
frozen concept table — never a fuzzy match), averaged over the six usable projects
(objektas_a, b, c, d, g, h). Coordinate descent over the grid, starting from the
defaults; a tie keeps the default.

Leave-one-out: the same descent on five projects, the chosen profile scored on the
sixth. In-sample and LOO are reported side by side; only LOO says anything about a
project the profile was not chosen on.

The per-project scope (which rooms get which work family) is fitted separately, per
project, as an ORACLE: greedy room × family switches that raise that project's own
±10 % count. It cannot be validated leave-one-out — it is his choice on one job — and is
reported as „what the scope switches can reach when he sets them", not as a default.

Zero API spend: the cached extracts are replayed through the live engine exactly as
`eval_harness.py --rows --recompute [--replay-geometry]` does (the expensive €0 lanes run
once per project; each candidate profile reruns only the per-room math and the row
build). The Anthropic key is replaced by a dead one and the client constructor raises.
Quantities only (his prices are never read here); codenames only in the output.

An offline tool: it drives the whole engine (still in extractor/vision_call.py) through the eval
harness, so it imports that module at run time. No runtime code under rules/ imports it (rule R2).
Report: docs/superpowers/research/2026-10-25-conventions-fit.md.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import itertools
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GT = REPO / "ground_truth"
USABLE = ("objektas_a", "objektas_b", "objektas_c", "objektas_d", "objektas_g", "objektas_h")

REVEALS_KINDS = ("langai", "lauko_durys", "praejimai", "vidaus_durys")
REVEALS_GRID = [dict(zip(REVEALS_KINDS, bits)) for bits in itertools.product((True, False), repeat=4)]

# The searched grid. `profile.*` keys go to `_overrides.profilis`; `rotband_dalis` to the scope
# (`_overrides.apimtis`, ROTBAND_DEFAULT_SHARE = 30 % today). Founder-fixed parameters (hidro_rows,
# rounding) and the score-neutral granularity are scored for the report but never chosen by the fit.
FIT_GRID: dict[str, list] = {
    "aperture_no_deduct_max_m2": [1.0, 3.0],
    "skirting_door_deduct_m": [0.85, 0.90, "drawn"],
    "skirting_waste": [1.10, 1.00],
    "kampai": ["visi", "vertikalus_lubos", "vertikalus", "isoriniai_angos", "isoriniai", "tik_lubos"],
    "reveals_scope": REVEALS_GRID,
    "rotband_dalis": [30, 0, 10, 20, 40, 50, 100],
}
REPORT_ONLY: dict[str, list] = {
    "hidro_rows": ["two", "one"],
    "rounding": ["row_boundary", "legacy"],
    "paint_rows": ["split", "merged"],
    "tile_rows": ["split", "merged"],
}
DEFAULTS = {"aperture_no_deduct_max_m2": 1.0, "skirting_door_deduct_m": 0.85, "skirting_waste": 1.10,
            "kampai": "visi", "reveals_scope": {"langai": True, "lauko_durys": True, "praejimai": True,
                                                "vidaus_durys": False},
            "rotband_dalis": 30, "hidro_rows": "two", "rounding": "row_boundary",
            "paint_rows": "split", "tile_rows": "split"}
SCOPE_FAMILIES = ("apdaila", "grindys", "plyteles")


def block_paid_calls() -> None:
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-disabled-rules-fit"
    try:
        import anthropic

        def _refuse(*_a, **_k):
            raise RuntimeError("rules.fit: a paid Anthropic call was attempted and blocked")
        anthropic.Anthropic.__init__ = _refuse          # type: ignore[method-assign]
        anthropic.AsyncAnthropic.__init__ = _refuse     # type: ignore[method-assign]
    except Exception:  # noqa: BLE001
        pass


def harness():
    block_paid_calls()
    os.chdir(REPO)
    for p in (str(REPO / "backend"), str(REPO)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import eval_harness  # noqa: E402
    return eval_harness


def snapshot(eh, slug: str, mode: str) -> dict:
    """The project's state right before the per-room math, after every €0 lane of the tail."""
    vc = __import__("extractor.vision_call", fromlist=["x"])
    cap: dict = {}
    orig = (vc._recompute_per_room_via_python, vc._recompute_santrauka, vc._build_pozicijos_from_rooms)

    def _cap(parsed, _rules):
        cap["p"] = copy.deepcopy(parsed)
        return parsed
    vc._recompute_per_room_via_python = _cap
    vc._recompute_santrauka = lambda p: p
    vc._build_pozicijos_from_rooms = lambda p: p
    eh.REPLAY_GEOMETRY = mode == "replay"
    eh.GEOMETRY_LANE = False
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            parsed = eh.run_pipeline_replay(GT / slug / "ai_extract.json")
            eh._rerun_deterministic_tail(parsed, slug)
    finally:
        vc._recompute_per_room_via_python, vc._recompute_santrauka, vc._build_pozicijos_from_rooms = orig
    return cap["p"]


def overrides_for(config: dict, apimtis: dict | None = None) -> dict:
    prof = {k: v for k, v in config.items() if k not in ("rotband_dalis",)}
    out: dict = {"profilis": prof}
    a = dict(apimtis or {})
    if config.get("rotband_dalis") is not None and config["rotband_dalis"] != 30:
        a["rotband"] = "dalis"
        a["rotband_dalis"] = config["rotband_dalis"]
    if a:
        out["apimtis"] = a
    return out


def build(eh, snap: dict, config: dict, apimtis: dict | None = None) -> dict:
    """Run the per-room math + row build on a copy of the snapshot under one configuration."""
    vc = __import__("extractor.vision_call", fromlist=["x"])
    from extractor import scope as _scope
    p = copy.deepcopy(snap)
    ov = dict(p.get("_overrides") or {})
    ov.update(overrides_for(config, apimtis))
    p["_overrides"] = ov
    rules = eh._harness_rules_override(p)
    with contextlib.redirect_stdout(io.StringIO()):
        p = vc._recompute_per_room_via_python(p, rules)
        p = vc._recompute_santrauka(p)
        a = _scope.normalize_apimtis(ov.get("apimtis")) if "apimtis" in ov else None
        if a:
            _scope.mark_rooms(p.get("patalpos") or [], a)
            p["_apimtis"] = a
            _scope.apply_ceiling_choice(p.get("patalpos") or [], a)
        p = vc._build_pozicijos_from_rooms(p)
        if a:
            p["pozicijos"] = _scope.filter_rows_by_families(p.get("pozicijos"), a)
    return p


def _key(config: dict, apimtis: dict | None = None) -> str:
    return json.dumps([config, apimtis or {}], sort_keys=True, default=str)


class Scorer:
    def __init__(self, eh, mode: str, slugs=USABLE):
        self.eh = eh
        self.snaps = {}
        for s in slugs:
            t0 = time.time()
            self.snaps[s] = snapshot(eh, s, mode)
            print(f"  snapshot {s} ({time.time() - t0:.0f} s)", flush=True)
        self.cache: dict = {}

    def card(self, slug: str, config: dict, apimtis: dict | None = None):
        k = (slug, _key(config, apimtis))
        if k not in self.cache:
            p = build(self.eh, self.snaps[slug], config, apimtis)
            self.cache[k] = self.eh._score_rows_of(p, slug)
        return self.cache[k]

    def share(self, slug: str, config: dict, apimtis: dict | None = None) -> float:
        sc = self.card(slug, config, apimtis)
        return float(sc.within_10_share or 0.0) if sc is not None else 0.0

    def mean(self, slugs, config: dict) -> float:
        return sum(self.share(s, config) for s in slugs) / len(slugs)


def descend(scorer: Scorer, slugs, rounds: int = 2, start: dict | None = None) -> dict:
    """Coordinate descent over FIT_GRID on `slugs`; a value must beat the current one to replace it."""
    cfg = copy.deepcopy(start or DEFAULTS)
    for _ in range(rounds):
        changed = False
        for name, values in FIT_GRID.items():
            best_v, best = cfg[name], scorer.mean(slugs, cfg)
            for v in values:
                trial = {**cfg, name: v}
                m = scorer.mean(slugs, trial)
                if m > best + 1e-9:
                    best_v, best = v, m
            if best_v != cfg[name]:
                cfg[name] = best_v
                changed = True
        if not changed:
            break
    return cfg


def per_project(scorer: Scorer, config: dict) -> dict:
    out = {}
    for s in scorer.snaps:
        sc = scorer.card(s, config)
        out[s] = None if sc is None else {"share": round(sc.within_10_share or 0, 1), "within_10": sc.buckets["within_10"],
                                          "n_scored": sc.n_scored}
    return out


def concept_rows(sc, concept_prefix: str) -> list[dict]:
    if sc is None:
        return []
    return [{"his": r.quantity, "ours": r.app_quantity, "pct": r.pct_error, "bucket": r.bucket, "unit": r.unit}
            for r in sc.rows if (r.concept or "").startswith(concept_prefix)]


def scope_oracle(scorer: Scorer, slug: str, config: dict) -> dict:
    """Greedy per-project scope: room × family switches (and whole families) that raise HIS ±10 % count."""
    snap = scorer.snaps[slug]
    rooms = [str(r.get("nr")).strip() for r in snap.get("patalpos") or [] if isinstance(r, dict) and r.get("nr")]
    a: dict = {"patalpu_sritys_ne": {}, "darbai_ne": []}

    def _score(ap):
        sc = scorer.card(slug, config, ap)
        return sc.buckets["within_10"] if sc is not None else 0
    best = base = _score(None)
    improved = True
    while improved:
        improved = False
        moves = [("room", nr, f) for nr in rooms for f in SCOPE_FAMILIES
                 if f not in a["patalpu_sritys_ne"].get(nr, [])]
        moves += [("lubos", "ne_musu", None)] if a.get("lubos") != "ne_musu" else []
        moves += [("kampai", "tik_isoriniai", None)] if a.get("kampai") != "tik_isoriniai" else []
        best_move = None
        for mv in moves:
            trial = copy.deepcopy(a)
            if mv[0] == "room":
                trial["patalpu_sritys_ne"].setdefault(mv[1], []).append(mv[2])
            else:
                trial[mv[0]] = mv[1]
            s = _score(trial)
            if s > best:
                best, best_move = s, trial
        if best_move is not None:
            a = best_move
            improved = True
    sc = scorer.card(slug, config, a if best > base else None)
    return {"base_within_10": base, "oracle_within_10": best, "apimtis": a if best > base else {},
            "share": round(sc.within_10_share or 0, 1) if sc is not None else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="replay", choices=("replay", "plain"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--no-scope", action="store_true")
    args = ap.parse_args()
    out_dir = Path(args.out) if args.out else (REPO / "docs" / "superpowers" / "research")
    eh = harness()
    t0 = time.time()
    scorer = Scorer(eh, args.mode)
    slugs = list(scorer.snaps)

    legacy = {**DEFAULTS, "hidro_rows": "one", "rounding": "legacy"}     # the engine before Phase 2
    result: dict = {"mode": args.mode, "projects": slugs, "defaults": DEFAULTS}
    result["before_legacy"] = per_project(scorer, legacy)
    result["defaults_scores"] = per_project(scorer, DEFAULTS)

    # one parameter at a time around the defaults — the table every choice is read from
    sweep = {}
    for name, values in {**FIT_GRID, **REPORT_ONLY}.items():
        sweep[name] = []
        for v in values:
            cfg = {**DEFAULTS, name: v}
            sweep[name].append({"value": v, "per_project": {s: round(scorer.share(s, cfg), 1) for s in slugs},
                                "mean": round(scorer.mean(slugs, cfg), 2)})
        print(f"  swept {name} ({time.time() - t0:.0f} s)", flush=True)
    result["sweep"] = sweep

    # leave-one-out for ONE parameter at a time (the others at their defaults): the value the five other
    # projects prefer, and what it does to the held-out project against the default
    loo_param = {}
    for name in FIT_GRID:
        folds = {}
        for held in slugs:
            train = [s for s in slugs if s != held]
            best = max(sweep[name], key=lambda e: (round(sum(e["per_project"][s] for s in train) / len(train), 6),
                                                    e["value"] == DEFAULTS[name]))
            dflt = next(e for e in sweep[name] if e["value"] == DEFAULTS[name])
            folds[held] = {"chosen": best["value"], "held_out": best["per_project"][held],
                           "held_out_default": dflt["per_project"][held]}
        loo_param[name] = folds
    result["loo_per_param"] = loo_param

    # kampai: his corner row against each convention
    result["kampai"] = {kc: {s: concept_rows(scorer.card(s, {**DEFAULTS, "kampai": kc}), "dazymo_kampai")
                             for s in slugs} for kc in FIT_GRID["kampai"]}
    # waterproofing family under the two forms
    result["hidro"] = {hv: {s: concept_rows(scorer.card(s, {**DEFAULTS, "hidro_rows": hv}), "hidroizoliacija")
                            for s in slugs} for hv in ("two", "one")}
    # reveals: his row against every scope
    result["reveals"] = [{"scope": rs, "rows": {s: concept_rows(scorer.card(s, {**DEFAULTS, "reveals_scope": rs}),
                                                                "angokrasciai") for s in slugs}}
                         for rs in REVEALS_GRID]

    fitted = descend(scorer, slugs, args.rounds)
    result["fitted_in_sample"] = fitted
    result["after_in_sample"] = per_project(scorer, fitted)
    print(f"  in-sample fit done ({time.time() - t0:.0f} s): {fitted}", flush=True)

    loo = {}
    for held in slugs:
        train = [s for s in slugs if s != held]
        cfg = descend(scorer, train, args.rounds)
        sc = scorer.card(held, cfg)
        loo[held] = {"config": cfg, "held_out": None if sc is None else {
            "share": round(sc.within_10_share or 0, 1), "within_10": sc.buckets["within_10"], "n_scored": sc.n_scored}}
        print(f"  LOO {held}: {loo[held]['held_out']} ({time.time() - t0:.0f} s)", flush=True)
    result["loo"] = loo

    if not args.no_scope:
        result["scope_oracle"] = {}
        for s in slugs:
            result["scope_oracle"][s] = scope_oracle(scorer, s, fitted)
            print(f"  scope oracle {s}: {result['scope_oracle'][s]['base_within_10']} → "
                  f"{result['scope_oracle'][s]['oracle_within_10']} ({time.time() - t0:.0f} s)", flush=True)

    def _mean(d):
        vals = [v["share"] for v in d.values() if v]
        return round(sum(vals) / len(vals), 2) if vals else None
    result["summary"] = {
        "before_legacy_mean": _mean(result["before_legacy"]),
        "defaults_mean": _mean(result["defaults_scores"]),
        "in_sample_mean": _mean(result["after_in_sample"]),
        "loo_mean": _mean({k: v["held_out"] for k, v in loo.items()}),
        "scope_oracle_mean": (round(sum(v["share"] for v in result.get("scope_oracle", {}).values()
                                        if v.get("share") is not None) / len(slugs), 2)
                              if result.get("scope_oracle") else None),
        "seconds": round(time.time() - t0),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"conventions_fitted{'' if args.mode == 'replay' else '_plain'}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(result["summary"], indent=1))
    print(f"→ {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
