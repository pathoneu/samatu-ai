"""Run the app's geometry lane in-process (main checkout venv) and dump, per room, what the
SAM spike needs: table area, the lane's vector outline (page fractions + its m²), the room
label position, and every sheet's scale. Run with the PROJECT venv, not the spike venv:

  /Users/ignasgaldikas/samatu-ai/venv/bin/python spikes/sam2/dump_lane.py objektas_h spikes/sam2/out/lane_objektas_h.json
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
BACKEND = HERE.parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
MAIN = Path("/Users/ignasgaldikas/samatu-ai")

from extractor import geometry_lane as gl  # noqa: E402
from extractor.vector_rooms import outline_at  # noqa: E402

KEEP = ("nr", "pavadinimas", "plotas_m2", "plotas_saltinis", "puslapio_nr", "polygon_pct",
        "polygon_source", "_konturas", "_konturo_priezastis", "_plotas_uzrasas", "bbox_pct",
        "polygon_holes_pct", "_atvira_erdve", "_vieta")


def main(slug: str, out: str) -> None:
    folder = MAIN / "ground_truth" / slug
    truth = json.loads((folder / "truth.json").read_text(encoding="utf-8"))
    pdf = (MAIN / truth["pdf_path"]).read_bytes()
    parsed = copy.deepcopy(json.loads((folder / "ai_extract.json").read_text(encoding="utf-8")))
    table = {str(r["nr"]): (r.get("plotas_m2"), r.get("plotas_saltinis")) for r in parsed["patalpos"]}
    res = gl.apply_geometry(parsed, pdf)
    geo = (parsed.get("_meta") or {}).get("geometrija") or {}
    rooms = []
    for r in parsed["patalpos"]:
        d = {k: r.get(k) for k in KEEP}
        d["table_m2"], d["table_source"] = table.get(str(r["nr"]), (None, None))
        # the one-click vector path (api/room_outline outline-at) at the room's seat, no neighbours passed
        v = r.get("_vieta") or {}
        sc = ((geo.get("masteliai") or {}).get(str(v.get("page"))) or {}).get("m_per_pt")
        if v.get("page") and sc:
            t = time.time()
            try:
                oa = outline_at(pdf, int(v["page"]), float(v["cx"]), float(v["cy"]), d["table_m2"], float(sc))
            except Exception as exc:  # noqa: BLE001
                oa = {"status": "error", "error": repr(exc)}
            oa["ms"] = round((time.time() - t) * 1000)
            d["outline_at"] = oa
        rooms.append(d)
    Path(out).write_text(json.dumps({
        "slug": slug, "pdf_path": str(MAIN / truth["pdf_path"]),
        "masteliai": geo.get("masteliai"), "sutapdinimas": res.get("sutapdinimas"),
        "grupes": res.get("grupes"), "konturai": res.get("konturai"),
        "konturu_priezastys": res.get("konturu_priezastys"), "rooms": rooms,
    }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(slug, "rooms", len(rooms), "konturai", res.get("konturai"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
