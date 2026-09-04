"""Eksplikacija→room merge: match by NUMBER, never collapse duplicate names.

Objektas A has rooms 108 and 109 both named "Berniuko kambarys". The old
name-keyed dict kept ONE row for that name, so both bedrooms inherited the
same area; and a one-character drift in the table read ("san. mazgas" vs
"san.mazgas") missed the row entirely, silently switching that room to the
Vision dimension chain — a different number between two runs of the same PDF.
"""
import sys, types
# suite runs from backend/


def _merge(rooms, eks_rows):
    """Exercise the shipped merge block in isolation."""
    import re as _re, unicodedata as _ud

    def _nkey(s):
        s = _ud.normalize("NFKD", (s or "").strip().lower())
        s = "".join(c for c in s if not _ud.combining(c))
        return _re.sub(r"[^a-z0-9]+", "", s)

    eks_by_nr, eks_by_name = {}, {}
    for r in eks_rows:
        nr = str(r.get("nr") or "").strip()
        if nr and nr not in eks_by_nr:
            eks_by_nr[nr] = r
        eks_by_name.setdefault(_nkey(r.get("pavadinimas")), []).append(r)
    claimed = set()
    for room in rooms:
        nr = str(room.get("nr") or "").strip()
        row = eks_by_nr.get(nr)
        if row is None:
            cands = [r for r in eks_by_name.get(_nkey(room.get("pavadinimas")), [])
                     if id(r) not in claimed]
            row = cands[0] if len(cands) == 1 else None
        if row is not None:
            claimed.add(id(row))
            if row.get("plotas_m2"):
                room["plotas_m2"] = row["plotas_m2"]
                room["plotas_saltinis"] = "eksplikacija"
    return rooms


def test_duplicate_names_do_not_collapse():
    rooms = [{"nr": "108", "pavadinimas": "Berniuko kambarys", "plotas_m2": 0},
             {"nr": "109", "pavadinimas": "Berniuko kambarys", "plotas_m2": 0}]
    eks = [{"nr": "108", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.71},
           {"nr": "109", "pavadinimas": "Berniuko kambarys", "plotas_m2": 14.02}]
    out = _merge(rooms, eks)
    assert out[0]["plotas_m2"] == 12.71
    assert out[1]["plotas_m2"] == 14.02, "twin bedrooms collapsed onto one row"


def test_punctuation_drift_still_matches_by_nr():
    rooms = [{"nr": "107", "pavadinimas": "Vaikų san.mazgas", "plotas_m2": 8.59}]
    eks = [{"nr": "107", "pavadinimas": "Vaikų san. mazgas", "plotas_m2": 6.59}]
    out = _merge(rooms, eks)
    assert out[0]["plotas_m2"] == 6.59
    assert out[0]["plotas_saltinis"] == "eksplikacija"


def test_name_fallback_when_nr_absent_and_unambiguous():
    rooms = [{"nr": "", "pavadinimas": "Tėvų  vonia", "plotas_m2": 0}]
    eks = [{"nr": "111", "pavadinimas": "Tėvu vonia", "plotas_m2": 7.45}]
    assert _merge(rooms, eks)[0]["plotas_m2"] == 7.45


def test_ambiguous_name_without_nr_is_left_alone():
    rooms = [{"nr": "", "pavadinimas": "Berniuko kambarys", "plotas_m2": 99.0}]
    eks = [{"nr": "108", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.71},
           {"nr": "109", "pavadinimas": "Berniuko kambarys", "plotas_m2": 14.02}]
    out = _merge(rooms, eks)
    assert out[0]["plotas_m2"] == 99.0, "guessed between two equally-named rows"
    assert "plotas_saltinis" not in out[0]
