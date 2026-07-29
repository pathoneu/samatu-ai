"""Every Vision reader's max_tokens must fit an answer ALONGSIDE thinking.

2026-07-29: apdailos_reader shipped with MAX_TOKENS = 4096. Opus 5 runs
extended thinking by default and it counts against the SAME cap, so the
answer was cut mid-JSON and the reader silently returned nothing — measured
on the identical PDF, output was 2,776 tokens one run and 4,757 the next,
and the reader failed in 3 of 4 paid runs. Headline MAE 4.8% when it lived,
13-14% when it died.

Two invariants, so this cannot regress or over-correct:
  · big enough — a snug cap is shared with a variable-length thinking block
  · under the SDK's non-streaming ceiling — above 21,333 the client raises
    ValueError BEFORE any HTTP call, i.e. the same silent failure from a
    new cause.
"""
import importlib

import pytest

from extractor.apdailos_reader import MAX_TOKENS_NONSTREAMING_CEILING

READERS = [
    "extractor.apdailos_reader",
    "extractor.doors_reader",
    "extractor.door_type_reader",
    "extractor.sanitary_fixture_reader",
]
MIN_SAFE = 8192


@pytest.mark.parametrize("mod_name", READERS)
def test_reader_cap_leaves_room_for_thinking(mod_name):
    mod = importlib.import_module(mod_name)
    cap = getattr(mod, "MAX_TOKENS")
    assert cap >= MIN_SAFE, (
        f"{mod_name}.MAX_TOKENS={cap} is shared with Opus 5 thinking; a "
        f"truncated answer fails SILENTLY (see this module's docstring)")


@pytest.mark.parametrize("mod_name", READERS)
def test_reader_cap_under_sdk_nonstreaming_ceiling(mod_name):
    mod = importlib.import_module(mod_name)
    cap = getattr(mod, "MAX_TOKENS")
    assert cap <= MAX_TOKENS_NONSTREAMING_CEILING, (
        f"{mod_name}.MAX_TOKENS={cap} exceeds the SDK non-streaming ceiling "
        f"{MAX_TOKENS_NONSTREAMING_CEILING}; the client raises before the call")
