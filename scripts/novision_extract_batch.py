"""Run the no-vision route on the corpus and write ground_truth/<slug>/ai_extract_novision.json."""
import json, os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

CORPUS = {
    "objektas_a": "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf",
    "objektas_b": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 1/TP_Objektas B_2025naujausias.pdf",
    "objektas_c": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 2/Techninio projekto planai_20250501 (a3)_2.pdf",
    "objektas_d": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 5/objektas_d_TP_bundled.pdf",
    "objektas_g": "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_g/project.pdf",
    "objektas_h": "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_h/project.pdf",
}

from extractor.no_vision_route import extract_interior_no_vision, should_use_no_vision

results = {}
for slug, rel in CORPUS.items():
    pdf = REPO / rel
    if not pdf.exists():
        print(f"[{slug}] MISSING {pdf}", flush=True)
        continue
    b = pdf.read_bytes()
    use, sent = should_use_no_vision(b)
    print(f"[{slug}] START vector={use} size={len(b)//1024}KB", flush=True)
    t = time.time()
    out = extract_interior_no_vision(b, None, route_sentence=sent)
    dur = round(time.time() - t, 1)
    out_path = REPO / f"ground_truth/{slug}/ai_extract_novision.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    meta = out.get("_meta", {})
    bz = meta.get("braizinio_skaitymas", {}) or {}
    sek = bz.get("sekundes") or {}
    results[slug] = {
        "elapsed_s": dur,
        "status": out.get("status"),
        "rooms": len(out.get("patalpos") or []),
        "pozicijos": len(out.get("pozicijos") or []),
        "bendras_plotas_m2": out.get("bendras_plotas_m2"),
        "lanes_s": bz.get("viso_s"),
        "lane_sek": sek,
        "no_vision_sek": meta.get("no_vision_sekundes"),
    }
    print(f"[{slug}] DONE {dur}s rooms={len(out.get('patalpos') or [])} poz={len(out.get('pozicijos') or [])}", flush=True)

(REPO / "ground_truth/_novision_runtime.json").write_text(json.dumps(results, indent=2))
print("done", flush=True)
