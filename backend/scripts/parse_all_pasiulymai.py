"""Ištraukia VISAS 5 rangovo sąmatų eilutes per pdfplumber lentelių parser'į.

Output: backend/training-data/parsed_pasiulymai.json
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "training-data"
OUT = DATA / "parsed_pasiulymai.json"


def _to_float(s) -> float | None:
    if s is None:
        return None
    s = str(s).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_pasiulymas(pdf_path: Path) -> dict:
    skyriai: list[dict] = []
    cur_skyrius: dict | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    # Padding nones
                    cells = [(c.strip() if isinstance(c, str) else c) for c in row]

                    c0 = (cells[0] or "") if len(cells) > 0 else ""
                    c1 = (cells[1] or "") if len(cells) > 1 else ""
                    c2 = (cells[2] or "") if len(cells) > 2 else ""
                    c3 = (cells[3] or "") if len(cells) > 3 else ""

                    # Skyrius — first col "Skyrius"
                    if c0 == "Skyrius":
                        cur_skyrius = {"pavadinimas": c1.strip(), "eilutes": []}
                        skyriai.append(cur_skyrius)
                        continue

                    # "Viso už skyrių" eilutė — praleidžiam
                    if "viso už" in c1.lower() or "viso bendrai" in str(c1 or "").lower():
                        continue

                    # Header row?
                    if c0.lower() in ("eil. nr.", "eil. nr", "eil.nr.", "eil. nr."):
                        continue
                    if c0 in (None, "") and "vnt" in str(c1 or "").lower():
                        continue

                    # Eilutė su nr — pirmas stulpelis turi būti skaičius
                    nr = None
                    try:
                        nr = int(c0)
                    except (ValueError, TypeError):
                        nr = None

                    if nr is None:
                        continue

                    aprasymas = (c1 or "").replace("\n", " ").strip()
                    aprasymas = re.sub(r"\s+", " ", aprasymas)

                    vnt = (c2 or "").lower().rstrip(".")
                    kiekis = _to_float(c3)

                    if not aprasymas or kiekis is None:
                        continue

                    # Kainos: stulpelis 4 = darbo vnt, 5 = darbo viso,
                    # 6 = medziagu vnt, 7 = medziagu viso
                    c4 = cells[4] if len(cells) > 4 else None
                    c5 = cells[5] if len(cells) > 5 else None
                    c6 = cells[6] if len(cells) > 6 else None
                    c7 = cells[7] if len(cells) > 7 else None
                    darbo_kaina_vnt = _to_float(c4)
                    darbo_kaina_viso = _to_float(c5)
                    medz_kaina_vnt = _to_float(c6)
                    medz_kaina_viso = _to_float(c7)

                    if cur_skyrius is None:
                        cur_skyrius = {"pavadinimas": "Be skyriaus", "eilutes": []}
                        skyriai.append(cur_skyrius)

                    cur_skyrius["eilutes"].append({
                        "nr": nr,
                        "aprasymas": aprasymas,
                        "vnt": vnt,
                        "kiekis": kiekis,
                        "darbo_kaina_vnt": darbo_kaina_vnt,
                        "darbo_kaina_viso": darbo_kaina_viso,
                        "medz_kaina_vnt": medz_kaina_vnt,
                        "medz_kaina_viso": medz_kaina_viso,
                        "viso_be_pvm": (
                            (darbo_kaina_viso or 0) + (medz_kaina_viso or 0)
                            if (darbo_kaina_viso or medz_kaina_viso) else None
                        ),
                    })

    return {"skyriai": skyriai}


def main():
    DATA.mkdir(exist_ok=True)
    out: dict[str, dict] = {}
    for i in range(1, 6):
        pdf = DATA / f"projektas_{i}" / f"projektas_{i}_pasiulymas.pdf"
        if not pdf.exists():
            print(f"[skip] {pdf} nerastas")
            continue
        print(f"[parse] P{i} ← {pdf.name}")
        parsed = parse_pasiulymas(pdf)
        out[f"P{i}"] = parsed
        n = sum(len(s["eilutes"]) for s in parsed["skyriai"])
        print(f"        → {len(parsed['skyriai'])} skyriai, {n} eilutės")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] saved → {OUT}")


if __name__ == "__main__":
    main()
