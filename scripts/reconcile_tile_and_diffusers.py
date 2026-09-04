#!/usr/bin/env python3
"""Reconcile WALL-TILE m² and DIFŪZORIŲ vnt against the contractor's own lines.

WHY (2026-07-29). Two quantities on Objektas A were flagged as gaps, and the
honest answer differs for each — so both need a number, not a claim:

  · WALL TILE. The contractor splits tiling by tile FORMAT (120×60 / 120×120 /
    90×90), we split it by LOCATION (vonios / kitų sienų / grindų), so only the
    aggregate is comparable. His notes document wall tile for two rooms only
    (107 = 32.73 m², 111 = 28.80 m²), which is why truth.json marks
    `plyteles_sienos_total_m2` confidence=incomplete. Comparing our TOTAL to
    that partial number is what produced both the "we are 37% over" and the
    "we are 32% under" readings at different times. This script prints the
    per-room split so the aggregate can be read against the right baseline.

  · DIFŪZORIAI. He bills 15 montavimas + 21 apdirbimas — two numbers that
    disagree with each other, so no single symbol count reproduces both. The
    17-page project draws none: the word occurs once, in note 3 of the
    apšvietimo plan ("...dėl difuzorių vietos ir formos parinkimo..."), i.e.
    their positions are still to be agreed, and no sheet's legend defines a
    diffuser glyph. His numbers come from the vėdinimo dalis, which is not in
    this bundle.

Zero API spend: replays the saved extract through the same deterministic tail
`eval_harness --rescore --recompute` uses, with the two 2026-07-29 gates
toggled OFF and ON, so before/after is measured on one code tree.

Usage:
    ./venv/bin/python scripts/reconcile_tile_and_diffusers.py            # objektas_a
    ./venv/bin/python scripts/reconcile_tile_and_diffusers.py --all
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

WALL_TILE_RX = re.compile(r"plytel\w*\s+klijavimas.*sien|sienų plytelių klijavimas"
                          r"|didžiaformač", re.I)
FLOOR_TILE_RX = re.compile(r"grindų plytelių klijavimas", re.I)
DIFFUSER_RX = re.compile(r"difūzor|difuzor", re.I)
VENT_SKYRIUS = "Ventiliacijos darbai"

# Per-room wall tile the contractor documented verbatim
# (docs/superpowers/fixtures/2026-05-26-objektas-a/contractor-notes-verbatim.md
# §Plytelės). Only these two rooms are documented — the rest of his wall-tile
# universe sits inside mixed-format lines.
OBJEKTAS_A_DOCUMENTED_WALL_TILE = {"107": 32.73, "111": 28.80}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("\n", " ")).strip()


def _contractor(slug: str) -> list[dict]:
    p = REPO / "ground_truth" / slug / "contractor_samata_parsed.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("line_items") or []


def _run(slug: str, gates_on: bool) -> dict:
    """The deterministic tail with the 2026-07-29 gates on or off."""
    import eval_harness as EH
    from extractor import symbol_legend as SL
    from extractor import universal_rules as UR

    real_no_tile, real_anchor = UR.elevation_says_no_tile, SL.diffuser_count_is_anchored
    if not gates_on:
        UR.elevation_says_no_tile = lambda room: False
        SL.diffuser_count_is_anchored = lambda parsed: True
    try:
        parsed = json.loads(
            (REPO / "ground_truth" / slug / "ai_extract.json").read_text("utf-8"))
        return EH._rerun_deterministic_tail(copy.deepcopy(parsed), slug)
    finally:
        UR.elevation_says_no_tile, SL.diffuser_count_is_anchored = real_no_tile, real_anchor


def _sum_lines(parsed: dict, rx: re.Pattern) -> list[tuple[str, object]]:
    return [(_norm(p.get("aprasymas")), p.get("kiekis"))
            for p in (parsed.get("pozicijos") or [])
            if rx.search(_norm(p.get("aprasymas")))]


def report(slug: str) -> None:
    print(f"\n{'=' * 92}\n{slug}\n{'=' * 92}")
    lines = _contractor(slug)
    if not lines:
        print("  nėra įkainuotos sąmatos — praleista")
        return

    # ── His side ────────────────────────────────────────────────────────────
    tile_sec = [it for it in lines
                if "plytel" in _norm(it.get("section")).lower()
                and it.get("quantity") is not None]
    print("\nRANGOVAS — plytelių skyrius (jis skirsto pagal FORMATĄ):")
    for it in tile_sec:
        if re.search(r"klijavimas|didžiaformač", _norm(it.get("name")), re.I):
            print(f"  {str(it.get('nr')):>3}  {_norm(it.get('name'))[:64]:<64} "
                  f"{it.get('quantity'):>8} {it.get('unit')}")
    dif = [it for it in lines if DIFFUSER_RX.search(_norm(it.get("name")))
           and it.get("quantity") is not None]
    print("\nRANGOVAS — difūzoriai:")
    for it in dif:
        print(f"  {str(it.get('nr')):>3}  {_norm(it.get('name'))[:64]:<64} "
              f"{it.get('quantity'):>8} {it.get('unit')}")
    if not dif:
        print("       — nė vienos eilutės —")

    before, after = _run(slug, False), _run(slug, True)

    # ── Per-room wall tile ──────────────────────────────────────────────────
    print("\nMŪSŲ — plytelės sienose pagal patalpas (m²):")
    print(f"  {'nr':>4}  {'patalpa':<22} {'prieš':>8} {'po':>8}  "
          f"{'šaltinis (po)':<16} rangovas")
    b_rooms = {r.get("nr"): r for r in (before.get("patalpos") or [])}
    tot_b = tot_a = 0.0
    for r in after.get("patalpos") or []:
        nr = r.get("nr")
        a = float(r.get("plyteles_sienos_m2") or 0)
        b = float((b_rooms.get(nr) or {}).get("plyteles_sienos_m2") or 0)
        tot_a, tot_b = tot_a + a, tot_b + b
        if a == 0 and b == 0:
            continue
        truth = OBJEKTAS_A_DOCUMENTED_WALL_TILE.get(nr) if slug == "objektas_a" else None
        print(f"  {str(nr):>4}  {_norm(r.get('pavadinimas'))[:22]:<22} "
              f"{b:>8.2f} {a:>8.2f}  {str(r.get('_tile_read_source')):<16} "
              f"{('%.2f' % truth) if truth else '—'}")
    print(f"  {'':>4}  {'VISO':<22} {tot_b:>8.2f} {tot_a:>8.2f}")

    if slug == "objektas_a":
        doc = sum(OBJEKTAS_A_DOCUMENTED_WALL_TILE.values())
        ours_doc_b = sum(float((b_rooms.get(k) or {}).get("plyteles_sienos_m2") or 0)
                         for k in OBJEKTAS_A_DOCUMENTED_WALL_TILE)
        ours_doc_a = sum(float(r.get("plyteles_sienos_m2") or 0)
                         for r in after["patalpos"]
                         if r.get("nr") in OBJEKTAS_A_DOCUMENTED_WALL_TILE)
        print(f"\n  Dokumentuotos patalpos (107+111) — rangovas {doc:.2f} m²:")
        print(f"    prieš {ours_doc_b:>7.2f} m²  ({(ours_doc_b - doc) / doc * 100:+.1f}%)")
        print(f"    po    {ours_doc_a:>7.2f} m²  ({(ours_doc_a - doc) / doc * 100:+.1f}%)")
        # 24 (28.80, wall) + 25-wall part (32.73) + 27 (4.48) + 28 (8.70)
        universe = 28.80 + 32.73 + 4.48 + 8.70
        print(f"  Visas jo sienų plytelių rinkinys (24 + 25sienos + 27 + 28) "
              f"= {universe:.2f} m²:")
        print(f"    prieš {tot_b:>7.2f} m²  ({(tot_b - universe) / universe * 100:+.1f}%)")
        print(f"    po    {tot_a:>7.2f} m²  ({(tot_a - universe) / universe * 100:+.1f}%)")

    # ── Emitted lines ───────────────────────────────────────────────────────
    for label, rx in (("SIENŲ plytelių klijavimas", WALL_TILE_RX),
                      ("GRINDŲ plytelių klijavimas", FLOOR_TILE_RX),
                      ("DIFŪZORIAI", DIFFUSER_RX)):
        b, a = _sum_lines(before, rx), _sum_lines(after, rx)
        if not b and not a:
            continue
        print(f"\nMŪSŲ eilutės — {label}:")
        keys = sorted({k for k, _ in b} | {k for k, _ in a})
        bd, ad = dict(b), dict(a)
        for k in keys:
            mark = "  " if bd.get(k, "∅") == ad.get(k, "∅") else "→ "
            print(f"  {mark}{k[:62]:<62} {str(bd.get(k, '—')):>8} → {str(ad.get(k, '—')):>8}")

    vb = [(_norm(p.get("aprasymas")), p.get("kiekis"))
          for p in before.get("pozicijos") or [] if p.get("skyrius") == VENT_SKYRIUS]
    va = [(_norm(p.get("aprasymas")), p.get("kiekis"))
          for p in after.get("pozicijos") or [] if p.get("skyrius") == VENT_SKYRIUS]
    if vb or va:
        print("\nMŪSŲ eilutės — Ventiliacijos darbai (išvestos iš difūzorių skaičiaus):")
        for k, v in vb:
            print(f"  → {k[:62]:<62} {str(v):>8} → "
                  f"{str(dict(va).get(k, '—')):>8}")

    leg = (after.get("_symbol_legend") or {}).get("difuzoriai") or {}
    print(f"\n  Brėžinio legendos patikra: difuzoriaus žymuo apibrėžtas = "
          f"{leg.get('defined')}  (puslapiai {leg.get('pages') or '—'})")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv:
        import yaml
        reg = yaml.safe_load((REPO / "ground_truth" / "registry.yaml").read_text("utf-8"))
        slugs = [p["slug"] for p in reg["projects"]
                 if (REPO / "ground_truth" / p["slug"] / "ai_extract.json").exists()]
    else:
        slugs = args or ["objektas_a"]
    for s in slugs:
        report(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
