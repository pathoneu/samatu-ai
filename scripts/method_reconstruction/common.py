"""Shared helpers for the Phase 0 baseline / Phase 2 method reconstruction.

Reads ONLY from the main checkout (ground truth, fixture PDFs, cached
extracts are gitignored and live there); nothing is copied into the repo.
Outputs go to a directory the caller names (default: $METHOD_OUT, else a
`method_reconstruction_out/` folder under the system temp dir) — never into
the repository, because they carry his row wording.

Confidentiality: project folders are referred to by CODENAME only. The
`objektas_*` folders keep their names; the other truth folders get
`objektas_r1`, `objektas_r2`, … in sorted folder order. No folder name other
than `objektas_*` is ever printed or written by these scripts.

Quantities only: the priced sąmata parse is never read here (the harness
itself prefers it for its € column — that column is not used).

NEVER triggers a paid call: `harness()` swaps the API key for a dead one and
makes the Anthropic client constructor raise.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(os.environ.get("METHOD_REPO", "/Users/ignasgaldikas/samatu-ai"))
GT = REPO / "ground_truth"


def out_dir() -> Path:
    p = Path(os.environ.get("METHOD_OUT") or (Path(tempfile.gettempdir()) / "method_reconstruction_out"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def projects() -> list[tuple[str, str]]:
    """(codename, folder) for every truth folder that carries a parsed sąmata."""
    folders = sorted(d.name for d in GT.iterdir()
                     if d.is_dir() and (d / "contractor_samata_parsed.json").exists())
    named = [(f, f) for f in folders if f.startswith("objektas_")]
    others = [f for f in folders if not f.startswith("objektas_")]
    named += [(f"objektas_r{i}", f) for i, f in enumerate(others, 1)]
    return named


def scrub(text: str) -> str:
    """Replace any non-codename folder name in a string by its codename."""
    for c, f in projects():
        if c != f:
            text = text.replace(f, c)
    return text


def his_rows(folder: str) -> list[dict]:
    """His line items, quantities only (subtotal lines dropped)."""
    d = json.loads((GT / folder / "contractor_samata_parsed.json").read_text(encoding="utf-8"))
    out = []
    for r in d.get("line_items") or []:
        name = " ".join(str(r.get("name") or "").split())
        if not name or name.lower().startswith("viso už skyri"):
            continue
        out.append({"nr": r.get("nr"), "section": r.get("section"), "name": name,
                    "unit": r.get("unit"), "quantity": r.get("quantity")})
    return out


def load_json(folder: str, name: str):
    p = GT / folder / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def block_paid_calls() -> None:
    """Make any Anthropic call fail loudly before it can cost anything."""
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-disabled-method-reconstruction"
    try:
        import anthropic

        def _refuse(*_a, **_k):
            raise RuntimeError("method_reconstruction: a paid Anthropic call was attempted and blocked")
        anthropic.Anthropic.__init__ = _refuse          # type: ignore[method-assign]
        anthropic.AsyncAnthropic.__init__ = _refuse     # type: ignore[method-assign]
    except Exception:  # noqa: BLE001 — no SDK installed means no call either
        pass


def harness():
    """Import the main checkout's eval_harness in-process (cwd = repo)."""
    block_paid_calls()
    os.chdir(REPO)
    for p in (str(REPO / "backend"), str(REPO)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import eval_harness  # noqa: E402
    return eval_harness


def pdf_path(folder: str) -> Path | None:
    t = load_json(folder, "truth.json") or {}
    rel = t.get("pdf_path")
    if rel and (REPO / rel).exists():
        return REPO / rel
    import yaml
    reg = yaml.safe_load((GT / "registry.yaml").read_text(encoding="utf-8"))
    for e in reg.get("projects") or []:
        if e.get("slug") == folder and e.get("project_pdf") and (REPO / e["project_pdf"]).exists():
            return REPO / e["project_pdf"]
    return None
