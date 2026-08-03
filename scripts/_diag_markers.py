"""Throwaway: enumerate every `+NNNN` token the marker regexes can see in each
corpus PDF. Zero API calls.

READ THIS BEFORE QUOTING THE NUMBERS: this script applies `_to_metres` (which
divides a bare 4-digit capture by 1000). The SHIPPED `scan_page_height_markers`
does NOT — it range-checks the raw capture, so `+3400` (3400) and `+3706`
(3706) both fall outside [2.0, 4.5] and are rejected. Consequence measured
2026-08-03: the shipped page-marker lane returns ZERO markers on all six corpus
PDFs. What this script shows is the token inventory the regexes match, i.e. the
BLAST RADIUS if anyone ever adds the mm conversion to the scanner — not the
lane's live output.
"""
import sys, pathlib, io, re, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import yaml, pdfplumber  # noqa: E402
from extractor import height_markers as hm  # noqa: E402

reg = yaml.safe_load((ROOT / "ground_truth/registry.yaml").read_text(encoding="utf-8"))

# --- candidate gate -------------------------------------------------------
# Strict drafting-marker token: sign, then at most 5 chars of digits with at
# most one separator, and NOT a prefix of a longer digit/word run.
STRICT = re.compile(r'(?<![\w.,])[+±]\s*(\d{1,2}[.,]\d{1,3}|\d{3,4})(?![\d.,\w])')


def gated(text):
    out = []
    for m in STRICT.finditer(text):
        v = hm._to_metres(m.group(1), "marker")
        if v is not None and round(v * 1000) % 10 == 0:
            out.append((m.group(0), v))
    return out


for e in reg["projects"]:
    p = ROOT / e["project_pdf"]
    if not p.exists():
        print(f"{e['slug']:<12} PDF absent")
        continue
    raw = p.read_bytes()
    with pdfplumber.open(io.BytesIO(raw)) as doc:
        pages = [(i + 1, doc.pages[i].extract_text() or "")
                 for i in range(len(doc.pages))]
    cur, new = [], []
    for pn, t in pages:
        for m in hm._HEIGHT_MARKER_RE.finditer(t):
            v = hm._to_metres(m.group(1), "marker")
            if v is not None:
                cur.append((pn, m.group(0), v))
        for tok, v in gated(t):
            new.append((pn, tok, v))
    cb = max(cur, key=lambda x: x[2]) if cur else None
    nb = max(new, key=lambda x: x[2]) if new else None
    print(f"\n=== {e['slug']}  ({len(pages)} pages)")
    print(f"  CURRENT: n={len(cur):<4} best={cb}")
    print(f"  GATED  : n={len(new):<4} best={nb}")
    cc = collections.Counter(v for _, _, v in cur)
    nc = collections.Counter(v for _, _, v in new)
    print(f"  current values: {sorted(cc.items(), key=lambda kv: -kv[1])[:8]}")
    print(f"  gated   values: {sorted(nc.items(), key=lambda kv: -kv[1])[:8]}")
    dropped = [x for x in cur if (x[1], x[2]) not in {(t, v) for _, t, v in new}]
    if dropped:
        seen = collections.Counter((t, v) for _, t, v in dropped)
        print(f"  DROPPED tokens: {sorted(seen.items(), key=lambda kv: -kv[1])[:10]}")
