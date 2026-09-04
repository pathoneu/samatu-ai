"""Experiment 2 — text-derived vs geometry-derived quantities on Objektas A.

Two probes (live Vision, ~$0.3 total), then offline lane analysis:

PROBE A (full-page, current pipeline delivery): objektas_a floor page rendered the
way Pass-1 sees it (≤2000px). Ask ONLY for transcription of per-room dimension
strings (no visual estimation).
PROBE B (tiled delivery): same page at 300 DPI cut into 4 overlapping tiles,
same prompt — pilots the resolution-budget lever from the headroom research.

ANALYSIS: for rooms where text dims exist, perimeter_text = 2*(a+b). Swap into
calc_room_quantities vs the Vision-geometry perimeters; score BOTH lanes through
the same deterministic math against contractor truth (walls 460.71 m²).

Usage:
  venv/bin/python scripts/exp2_text_vs_geometry.py probe    # 2 Vision calls
  venv/bin/python scripts/exp2_text_vs_geometry.py analyze  # offline
"""
from __future__ import annotations

import base64
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

PDF = REPO / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
CACHED = REPO / "ground_truth/objektas_a/ai_extract.json"
OUT = REPO / "eval_runs/2026-06-11_experiments"
FLOOR_PAGE = 2
TRUTH_WALLS = 460.71   # contractor: sienos žemos 278.67 + aukštos 150.59 + garažas 31.45
TRUTH_CEIL = 165.6
MODEL = "claude-opus-4-7"

SYSTEM = (
    "Tu esi LT statybos brėžinių matmenų TRANSKRIBUOTOJAS. Skaitai TIK užrašytus "
    "matmenis (dimension strings — skaičiai prie matavimo linijų, pvz. 4500, 12 600, 3,40). "
    "NIEKADA nevertini matmenų iš akies — jei skaičius neužrašytas, grąžini null. "
    "Grąžink TIK JSON, be markdown fences."
)


def _user_text(rooms: list[dict]) -> str:
    lines = ["Aukšto plano patalpos (iš eksplikacijos):"]
    for r in rooms:
        lines.append(f"  {r.get('nr')} {r.get('pavadinimas')}  ({r.get('plotas_m2')} m²)")
    lines.append("""
Užduotis: kiekvienai patalpai surask jos UŽRAŠYTUS matmenis (plotis × ilgis) iš
dimension strings ant plano. Matmenys mm (pvz. 4500) arba m (pvz. 4,50 — konvertuok į mm).
TIK perskaityti skaičiai — ne įvertinti. Jei patalpos matmenų neužrašyta — null.

Output JSON:
{
  "patalpos": [
    {"nr": "101", "plotis_mm": 4500 | null, "ilgis_mm": 3000 | null,
     "perskaityti_stringai": ["4500", "3000"]}
  ],
  "visi_dimension_strings": ["4500", "3000", "12600", ...],
  "pastabos": "trumpai — kur matmenys užrašyti, kur ne"
}""")
    return "\n".join(lines)


def _render_page(dpi: int):
    from pdf2image import convert_from_bytes
    return convert_from_bytes(PDF.read_bytes(), dpi=dpi,
                              first_page=FLOOR_PAGE, last_page=FLOOR_PAGE)[0]


def _img_b64(img, max_dim: int | None = None) -> str:
    if max_dim and max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _tiles(img, n=2, overlap=0.12):
    """Cut into n×n overlapping tiles."""
    W, H = img.size
    tw, th = W / n, H / n
    out = []
    for i in range(n):
        for j in range(n):
            x0 = max(0, int(i * tw - overlap * tw))
            y0 = max(0, int(j * th - overlap * th))
            x1 = min(W, int((i + 1) * tw + overlap * tw))
            y1 = min(H, int((j + 1) * th + overlap * th))
            out.append(img.crop((x0, y0, x1, y1)))
    return out


def _call(client, content) -> dict:
    resp = client.messages.create(
        model=MODEL, max_tokens=8192,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.content[0].text
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    out = json.loads(m.group(0)) if m else {"_error": "no JSON", "_raw": raw[:500]}
    u = resp.usage
    out["_meta"] = {"in": u.input_tokens, "out": u.output_tokens}
    return out


def probe() -> None:
    import anthropic
    client = anthropic.Anthropic()
    rooms = json.load(open(CACHED))["patalpos"]
    rl = [{"nr": r.get("nr"), "pavadinimas": r.get("pavadinimas"),
           "plotas_m2": r.get("plotas_m2")} for r in rooms]
    utext = _user_text(rl)

    # PROBE A — full page, pipeline-style delivery (≤2000px)
    print("PROBE A: full page ≤2000px ...", flush=True)
    img = _render_page(dpi=200)
    a = _call(client, [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": _img_b64(img, max_dim=2000)}},
        {"type": "text", "text": utext},
    ])
    (OUT / "exp2_probeA_fullpage.json").write_text(json.dumps(a, ensure_ascii=False, indent=2))
    print(f"  strings found: {len(a.get('visi_dimension_strings') or [])} · "
          f"tokens {a['_meta']}", flush=True)

    # PROBE B — 300 DPI, 4 overlapping tiles (resolution-budget lever)
    print("PROBE B: 300 DPI × 4 overlapping tiles ...", flush=True)
    img_hi = _render_page(dpi=300)
    print(f"  page at 300dpi: {img_hi.size}", flush=True)
    content = []
    for k, t in enumerate(_tiles(img_hi, n=2), 1):
        content.append({"type": "text", "text": f"[Tile {k}/4 — persidengiančios to paties plano dalys]"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                    "data": _img_b64(t, max_dim=1500)}})
    content.append({"type": "text", "text": utext})
    b = _call(client, content)
    (OUT / "exp2_probeB_tiled.json").write_text(json.dumps(b, ensure_ascii=False, indent=2))
    print(f"  strings found: {len(b.get('visi_dimension_strings') or [])} · "
          f"tokens {b['_meta']}", flush=True)


def analyze() -> None:
    from extractor.universal_rules import calc_room_quantities
    cached = json.load(open(CACHED))
    rooms = cached["patalpos"]

    def walls_total(rs):
        return round(sum(float(calc_room_quantities(r).get("walls_paintable_m2") or 0)
                         for r in rs), 2)

    geo_walls = walls_total(rooms)

    results = {"geometry_lane": {"walls_paint": geo_walls,
                                 "err_pct": round((geo_walls - TRUTH_WALLS) / TRUTH_WALLS * 100, 1)}}

    for label, fname in [("A_fullpage", "exp2_probeA_fullpage.json"),
                         ("B_tiled", "exp2_probeB_tiled.json")]:
        p = OUT / fname
        if not p.exists():
            continue
        probe_res = json.load(open(p))
        by_nr = {str(x.get("nr")): x for x in probe_res.get("patalpos") or []}
        covered, swapped = 0, []
        for r in rooms:
            t = by_nr.get(str(r.get("nr")))
            r2 = dict(r)
            if t and t.get("plotis_mm") and t.get("ilgis_mm"):
                covered += 1
                r2["perimetras_m"] = round(2 * (t["plotis_mm"] + t["ilgis_mm"]) / 1000, 2)
                r2["_perim_lane"] = "text"
            swapped.append(r2)
        text_walls = walls_total(swapped)
        results[f"text_lane_{label}"] = {
            "rooms_with_text_dims": f"{covered}/{len(rooms)}",
            "n_strings_transcribed": len(probe_res.get("visi_dimension_strings") or []),
            "walls_paint_textperims": text_walls,
            "err_pct": round((text_walls - TRUTH_WALLS) / TRUTH_WALLS * 100, 1),
            "per_room": [
                {"nr": r.get("nr"), "name": r.get("pavadinimas"),
                 "perim_geo": rooms[i].get("perimetras_m"),
                 "perim_text": r.get("perimetras_m") if r.get("_perim_lane") == "text" else None}
                for i, r in enumerate(swapped)],
        }

    # Text-anchored quantities we already know
    ceil = round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2)
    results["text_lane_floor_ceiling"] = {
        "ceiling_from_eksplikacija": ceil,
        "err_pct": round((ceil - TRUTH_CEIL) / TRUTH_CEIL * 100, 2),
    }
    out_p = OUT / "exp2_results.json"
    out_p.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    {"probe": probe, "analyze": analyze}[sys.argv[1]]()
