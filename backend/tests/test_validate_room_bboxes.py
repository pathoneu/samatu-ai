"""Sprint 4 follow-up: _validate_room_bboxes warns when room bboxes
look like Vision pointed at labels/elevations instead of floor plan rooms."""
from extractor.vision_call import _validate_room_bboxes


def test_warns_when_bboxes_too_small_to_be_floor_plan():
    # 15 rooms each occupying tiny ~1.8% of page — total ~27%? Actually:
    # 10% × 18% = 1.8% per room × 15 rooms = 27% — but rooms can overlap.
    # Make them all small enough so even union is < 5%.
    result = {
        "patalpos": [
            {"pavadinimas": f"R{i}", "bbox_pct": {"x": 0.4, "y": 0.4, "w": 0.02, "h": 0.02}}
            for i in range(10)
        ],
    }
    out = _validate_room_bboxes(result)
    warnings = out.get("warnings") or []
    assert len(warnings) == 1
    assert warnings[0]["code"] == "bbox_pct_floor_plan_unlikely"
    assert warnings[0]["severity"] == "warning"


def test_no_warning_when_bboxes_cover_typical_floor_plan_area():
    # 4 rooms each ~10% × 10% = 1% per room × 4 = 4%? Actually want ≥ 5%.
    # 5 rooms each 10% × 12% = 1.2% × 5 = 6%.
    result = {
        "patalpos": [
            {"pavadinimas": f"R{i}", "bbox_pct": {"x": 0.1 * i, "y": 0.3, "w": 0.10, "h": 0.12}}
            for i in range(5)
        ],
    }
    out = _validate_room_bboxes(result)
    assert not out.get("warnings")


def test_skipped_when_too_few_boxed_rooms():
    # Only 2 rooms — algorithm bails (need ≥ 3 to be meaningful).
    result = {
        "patalpos": [
            {"pavadinimas": "A", "bbox_pct": {"x": 0.0, "y": 0.0, "w": 0.01, "h": 0.01}},
            {"pavadinimas": "B", "bbox_pct": {"x": 0.5, "y": 0.5, "w": 0.01, "h": 0.01}},
        ],
    }
    out = _validate_room_bboxes(result)
    assert not out.get("warnings")


def test_appends_to_existing_warnings():
    existing = [{"code": "other", "message": "prior"}]
    result = {
        "warnings": existing,
        "patalpos": [
            {"pavadinimas": f"R{i}", "bbox_pct": {"x": 0.0, "y": 0.0, "w": 0.01, "h": 0.01}}
            for i in range(5)
        ],
    }
    out = _validate_room_bboxes(result)
    assert len(out["warnings"]) == 2
    assert out["warnings"][0]["code"] == "other"
    assert out["warnings"][1]["code"] == "bbox_pct_floor_plan_unlikely"


def test_ignores_rooms_with_null_bbox():
    result = {
        "patalpos": [
            {"pavadinimas": "A", "bbox_pct": None},
            {"pavadinimas": "B", "bbox_pct": {"x": 0.4, "y": 0.4, "w": 0.01, "h": 0.01}},
            {"pavadinimas": "C", "bbox_pct": {"x": 0.5, "y": 0.4, "w": 0.01, "h": 0.01}},
        ],
    }
    out = _validate_room_bboxes(result)
    # Only 2 boxed rooms — under threshold for evaluation.
    assert not out.get("warnings")
