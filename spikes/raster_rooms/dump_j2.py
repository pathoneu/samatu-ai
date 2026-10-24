"""Vector truth for the contractor scan objektas_j3: the app's geometry lane on its vector original
objektas_j2 (sheet 1). Run with the PROJECT venv (imports backend/ read-only):

  /Users/ignasgaldikas/samatu-ai/venv/bin/python spikes/raster_rooms/dump_j2.py <j2.pdf> spikes/raster_rooms/out/lane_objektas_j2.json

There is no cached extraction for j2, so the room list is the sheet's own eksplikacija (room nr + m²
as printed on sheet 1 — the designer's numbers). Same output shape as spikes/sam2/dump_lane.py.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "backend"))

from extractor import geometry_lane as gl  # noqa: E402
from extractor.vector_rooms import outline_at  # noqa: E402

# eksplikacija of sheet 1 (nr -> m²), as printed on the sheet
TABLE = {"1": 3.14, "2": 5.47, "3": 35.86, "4": 15.27, "5": 3.99, "6": 3.69, "7": 11.42, "8": 5.57, "9": 12.13}
KEEP = ("nr", "plotas_m2", "puslapio_nr", "polygon_pct", "polygon_source", "_konturas", "_konturo_priezastis",
        "polygon_holes_pct", "_atvira_erdve", "_vieta")


def main(pdf_path: str, out: str) -> None:
    pdf = Path(pdf_path).read_bytes()
    parsed = {"patalpos": [{"nr": nr, "pavadinimas": f"Patalpa {nr}", "plotas_m2": a, "plotas_saltinis": "eksplikacija",
                            "puslapio_nr": 1} for nr, a in TABLE.items()]}
    res = gl.apply_geometry(parsed, pdf)
    geo = (parsed.get("_meta") or {}).get("geometrija") or {}
    # The lane is blind on this sheet (plan §9: badges 11,7 pt > the 6,5 pt cap, no scale on sheet 1).
    # Seats: the printed room numbers in their squares (single digits, 9-14 pt tall, inside the plan
    # frame) from the text layer. Scale: the stated „M 1:40" (0,014111 m/pt) is WRONG for this A3 print —
    # outlines came out 18-31 % under the table. Matched by hand to the dimension strings on the wall faces
    # (room 9: 415+2000+785 = 3200 mm over a 203,1 pt face, 3790 mm over 240,3 pt; room 7: 3570 mm over
    # 226,4 pt) -> 0,015756 / 0,015772 / 0,015770 m/pt; mean 0,01576 m/pt (≈ 1:44,7, fit-to-page).
    import pdfplumber
    with pdfplumber.open(pdf_path) as doc:
        pg = doc.pages[0]
        W, H = float(pg.width), float(pg.height)
        seats = {w["text"]: ((w["x0"] + w["x1"]) / 2 / W, (w["top"] + w["bottom"]) / 2 / H)
                 for w in pg.extract_words() if w["text"] in TABLE and 9 <= w["bottom"] - w["top"] <= 14 and w["x1"] < 950}
    m_per_pt = 0.01576
    geo.setdefault("masteliai", {})
    geo["masteliai"] = {**(geo["masteliai"] or {}), "1": {"m_per_pt": round(m_per_pt, 6), "mastelis": 45, "saltinis": "dimension strings 3200/3790/3570 on wall faces (stated M 1:40 is a pre-print scale)"}}
    rooms = []
    for r in parsed["patalpos"]:
        d = {k: r.get(k) for k in KEEP}
        d["table_m2"] = TABLE[str(r["nr"])]
        if not r.get("_vieta") and str(r["nr"]) in seats:
            cx, cy = seats[str(r["nr"])]
            d["_vieta"] = {"page": 1, "cx": cx, "cy": cy, "saltinis": "zenkliukas (spike: text layer)"}
        v = d.get("_vieta") or {}
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
    Path(out).write_text(json.dumps({"slug": "objektas_j2", "pdf_path": pdf_path, "masteliai": geo.get("masteliai"),
                                     "konturai": res.get("konturai"), "konturu_priezastys": res.get("konturu_priezastys"),
                                     "rooms": rooms}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("rooms", len(rooms), "konturai", res.get("konturai"), "masteliai", geo.get("masteliai"))
    for d in rooms:
        print(d["nr"], d["table_m2"], d.get("_vieta"), (d.get("_konturas") or {}).get("plotas_m2"),
              (d.get("outline_at") or {}).get("status"), (d.get("outline_at") or {}).get("plotas_m2"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
