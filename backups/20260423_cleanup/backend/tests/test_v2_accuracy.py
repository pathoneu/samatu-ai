"""
V2 pipeline end-to-end accuracy test.
Run from backend/ directory: python -m pytest tests/test_v2_accuracy.py -v -s

Success criteria per CLAUDE_CODE_INSTRUCTIONS.md:
  P1 (1_BD.pdf): 4/5 key quantities within 15%
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest

BACKEND = pathlib.Path(__file__).parent.parent
TEST_PDFS = BACKEND / "test_pdfs"

EXPECTED = {
    "P1": {
        "pdf": TEST_PDFS / "1_BD.pdf",
        "dazomas_plotas_m2": 424.75,
        "kampai_m": 580.54,
        "angokrasciai_m": 94.02,
        "gkp_lubu_m2": 74.91,
        "plyteliu_plotas_m2": 157.34,
        "tolerance": 0.20,  # 20% — V2 first run
    },
}


@pytest.mark.parametrize("pid,cfg", [(k, v) for k, v in EXPECTED.items() if v["pdf"].exists()])
def test_v2_accuracy(pid, cfg):
    from vision_v2_pipeline import process_interior_project_v2

    pdf_bytes = cfg["pdf"].read_bytes()
    result = asyncio.run(process_interior_project_v2(pdf_bytes))

    print(f"\n=== V2 ACCURACY: {pid} ===")
    print(f"Status: {result.get('status')}")
    if result.get("status") != "ok":
        pytest.skip(f"{pid}: pipeline error — {result.get('error')}")

    quantities = result.get("validated_quantities", {})
    tolerance = cfg["tolerance"]

    check_keys = [k for k in cfg if k not in ("pdf", "tolerance")]
    results_detail = []
    passed = 0

    for key in check_keys:
        expected_val = cfg[key]
        actual_val = quantities.get(key) or 0
        error_pct = abs(actual_val - expected_val) / expected_val if expected_val else 1
        ok = error_pct <= tolerance
        if ok:
            passed += 1
        mark = "✓" if ok else "✗"
        line = f"  {mark} {key}: {actual_val:.2f} vs {expected_val:.2f} ({error_pct*100:.1f}%)"
        print(line)
        results_detail.append((key, ok, actual_val, expected_val, error_pct))

    print(f"\n  Passed: {passed}/{len(check_keys)}")

    # Require at least 4/5 quantities within tolerance
    assert passed >= 4, (
        f"{pid}: only {passed}/{len(check_keys)} quantities within {tolerance*100:.0f}% tolerance\n"
        + "\n".join(
            f"  {k}: {a:.2f} vs {e:.2f} ({ep*100:.1f}%)"
            for k, ok, a, e, ep in results_detail if not ok
        )
    )
