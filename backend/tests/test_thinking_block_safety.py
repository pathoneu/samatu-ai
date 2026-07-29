"""No reader may crash on a ThinkingBlock (2026-07-29).

Opus 5 has extended thinking ON by default, so `resp.content[0]` is often a
ThinkingBlock with no `.text`. Every site that did `resp.content[0].text`
died with AttributeError — INTERMITTENTLY, because whether a thinking block
is emitted varies run to run. Measured cost: the apdailos reader died
mid-run on berzas, every room fell back to paskirtis defaults, 31.45 m² of
real garage paint vanished and headline MAE went 6.116% → 12.996%.

This test fails the build if any extractor reaches into content[0].text
again, and proves the shared helper skips thinking blocks.
"""
import pathlib
import types

from extractor.response_text import response_text


def test_response_text_skips_thinking_blocks():
    resp = types.SimpleNamespace(content=[
        types.SimpleNamespace(type="thinking", thinking="hmm..."),   # no .text
        types.SimpleNamespace(type="text", text='{"ok": 1}'),
    ])
    assert response_text(resp) == '{"ok": 1}'


def test_response_text_handles_text_first_and_multi_block():
    resp = types.SimpleNamespace(content=[
        types.SimpleNamespace(type="text", text="a"),
        types.SimpleNamespace(type="text", text="b"),
    ])
    assert response_text(resp) == "ab"


def test_response_text_empty_when_no_text_blocks():
    resp = types.SimpleNamespace(content=[
        types.SimpleNamespace(type="thinking", thinking="only thinking"),
    ])
    assert response_text(resp) == ""


def test_no_extractor_reads_content_zero_text():
    """The regression guard: one grep across the whole extractor package."""
    root = pathlib.Path(__file__).resolve().parents[1] / "extractor"
    offenders = []
    for p in root.rglob("*.py"):
        if p.name == "response_text.py":
            continue
        txt = p.read_text(encoding="utf-8")
        if "content[0].text" in txt:
            offenders.append(str(p.relative_to(root)))
    assert not offenders, (
        "these readers will crash on a ThinkingBlock — use "
        f"response_text(resp) instead: {offenders}")
