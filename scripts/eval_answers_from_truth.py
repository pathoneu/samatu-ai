#!/usr/bin/env python3
"""Write `ground_truth/<slug>/answers.json` — what a person would type when the app asks —
from the truth files ONLY (v4 eval re-base, 2026-10-25).

Sources read (and nothing else):
  * `contractor_samata_parsed.json` — the contractor's own row labels (a height he states in a
    label, e.g. „karkasą 2,8m aukštis“, is his answer to „Kokio aukščio lubos?“),
  * `truth.json` — `notes_for_evaluator` and the `source` strings of `gt_totals`.
NEVER read: `ai_extract.json`, `truth.json › gt_dimensions` (its heights are Vision-derived, the
guess the instrument must not feed back), `reading_truth.json` (doors and windows, not a number
the person types).

Rule for the project height: take the statements of a height in 2,0–3,0 m (the standard-storey
heights). When they all agree the project value is that number; when none exists the project
gets no answer (the app would stay blank too — a real gap); when they disagree nothing is
guessed. Heights above 3,0 m are recorded in `_pastabos` for the human reader but never applied:
the sąmata says WHICH ceilings are high only through areas, and mapping an area to rooms would
be copying the answer key.

Usage (from the repo root):
    python scripts/eval_answers_from_truth.py            # write the six corpus projects
    python scripts/eval_answers_from_truth.py --print    # inventory only, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GT = ROOT / "ground_truth"
CORPUS = ("objektas_a", "objektas_b", "objektas_c", "objektas_d", "objektas_g", "objektas_h")

# „2,8m aukštis“, „3,4 m aukščio“, „aukštis 2,8 m“, „H = 2,8 m“ — a metre figure next to the word.
_HEIGHT_RES = (
    re.compile(r"(\d[.,]\d{1,2})\s*m\s*aukšt", re.I),
    re.compile(r"aukšt\w*\s*[:=]?\s*(\d[.,]\d{1,2})\s*m\b", re.I),
)
LOW_MIN, LOW_MAX = 2.0, 3.0


def _heights_in(text: str) -> list[float]:
    out: list[float] = []
    for rx in _HEIGHT_RES:
        for m in rx.finditer(text or ""):
            try:
                out.append(round(float(m.group(1).replace(",", ".")), 2))
            except ValueError:
                pass
    return out


def _statements(slug: str) -> list[dict]:
    """Every height the truth files state, with where it was stated."""
    found: list[dict] = []
    d = GT / slug
    sam = d / "contractor_samata_parsed.json"
    if sam.exists():
        for it in json.loads(sam.read_text(encoding="utf-8")).get("line_items") or []:
            for h in _heights_in(str(it.get("name") or "")):
                found.append({"m": h, "kur": f"sąmatos eilutė nr. {it.get('nr')}"})
    tr = d / "truth.json"
    if tr.exists():
        t = json.loads(tr.read_text(encoding="utf-8"))
        for h in _heights_in(str(t.get("notes_for_evaluator") or "")):
            found.append({"m": h, "kur": "truth.json › notes_for_evaluator"})
        for key, v in (t.get("gt_totals") or {}).items():
            if isinstance(v, dict):
                for h in _heights_in(str(v.get("source") or "") + " " + str(v.get("notes") or "")):
                    found.append({"m": h, "kur": f"truth.json › gt_totals › {key}"})
    return found


def build_answers(slug: str) -> dict:
    stated = _statements(slug)
    low = sorted({s["m"] for s in stated if LOW_MIN <= s["m"] <= LOW_MAX})
    high = sorted({s["m"] for s in stated if s["m"] > LOW_MAX})
    project_h = low[0] if len(low) == 1 else None
    notes = []
    if not stated:
        notes.append("Truth files state no ceiling height — no answer; rows that wait for it stay blank (real gap).")
    if len(low) > 1:
        notes.append(f"Statements disagree ({low}) — nothing guessed.")
    if high:
        notes.append(f"Higher ceilings stated ({high} m) without rooms — recorded, not applied.")
    return {
        "slug": slug,
        "kas": "Ką žmogus įrašytų, kai programa klausia — tik iš teisybės failų (ne iš ai_extract.json).",
        "lubu_aukstis_m": project_h,
        "lubu_auksciai": {},
        "saltiniai": [s for s in stated if (s["m"] in low and project_h is not None)],
        "_pastabos": notes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--print", action="store_true", help="show the inventory, write nothing")
    ap.add_argument("slugs", nargs="*", default=list(CORPUS))
    args = ap.parse_args()
    for slug in args.slugs:
        if not (GT / slug).is_dir():
            print(f"{slug}: no ground_truth folder", file=sys.stderr)
            continue
        ans = build_answers(slug)
        print(f"{slug}: lubu_aukstis_m={ans['lubu_aukstis_m']}  {ans['_pastabos']}")
        if not args.print:
            (GT / slug / "answers.json").write_text(
                json.dumps(ans, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
