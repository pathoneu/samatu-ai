#!/usr/bin/env python3
"""Download the OCR model files into backend/data/models/ocr/ (gitignored) — run at image build.

    python scripts/fetch_ocr_models.py [--dir DIR] [--soft]

`backend/text/ocr.py` (RapidEngine) loads its three ONNX models (PP-OCRv6 medium detector, PP-OCRv6 medium
multilingual recogniser with Lithuanian, the text-direction classifier) from that directory; in production it never
downloads them while a person waits. The file names, URLs and SHA-256 sums come from RapidOCR's own model table
(`text.ocr.model_files()`), so this script and the engine always agree. Each file is checked against its SHA-256;
an existing file that matches is kept, one that does not is downloaded again. Up to 3 attempts per file.

`--soft`: a failed download prints a warning and exits 0 — the build goes on, OCR then stays unavailable (the
feature is behind SAMATU_OCR, default OFF), and the first OCR attempt says the models are missing.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ATTEMPTS = 3


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path, sha256: str | None) -> None:
    if dest.is_file() and (not sha256 or _sha256(dest) == sha256):
        print(f"ok (present)  {dest.name}")
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, tmp.open("wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            got = _sha256(tmp)
            if sha256 and got != sha256:
                raise ValueError(f"SHA-256 mismatch for {dest.name}: {got} != {sha256}")
            tmp.replace(dest)
            print(f"ok (fetched)  {dest.name}  {dest.stat().st_size / 1e6:.1f} MB")
            return
        except Exception as e:  # noqa: BLE001 — retried, then reported
            last = e
            tmp.unlink(missing_ok=True)
            print(f"attempt {attempt}/{ATTEMPTS} failed for {dest.name}: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise RuntimeError(f"could not fetch {dest.name}") from last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=None, help="target directory (default: text.ocr.model_dir())")
    ap.add_argument("--soft", action="store_true", help="warn instead of failing when a download fails")
    args = ap.parse_args()
    try:
        from text.ocr import model_dir, model_files
        target = args.dir or model_dir()
        target.mkdir(parents=True, exist_ok=True)
        for task, f in model_files().items():
            fetch(f["url"], target / f["file"], f.get("sha256"))
    except Exception as e:  # noqa: BLE001
        if args.soft:
            print(f"WARNING: OCR models not fetched ({e}); OCR stays unavailable until they are.", file=sys.stderr)
            return 0
        raise
    print(f"OCR models in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
