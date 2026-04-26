"""
Phase 1 — Project Analyzer.
ONE API call with targeted pages to extract room table and classify project.
Strategy: send first N pages at medium DPI (table is usually on page 1 or early pages).
"""
import base64
import io
import pathlib
from dotenv import load_dotenv
from anthropic import Anthropic
from vision_tools import PROJECT_ANALYZER_TOOL

load_dotenv(pathlib.Path(__file__).parent / ".env")

VISION_MODEL = "claude-opus-4-7"
_client: Anthropic | None = None

_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "phase1_analyzer.txt"

# Phase 1 image settings — balance readability vs token count
# At 150 DPI, A3 page ≈ 1754×1240px → resize to 1200px → ~960 tokens per image
# 20 images × 960 = 19,200 tokens (well under 30k TPM limit)
_PHASE1_DPI = 150
_PHASE1_MAX_DIM = 1200
_PHASE1_QUALITY = 75
_PHASE1_MAX_PAGES = 20


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _img_to_b64(img, max_dim: int = _PHASE1_MAX_DIM, quality: int = _PHASE1_QUALITY) -> str:
    """Resize PIL image and encode as base64 JPEG."""
    from PIL import Image
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _select_pages_for_phase1(pdf_bytes: bytes, max_pages: int = _PHASE1_MAX_PAGES) -> list[int]:
    """
    Smart page selection: prioritize pages likely to contain the room table.
    Returns 1-based page numbers to include, capped at max_pages.
    """
    import pdfplumber

    table_pages = []
    other_important = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)
        for i, page in enumerate(pdf.pages[:min(total, 60)]):
            pno = i + 1
            text = (page.extract_text() or "").lower()
            # Explicit room table markers
            if any(k in text for k in ("patalpų eksplikacija", "eksplikacija", "pavadinimas", "tambūras")):
                table_pages.append(pno)
            # Floor/partition plan markers
            elif any(k in text for k in ("pertvarų planas", "baldų išdėstymo", "aukšto planas")):
                other_important.append(pno)

    # Always include page 1 (often has title block + room table)
    selected = sorted(set([1] + table_pages[:5] + other_important[:3]))

    # Fill remaining budget with early pages
    remaining = max_pages - len(selected)
    if remaining > 0:
        early = [p for p in range(2, min(21, max_pages + 5)) if p not in selected]
        selected = sorted(set(selected + early[:remaining]))

    return selected[:max_pages]


def pdf_to_b64_pages_phase1(pdf_bytes: bytes, max_pages: int = _PHASE1_MAX_PAGES) -> list[str]:
    """Convert selected PDF pages to base64 JPEGs for Phase 1."""
    from pdf2image import convert_from_bytes

    page_numbers = _select_pages_for_phase1(pdf_bytes, max_pages)
    if not page_numbers:
        page_numbers = list(range(1, max_pages + 1))

    result = []
    for pno in page_numbers:
        try:
            images = convert_from_bytes(
                pdf_bytes, dpi=_PHASE1_DPI, fmt="jpeg",
                first_page=pno, last_page=pno
            )
            if images:
                result.append(_img_to_b64(images[0]))
        except Exception:
            continue
    return result


def phase1_analyze_project(pdf_pages_base64: list[str], max_pages: int = _PHASE1_MAX_PAGES) -> dict:
    """
    Extract room table, classify project complexity.
    Sends up to max_pages pre-selected images in a single API call.
    """
    client = _get_client()
    prompt_text = _load_prompt()

    pages_to_send = pdf_pages_base64[:max_pages]

    content_blocks: list[dict] = []
    for b64 in pages_to_send:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    content_blocks.append({"type": "text", "text": prompt_text})

    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        tools=[PROJECT_ANALYZER_TOOL],
        tool_choice={"type": "tool", "name": "analyze_project_context"},
        messages=[{"role": "user", "content": content_blocks}],
    )

    for block in response.content:
        if block.type == "tool_use":
            result = dict(block.input)
            result["_pages_sent"] = len(pages_to_send)
            return result

    raise ValueError("Phase 1: Claude did not call analyze_project_context tool")


def phase1_from_pdf_bytes(pdf_bytes: bytes, max_pages: int = _PHASE1_MAX_PAGES) -> dict:
    """Convenience wrapper: convert PDF bytes directly to Phase 1 result."""
    pages = pdf_to_b64_pages_phase1(pdf_bytes, max_pages=max_pages)
    return phase1_analyze_project(pages, max_pages=max_pages)
