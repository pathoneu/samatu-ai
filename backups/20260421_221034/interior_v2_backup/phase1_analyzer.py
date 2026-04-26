"""
V2.1 Phase 1 — Project Analyzer.
Multi-file aware: accepts all pages from all PDFs as one collection.
"""
import base64
import io
import time
from typing import Any

from anthropic import Anthropic

from .tools import PROJECT_ANALYZER_TOOL
from .prompts import PHASE1_PROMPT

VISION_MODEL = "claude-opus-4-7"
_MAX_PHASE1_PAGES = 20
_DPI = 150
_MAX_DIM = 1200
_QUALITY = 75

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _resize_b64(b64: str, max_dim: int = _MAX_DIM, quality: int = _QUALITY) -> str:
    from PIL import Image
    data = base64.b64decode(b64)
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _select_pages(all_pages: list[dict], max_pages: int = _MAX_PHASE1_PAGES) -> list[dict]:
    """
    Smart selection: prioritize pages likely to contain room table.
    Prefers pages from partition/furniture plans, first pages of each file.
    """
    import re
    table_keywords = re.compile(
        r"patalpų eksplikacija|eksplikacija|pavadinimas|tambūras|baldų išdėstymo|pertvarų planas",
        re.I,
    )
    high_priority = []
    medium_priority = []
    low_priority = []

    for page in all_pages:
        text = page.get("text", "")
        filename = page.get("filename", "").lower()
        is_first = page.get("page_idx", 0) == 0

        if table_keywords.search(text) or "pertvara" in filename or "baldai" in filename:
            high_priority.append(page)
        elif is_first:
            medium_priority.append(page)
        else:
            low_priority.append(page)

    selected = []
    for bucket in [high_priority, medium_priority, low_priority]:
        for page in bucket:
            if len(selected) >= max_pages:
                break
            if page not in selected:
                selected.append(page)
        if len(selected) >= max_pages:
            break

    return selected[:max_pages]


def phase1_analyze_project(all_pages: list[dict]) -> dict[str, Any]:
    """
    Phase 1: extract room table, classify project.
    all_pages: list of {filename, page_idx, image_b64, text (optional)}
    """
    client = _get_client()
    pages = _select_pages(all_pages)

    filenames = sorted({p["filename"] for p in all_pages})
    num_files = len(filenames)
    filenames_list = "\n".join(f"  - {f}" for f in filenames)

    prompt = PHASE1_PROMPT.format(
        num_files=num_files,
        filenames_list=filenames_list,
    )

    # Build vision content blocks
    content: list[dict] = [{"type": "text", "text": prompt}]
    for i, page in enumerate(pages):
        b64 = page.get("image_b64", "")
        if not b64:
            continue
        try:
            b64 = _resize_b64(b64)
        except Exception:
            pass
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64,
            },
        })
        content.append({
            "type": "text",
            "text": f"[Page {i+1} from '{page['filename']}', page index {page['page_idx']+1}]",
        })

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=VISION_MODEL,
                max_tokens=4096,
                tools=[PROJECT_ANALYZER_TOOL],
                tool_choice={"type": "tool", "name": "analyze_project_context"},
                messages=[{"role": "user", "content": content}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    return dict(block.input)
            raise ValueError("Phase 1: tool not called")
        except Exception as exc:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

    raise ValueError("Phase 1: all retries failed")
