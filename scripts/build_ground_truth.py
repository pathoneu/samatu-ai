"""build_ground_truth — the keystone, built as a byproduct of the correction loop.

Every human correction in the viewer persists into the canonical project blob
(localStorage → PUT /api/projects → SQLite). This reads that blob across all
projects and extracts the human-confirmed signals into a ground-truth corpus
the eval harness can score against — WITHOUT a separate 1-hour interactive flow.

Two signals (both already in the blob):
  • POLYGON truth  — rooms the user accepted/corrected (polygon_source ∈
    {corrected, manual}) → a wall-following polygon + plotas_m2 confirmed by a
    human (the auto_floodfill ones are AI-proposed, not yet confirmed).
  • QUANTITY truth — rows the user edited or verified (manual_override /
    user_verified) → an (ai_value, human_value) pair → per-class bias bands.

A third signal on request (togal-v2 W11, `--with-corrections`): the `corrections`
table — every accept, reject or edit a person made of an AI result, one row each
(source eilute_teisinga, eilute_kiekis, patalpa_patvirtinta, klausimas_*, konturas,
simbolis, pokalbis_*, prielaidos) — added under a `corrections` key; the other keys
keep their shape.

Run:  python scripts/build_ground_truth.py [--db PATH] [--out corpus.json] [--with-corrections]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "backend" / "data" / "samatu.db"

# Human-confirmed polygon sources (auto_floodfill is AI-proposed, NOT confirmed).
_POLYGON_TRUTH_SOURCES = {"corrected", "manual"}
# Human-confirmed quantity sources.
_QTY_TRUTH_SOURCES = {"manual_override", "user_verified"}

_CLASS_PATTERNS = [
    ("beapvadinėms durims", "durys_beapvadines"),
    ("silikonavimas", "silikonavimas"),
    ("kampų montavimas", "kampai"),
    ("angokrašči", "angokrasciai"),
    ("skylių gręžimas", "skyliu_grezimas"),
    ("glaistymas", "glaistymas_dazymas"),
    ("dažymas", "glaistymas_dazymas"),
    ("plytel", "plyteles"),
    ("grind", "grindys"),
    ("rotband", "rotband"),
]


def _classify(aprasymas: str) -> str:
    label = (aprasymas or "").lower()
    for needle, klass in _CLASS_PATTERNS:
        if needle in label:
            return klass
    return "kita"


def _iter_projects(db_path: Path):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        for row in con.execute("SELECT id, data FROM projects"):
            try:
                yield row["id"], json.loads(row["data"])
            except (json.JSONDecodeError, TypeError):
                continue
    finally:
        con.close()


def _corrections(db_path: Path) -> list[dict]:
    """Every row of the `corrections` table, oldest first, values parsed back from their JSON text.
    An older database without the table gives an empty list."""
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        try:
            rows = con.execute("SELECT * FROM corrections ORDER BY occurred_at, id").fetchall()
        except sqlite3.OperationalError:
            return []
        out = []
        for r in rows:
            d = dict(r)
            for k in ("old_value", "new_value"):
                if d.get(k) is not None:
                    try:
                        d[k] = json.loads(d[k])
                    except (json.JSONDecodeError, TypeError):
                        pass
            out.append(d)
        return out
    finally:
        con.close()


def build_corpus(db_path: Path, with_corrections: bool = False) -> dict:
    polygon_truth: list[dict] = []
    quantity_truth: list[dict] = []
    for pid, proj in _iter_projects(db_path):
        for r in proj.get("patalpos") or []:
            if r.get("polygon_source") in _POLYGON_TRUTH_SOURCES and r.get("polygon_pct"):
                polygon_truth.append({
                    "project_id": pid, "room_nr": str(r.get("nr")),
                    "plotas_m2": r.get("plotas_m2"),
                    "polygon_source": r.get("polygon_source"),
                    "n_vertices": len(r.get("polygon_pct") or []),
                    "polygon_pct": r.get("polygon_pct"),
                })
        rows = proj.get("darbu_sarasas") or proj.get("pozicijos") or []
        for it in rows:
            src = it.get("quantity_source")
            verified = bool(it.get("user_verified_at"))
            if src in _QTY_TRUTH_SOURCES or verified:
                ai = it.get("ai_kiekis_original")
                human = it.get("kiekis")
                rel = None
                if isinstance(ai, (int, float)) and isinstance(human, (int, float)) and human:
                    rel = (ai - human) / human
                quantity_truth.append({
                    "project_id": pid, "aprasymas": it.get("aprasymas"),
                    "quantity_class": _classify(it.get("aprasymas")),
                    "ai_value": ai, "human_value": human, "rel_error": rel,
                    "source": "verified" if (verified and src not in _QTY_TRUTH_SOURCES) else src,
                })

    # Per-class bias bands from the (ai, human) pairs that actually differ.
    by_class: dict[str, list[float]] = {}
    for q in quantity_truth:
        if isinstance(q["rel_error"], (int, float)):
            by_class.setdefault(q["quantity_class"], []).append(q["rel_error"])
    class_bias = {
        k: {"n": len(v), "mean_rel_error": round(sum(v) / len(v), 4),
            "min": round(min(v), 4), "max": round(max(v), 4)}
        for k, v in by_class.items()
    }
    corpus = {
        "polygon_truth": polygon_truth,
        "quantity_truth": quantity_truth,
        "class_bias": class_bias,
        "stats": {
            "polygon_confirmed": len(polygon_truth),
            "quantity_confirmed": len(quantity_truth),
            "classes": sorted(class_bias),
        },
    }
    if with_corrections:
        corpus["corrections"] = _corrections(db_path)
        by_source: dict[str, int] = {}
        for c in corpus["corrections"]:
            by_source[str(c.get("source") or "")] = by_source.get(str(c.get("source") or ""), 0) + 1
        corpus["stats"]["corrections"] = len(corpus["corrections"])
        corpus["stats"]["corrections_by_source"] = dict(sorted(by_source.items()))
    return corpus


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--out", default=None)
    ap.add_argument("--with-corrections", action="store_true",
                    help="add the corrections table (every accept/reject/edit) under a `corrections` key")
    args = ap.parse_args()
    corpus = build_corpus(Path(args.db), with_corrections=args.with_corrections)
    if args.out:
        Path(args.out).write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    s = corpus["stats"]
    print(f"ground truth: {s['polygon_confirmed']} confirmed polygons, "
          f"{s['quantity_confirmed']} confirmed quantities; classes: {s['classes']}"
          + (f"; {s['corrections']} corrections {s['corrections_by_source']}" if "corrections" in s else ""))


if __name__ == "__main__":
    main()
