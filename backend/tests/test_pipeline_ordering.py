"""Pipeline ordering contract for `extract_interior` (2026-07-29).

A run has exactly ONE per-room recompute (`_recompute_per_room_via_python`),
ONE pozicijos build and ONE santrauka recompute. Any step that WRITES a
calculator input must therefore run *above* the recompute.

The bug this locks down: `_apply_wall_elevation_tile_override` used to run at
Step 4.08, i.e. AFTER the only recompute of the run. It writes
`_tile_area_from_elevation_m2`, which is the input that drives the ELEVATION
branch of `calc_room_quantities` (walls_paintable = walls_gross − openings −
tile, plus full-tile detection zeroing wall paint). A fresh extraction's
`walls_paintable_m2` / `dazymo_plotas_m2` never saw it — the numbers silently
changed the first time anything else triggered a recompute (POST
/recompute-interior, /api/recompute-quantities, eval_harness --rescore
--recompute), so the same project showed different paint areas before and
after the user touched an assumption.

Same class of bug for `_plyteliu_specs`, which is read by
`_build_pozicijos_from_rooms` but used to be written after it.

These assertions are AST-based (not string matching) and read the real
`extract_interior` source, so they fail if anyone moves the steps back.
"""

from __future__ import annotations

import ast
import inspect

from extractor import vision_call


def _extract_interior_tree() -> ast.AST:
    return ast.parse(inspect.getsource(vision_call.extract_interior))


def _call_linenos(tree: ast.AST, func_name: str) -> list[int]:
    """Line numbers (relative to the function source) of every call to
    `func_name`, whether called bare or as an attribute."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = getattr(f, "id", None) or getattr(f, "attr", None)
        if name == func_name:
            out.append(node.lineno)
    return sorted(out)


def _subscript_assign_linenos(tree: ast.AST, key: str) -> list[int]:
    """Line numbers of every `something[key] = ...` assignment."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == key):
                out.append(node.lineno)
    return sorted(out)


def test_exactly_one_recompute_in_the_run():
    """The invariant only holds because there is a single recompute. If a
    second one is ever added, this contract needs rethinking rather than
    silently passing."""
    tree = _extract_interior_tree()
    assert len(_call_linenos(tree, "_recompute_per_room_via_python")) == 1
    assert len(_call_linenos(tree, "_build_pozicijos_from_rooms")) == 1
    assert len(_call_linenos(tree, "_recompute_santrauka")) == 1


def test_tile_override_runs_before_the_recompute():
    """`_tile_area_from_elevation_m2` must be on the room before
    calc_room_quantities reads it — otherwise fresh extractions and recomputed
    ones disagree on walls_paintable_m2 / dazymo_plotas_m2."""
    tree = _extract_interior_tree()
    override = _call_linenos(tree, "_apply_wall_elevation_tile_override")
    recompute = _call_linenos(tree, "_recompute_per_room_via_python")
    assert override, "tile override call vanished from extract_interior"
    assert max(override) < min(recompute), (
        "_apply_wall_elevation_tile_override must run BEFORE "
        "_recompute_per_room_via_python; it writes a calculator input"
    )


def test_tile_override_runs_before_pozicijos_and_santrauka():
    """The override also changes plyteles_sienos_m2, which feeds the kiekių
    žiniaraštis and the santrauka totals."""
    tree = _extract_interior_tree()
    override = max(_call_linenos(tree, "_apply_wall_elevation_tile_override"))
    assert override < min(_call_linenos(tree, "_build_pozicijos_from_rooms"))
    assert override < min(_call_linenos(tree, "_recompute_santrauka"))


def test_plyteliu_specs_written_before_pozicijos_build():
    """`_build_pozicijos_from_rooms` reads parsed['_plyteliu_specs'] to label
    tile lines with their size; writing it afterwards means the first run
    never sees it."""
    tree = _extract_interior_tree()
    writes = _subscript_assign_linenos(tree, "_plyteliu_specs")
    assert writes, "_plyteliu_specs assignment vanished from extract_interior"
    assert max(writes) < min(_call_linenos(tree, "_build_pozicijos_from_rooms"))


def test_post_math_steps_are_validators_only():
    """Guard rail: nothing after the recompute may call a known data producer.

    Validators (lt_sanity, cross_page_validator, sanity_checks,
    consistency_checker, perimeter_validator) only append warnings, so they are
    legitimately allowed to stay below the math."""
    tree = _extract_interior_tree()
    recompute = min(_call_linenos(tree, "_recompute_per_room_via_python"))
    PRODUCERS = (
        "_apply_wall_elevation_tile_override",
        "extract_wall_elevations",
        "extract_plyteliu_specifikacija",
        "fold_niches_into_rooms",
        "infer_missing_niches",
    )
    late = {
        name: [ln for ln in _call_linenos(tree, name) if ln > recompute]
        for name in PRODUCERS
    }
    offenders = {k: v for k, v in late.items() if v}
    assert not offenders, (
        f"data producers must not run after the recompute: {offenders}"
    )
