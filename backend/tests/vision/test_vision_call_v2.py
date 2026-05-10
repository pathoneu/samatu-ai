"""Week 3 Task 3.1 — verify the Opus 4.7 v2 vision call uses strict JSON schema
and 1h cache TTL, and never passes the deprecated `temperature` parameter.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.extractor import vision_call_v2  # noqa: E402


def test_module_does_not_use_regex_repair():
    src = inspect.getsource(vision_call_v2)
    assert "_repair_json" not in src, "regex repair removed in v2 (uses output_config.format)"
    # Avoid `re.` standalone checks — only fail if we find an `import re` at module top.
    first_line = src.split("\n", 1)[0]
    assert "import re" not in first_line


def test_call_uses_output_config_format_and_explicit_ttl():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = MagicMock()

    schema = {"type": "object", "properties": {}}
    vision_call_v2.call_opus_vision(
        fake_client,
        system_text="hello",
        messages=[{"role": "user", "content": []}],
        schema=schema,
        effort="high",
    )

    fake_client.messages.create.assert_called_once()
    kwargs = fake_client.messages.create.call_args.kwargs
    # Strict JSON schema enforcement (no regex repair fallback).
    output_cfg = kwargs["output_config"]
    assert output_cfg["format"]["type"] == "json_schema"
    assert output_cfg["format"]["json_schema"]["schema"] is schema
    assert output_cfg["effort"] == "high"
    # Cache invariant: system has the breakpoint with explicit 1h TTL.
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    # No `temperature` (Opus 4.7 returns 400 on it).
    assert "temperature" not in kwargs


def test_build_image_message_orders_text_label_before_image():
    msg = vision_call_v2.build_image_message(
        pages=[
            {"page_index": 1, "image_b64": "A" * 32},
            {"page_index": 2, "image_b64": "B" * 32},
        ],
        final_instruction="Now extract.",
    )
    assert msg["role"] == "user"
    content = msg["content"]
    # Pattern: [text:"Page 1 of 2:", image, text:"Page 2 of 2:", image, text:final]
    assert content[0]["type"] == "text" and "Page 1 of 2" in content[0]["text"]
    assert content[1]["type"] == "image"
    assert content[2]["type"] == "text" and "Page 2 of 2" in content[2]["text"]
    assert content[3]["type"] == "image"
    assert content[4]["type"] == "text" and "Now extract." in content[4]["text"]
