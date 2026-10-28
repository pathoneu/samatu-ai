"""Task 1 (2026-10-28): Measure how many rooms per stored project would trigger
the zoom pass under the current zoom_wanted rule (v4 3c-2, 2026-10-25).

Background
----------
The stored ai_extract.json files for h, d, a, b each carry
_meta.zoom_attempted = 9, 2, 0, 0. These were written before the 2026-10-25 rule
that makes zoom_wanted return False for any room whose plotas_saltinis is in
READ_SOURCES["plotas_saltinis"] or that has a vector outline (_konturas). The
stored rooms already carry the lanes' outlines and sources set at the END of a
full read, so applying zoom_wanted to them now shows the count the rule gives
at the end of a fresh read.

Expected results (verified by reading room records above):
  objektas_a: 0  (all eksplikacija  -> READ_SOURCES hit)
  objektas_b: 0  (all eksplikacija  -> READ_SOURCES hit)
  objektas_c: 6  (wall_dim_calc / default_fallback, no _konturas -> zoom fires)
  objektas_d: 0  (all eksplikacija  -> READ_SOURCES hit; stored was 2, predate rule)
  objektas_g: 1  (room 07: wall_dim_calc, no _konturas; rooms 01-06/08-09:
                  plano_uzrasas READ_SOURCES hit or _konturas; stored was 9, predate rule)
  objektas_h: 0  (all eksplikacija  -> READ_SOURCES hit; stored was 9, predate rule)

Conclusion: on every project whose room list came from an eksplikacija table
(a, b, d, h) zoom_wanted is 0 on the stored rooms. The 2026-10-25 rule already
handles this. No additional SAMATU_ZOOM_SKIP_TABLE flag is needed.

Note on _meta.kambariu_tapatybe: all stored files lack this key (the code that
writes it post-dates the stored reads). Table-read status is inferred here from
whether ALL rooms carry plotas_saltinis in READ_SOURCES["plotas_saltinis"].

Run with -s to see the per-project count table.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

PROJECTS = ["objektas_a", "objektas_b", "objektas_c", "objektas_d",
            "objektas_g", "objektas_h"]


def _load(slug: str) -> dict | None:
    p = ROOT / "ground_truth" / slug / "ai_extract.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _zoom_wanted(room: dict) -> bool:
    """Mirrors extractor.vision_call.zoom_wanted (v4 3c-2)."""
    from extractor.vision_call import READ_SOURCES
    if (room.get("plotas_saltinis") or "") in READ_SOURCES["plotas_saltinis"]:
        return False
    if (str(room.get("polygon_source") or "") == "vektoriniai_konturai"
            or room.get("_konturas")):
        return False
    return True


def _is_table_project(rooms: list) -> bool:
    """Infer whether room list came from an eksplikacija table.

    True when every room has plotas_saltinis in READ_SOURCES["plotas_saltinis"]
    (the deterministic primitives that a table read sets). Used because all
    stored ai_extract.json files predate the _meta.kambariu_tapatybe key.
    """
    from extractor.vision_call import READ_SOURCES
    if not rooms:
        return False
    return all((r.get("plotas_saltinis") or "") in READ_SOURCES["plotas_saltinis"]
               for r in rooms)


# ---------------------------------------------------------------------------
# §2 Table: zoom_wanted count per project on stored room records
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", PROJECTS)
def test_zoom_wanted_count_on_stored_rooms(slug, capsys):
    d = _load(slug)
    if d is None:
        pytest.skip(f"ground_truth/{slug}/ai_extract.json not on this machine")

    rooms = d.get("patalpos") or []
    meta = d.get("_meta") or {}

    wanted_rooms = [r for r in rooms if _zoom_wanted(r)]
    wanted_count = len(wanted_rooms)

    stored_attempted = meta.get("zoom_attempted", "N/A")
    kt = meta.get("kambariu_tapatybe") or {}
    kt_saltinis = kt.get("saltinis", "<absent>")
    is_table = _is_table_project(rooms)

    with capsys.disabled():
        print(
            f"\n{slug:20s}  rooms={len(rooms):2d}  "
            f"zoom_wanted={wanted_count:2d}  "
            f"stored_zoom_attempted={stored_attempted!s:5}  "
            f"is_table_inferred={str(is_table):5}  "
            f"kt.saltinis={kt_saltinis}"
        )

    if wanted_rooms:
        for r in wanted_rooms:
            with capsys.disabled():
                print(f"  nr={r.get('nr')}  plotas_saltinis={r.get('plotas_saltinis')!r}"
                      f"  polygon_source={r.get('polygon_source')!r}"
                      f"  _konturas={bool(r.get('_konturas'))}")

    # Table-read projects: rule must already give zoom_wanted=0
    if is_table:
        assert wanted_count == 0, (
            f"{slug}: table project but zoom_wanted={wanted_count} rooms are "
            f"non-zero — flag SAMATU_ZOOM_SKIP_TABLE would be needed"
        )


def test_no_flag_needed_zoom_skip_table():
    """All table-read projects already have zoom_wanted=0 on stored rooms.

    The 2026-10-25 rule (plotas_saltinis in READ_SOURCES -> zoom_wanted False)
    already skips the zoom on every project whose room list came from an
    eksplikacija table (a, b, d, h).  The stored zoom_attempted figures of 9
    (h) and 2 (d) predate that rule.  No SAMATU_ZOOM_SKIP_TABLE flag is needed.
    """
    from extractor.vision_call import READ_SOURCES

    table_slugs_present = []
    for slug in PROJECTS:
        d = _load(slug)
        if d is None:
            continue
        rooms = d.get("patalpos") or []
        if _is_table_project(rooms):
            table_slugs_present.append(slug)
            wanted = sum(1 for r in rooms if _zoom_wanted(r))
            assert wanted == 0, (
                f"{slug}: expected zoom_wanted=0 on table project, got {wanted}"
            )

    assert table_slugs_present, "No table projects found on this machine"


def test_stored_zoom_counts_predate_rule():
    """Document: stored zoom_attempted for h (9) and d (2) come from before the
    2026-10-25 rule; on the stored rooms zoom_wanted now returns 0 for both.
    """
    for slug, expected_stored in [("objektas_h", 9), ("objektas_d", 2)]:
        d = _load(slug)
        if d is None:
            pytest.skip(f"ground_truth/{slug}/ai_extract.json not present")
        meta = d.get("_meta") or {}
        rooms = d.get("patalpos") or []
        stored = meta.get("zoom_attempted")
        if stored is not None:
            assert stored == expected_stored, (
                f"{slug}: expected stored zoom_attempted={expected_stored}, got {stored}"
            )
        wanted = sum(1 for r in rooms if _zoom_wanted(r))
        assert wanted == 0, (
            f"{slug}: zoom_wanted={wanted} on stored rooms; "
            f"expected 0 (rule already handles eksplikacija rooms)"
        )
