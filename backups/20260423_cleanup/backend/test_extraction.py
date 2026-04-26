#!/usr/bin/env python3
"""
test_extraction.py — compare _extract_kz_direct() against Opus ground-truth JSON files.

Usage:
    cd ~/samatu-ai
    source venv/bin/activate
    python backend/test_extraction.py
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from main import _extract_kz_direct

# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------

PDF_DIR  = Path(__file__).parent / "test_pdfs"
TEST_DIR = Path(__file__).parent / "tests"

# Each entry: (pdf_path, expected_json_path, expected_row_count_or_None_for_no_kz)
CASES = [
    (PDF_DIR / "03_SA.pdf",       TEST_DIR / "03_SA_expected.json",  None),
    (PDF_DIR / "1_BD.pdf",        None,                               0),   # no KŽ table
    (PDF_DIR / "SA-02.pdf",       None,                               0),   # no KŽ table
]

PASS  = "\033[32m✓\033[0m"
FAIL  = "\033[31m✗\033[0m"
WARN  = "\033[33m~\033[0m"
EXTRA = "\033[35m+\033[0m"   # magenta + for extra rows
MISS  = "\033[36m-\033[0m"   # cyan   - for missing rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_key(r: dict) -> tuple:
    """Canonical identity key: (nr, mato_vnt, skyrius)."""
    return (r.get("nr", ""), r.get("mato_vnt", ""), r.get("skyrius", ""))


def _row_key_with_kiekis(r: dict) -> tuple:
    """Stricter key that also includes kiekis — used for exact-match lookup."""
    return (r.get("nr", ""), r.get("mato_vnt", ""), r.get("skyrius", ""), r.get("kiekis"))


def _fmt_row(r: dict, label: str = "") -> str:
    k = r.get("kiekis")
    kstr = str(k) if k is not None else "null"
    sec  = r.get("skyrius", "")[:30]
    apr  = r.get("aprasymas", "")[:55]
    return (
        f"  {label:2s}  nr={r.get('nr','?'):6s}  {r.get('mato_vnt','?'):6s}"
        f"  kiekis={kstr:<10s}  [{sec}]  {apr}"
    )


# ---------------------------------------------------------------------------
# Core comparison
# ---------------------------------------------------------------------------

def compare_against_expected(extracted: list[dict], expected: list[dict], pdf_name: str) -> bool:
    print(f"\n{'='*68}")
    print(f"  {pdf_name}")
    print(f"{'='*68}")

    n_ext = len(extracted)
    n_exp = len(expected)
    count_ok = n_ext == n_exp
    mark = PASS if count_ok else FAIL
    print(f"  {mark} Row count:  extracted={n_ext}  expected={n_exp}")

    # ── Section breakdown ──────────────────────────────────────────────────
    ext_by_sec: dict[str, int] = defaultdict(int)
    exp_by_sec: dict[str, int] = defaultdict(int)
    for r in extracted:
        ext_by_sec[r.get("skyrius", "")] += 1
    for r in expected:
        exp_by_sec[r.get("skyrius", "")] += 1

    all_secs = sorted(set(ext_by_sec) | set(exp_by_sec))
    for sec in all_secs:
        e, a = ext_by_sec.get(sec, 0), exp_by_sec.get(sec, 0)
        m = PASS if e == a else FAIL
        print(f"    {m}  [{sec[:60]}]  extracted={e}  expected={a}")

    # ── Duplicate detection (spurious: same key including kiekis) ──────────
    seen: set = set()
    spurious_dups = []
    for r in extracted:
        k = _row_key_with_kiekis(r)
        if k in seen:
            spurious_dups.append(r)
        else:
            seen.add(k)
    if spurious_dups:
        print(f"  {FAIL} Spurious duplicate rows: {len(spurious_dups)}")
        for d in spurious_dups[:5]:
            print(_fmt_row(d, FAIL))
    else:
        print(f"  {PASS} No spurious duplicates")

    # ── Build lookup structures ────────────────────────────────────────────
    # Index expected by (nr, mato_vnt, skyrius) — allows multiple rows per key
    exp_by_key: dict[tuple, list] = defaultdict(list)
    for r in expected:
        exp_by_key[_row_key(r)].append(r)

    ext_by_key: dict[tuple, list] = defaultdict(list)
    for r in extracted:
        ext_by_key[_row_key(r)].append(r)

    # ── Missing rows (in expected, absent from extracted) ─────────────────
    missing = []
    for key, exp_rows in exp_by_key.items():
        ext_rows = ext_by_key.get(key, [])
        if len(ext_rows) < len(exp_rows):
            missing.extend(exp_rows[len(ext_rows):])

    # ── Extra rows (in extracted, absent from expected) ───────────────────
    extra = []
    for key, ext_rows in ext_by_key.items():
        exp_rows = exp_by_key.get(key, [])
        if len(ext_rows) > len(exp_rows):
            extra.extend(ext_rows[len(exp_rows):])

    if missing:
        print(f"\n  {MISS} MISSING rows ({len(missing)}) — in expected but not extracted:")
        for r in missing:
            print(_fmt_row(r, MISS))

    if extra:
        print(f"\n  {EXTRA} EXTRA rows ({len(extra)}) — extracted but not in expected:")
        for r in extra:
            print(_fmt_row(r, EXTRA))

    # ── Field-level diffs for matched rows ────────────────────────────────
    field_diffs = []
    for key in set(exp_by_key) & set(ext_by_key):
        for exp_r, ext_r in zip(exp_by_key[key], ext_by_key[key]):
            diffs = []
            for field in ("kiekis", "aprasymas"):
                ev, av = exp_r.get(field), ext_r.get(field)
                # kiekis: compare as float when both numeric
                if field == "kiekis":
                    try:
                        if ev is not None and av is not None and float(ev) != float(av):
                            diffs.append((field, av, ev))
                        elif (ev is None) != (av is None):
                            diffs.append((field, av, ev))
                    except (TypeError, ValueError):
                        if ev != av:
                            diffs.append((field, av, ev))
                else:
                    if ev != av:
                        diffs.append((field, av, ev))
            if diffs:
                field_diffs.append((ext_r, diffs))

    if field_diffs:
        print(f"\n  {WARN} Field mismatches in matched rows ({len(field_diffs)}):")
        for row, diffs in field_diffs[:10]:
            print(_fmt_row(row, WARN))
            for field, got, want in diffs:
                g = repr(got)[:60] if isinstance(got, str) else got
                w = repr(want)[:60] if isinstance(want, str) else want
                print(f"       {field}: got={g}  want={w}")
    elif not missing and not extra:
        print(f"  {PASS} All matched rows have correct field values")

    ok = count_ok and not missing and not extra and not spurious_dups and not field_diffs
    return ok


# ---------------------------------------------------------------------------
# No-KŽ cases (expect direct extraction to return None)
# ---------------------------------------------------------------------------

def check_no_kz(pdf_path: Path) -> bool:
    print(f"\nExtracting {pdf_path.name} …", end="", flush=True)
    result = _extract_kz_direct(pdf_path.read_bytes())
    if result is None:
        print(f" OK (correctly returned None — no KŽ table)")
        print(f"  {PASS} Direct extraction returned None as expected")
        return True
    else:
        _, rows = result
        print(f" FAILED ({len(rows)} rows returned, expected None)")
        print(f"  {FAIL} Expected no KŽ table — got {len(rows)} rows")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_pass = True
    tested = 0

    for pdf_path, expected_path, zero_row_flag in CASES:
        if not pdf_path.exists():
            print(f"\n  [skip] {pdf_path.name} not found")
            continue

        # No-KŽ case
        if zero_row_flag == 0:
            ok = check_no_kz(pdf_path)
            if not ok:
                all_pass = False
            tested += 1
            continue

        # Has-KŽ case
        if expected_path is None or not expected_path.exists():
            print(f"\n  [skip] expected JSON not found: {expected_path}")
            continue

        expected = json.loads(expected_path.read_text(encoding="utf-8"))

        print(f"\nExtracting {pdf_path.name} …", end="", flush=True)
        result = _extract_kz_direct(pdf_path.read_bytes())

        if result is None:
            print(f" FAILED (returned None — no KŽ table detected)")
            print(f"  {FAIL} Expected {len(expected)} rows — got None")
            all_pass = False
            tested += 1
            continue

        _, extracted = result
        print(f" done  ({len(extracted)} rows)")

        ok = compare_against_expected(extracted, expected, pdf_path.name)
        if not ok:
            all_pass = False
        tested += 1

    print(f"\n{'='*68}")
    if tested == 0:
        print("  No test cases found")
        sys.exit(1)
    elif all_pass:
        print(f"  {PASS}  ALL {tested} test(s) PASSED")
    else:
        print(f"  {FAIL}  Some tests FAILED (see above)")
    print()

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
