"""Throwaway: dump the samata PDF's text lines that carry a quantity, so the
line-item DESCRIPTIONS behind each truth number can be read. Local only."""
import sys, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import eval_harness as EH  # noqa: E402
import pdfplumber  # noqa: E402

slug = sys.argv[1]
needles = [n.lower() for n in sys.argv[2:]]
import yaml  # noqa: E402
reg = yaml.safe_load((ROOT / "ground_truth/registry.yaml").read_text(encoding="utf-8"))
entry = next(e for e in reg["projects"] if e["slug"] == slug)
pdf = ROOT / entry["samata_pdf"]
with pdfplumber.open(str(pdf)) as doc:
    for pi, page in enumerate(doc.pages):
        for line in (page.extract_text() or "").splitlines():
            s = line.strip()
            if not s:
                continue
            if needles:
                if any(n in s.lower() for n in needles):
                    print(f"p{pi+1}: {s}")
            elif re.search(r"\bm2\b|\bm²\b|\bb/m\b|\bm\b", s):
                print(f"p{pi+1}: {s}")
