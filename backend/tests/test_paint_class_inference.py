"""Sprint 0 Fix 5: prefer paint class inferred from spec text when present."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from extractor.vision_call import _resolve_paint_class


def test_inferred_class_used_when_flag_on_and_present(monkeypatch):
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "1")
    user_default = 1
    inferred = 2
    inferred_text = "Q2 matinis dažymas"
    cls, src = _resolve_paint_class(user_default, inferred, inferred_text)
    assert cls == 2
    assert src == "inferred_from_spec"


def test_falls_back_to_user_when_inference_missing(monkeypatch):
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "1")
    cls, src = _resolve_paint_class(user_default=1, inferred=None, inferred_text=None)
    assert cls == 1
    assert src == "user_default"


def test_flag_off_always_uses_user(monkeypatch):
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "0")
    cls, src = _resolve_paint_class(user_default=1, inferred=2, inferred_text="Q2")
    assert cls == 1
    assert src == "user_default"
