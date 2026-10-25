"""Two helpers the remaining Vision readers (height_extractor, schedule_extractor — Phase 3c) share. They lived
in `dimension_extractor`, deleted in v4 Phase 3b (dimension strings come from the text layer)."""
from __future__ import annotations

import json
from typing import Any


def _decode_response_json(text: str) -> dict[str, Any]:
    """Robust JSON decode for model output: code fences, leading/trailing prose, a BOM; falls back to the first
    top-level JSON object by brace matching."""
    if not text:
        raise ValueError("empty model response")
    s = text.strip().lstrip("﻿")
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start: i + 1])
    raise ValueError("unbalanced JSON object in response")


def _detect_image_media_type(img_bytes: bytes) -> str:
    """Sniff a decoded image's media type (png, jpeg, webp, gif; png by default)."""
    if img_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if img_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
        return "image/webp"
    if img_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/png"
