"""
GAP analizė — kurios pozicijos per visus 5 Rangovo sąmatų projektus,
koks kiekio range, ar V8 grąžina tą pozicija.

Output: backend/training-data/gap_analysis.md (markdown lentelė)
"""
from __future__ import annotations
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
IN = ROOT / "training-data" / "parsed_pasiulymai.json"
OUT_MD = ROOT / "training-data" / "gap_analysis.md"
OUT_JSON = ROOT / "training-data" / "gap_analysis.json"


def normalize(s: str) -> str:
    """Norm aprašymą: lower, sutrauk tarpus, panaikink LT diakritiką."""
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    # remove accents for grouping
    nfkd = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in nfkd if not unicodedata.combining(c))
    return s


# Manualinis mapping į CANONICAL pavadinimus —
# panašios eilutės, kurios reiškia tą patį, sumetama į vieną grupę.
CANONICAL_PATTERNS: list[tuple[str, list[str]]] = [
    # (canonical_name, [substring patterns])
    ("Sienų lyginimas Rotband", ["sienu lyginimas", "rotband"]),
    ("Sienų/lubų glaistymas/dažymas", ["sienu/ lubu glaistymas", "sienu, lubu glaistymas",
                                         "sienu/lubu glaistymas", "sienu lubu glaistymas"]),
    ("Lubų glaistymas/dažymas (virš 3m)", ["lubu glaistymas/dazymas (virs 3m"]),
    ("Lubų glaistymas/dažymas", ["lubu glaistymas/dazymas", "lubu glaistymas dazymas"]),
    ("Sienų dekoravimas molio tinku", ["molio tinku", "molio tinkas"]),
    ("Sienų tapetavimas", ["tapeta"]),
    ("Stiklo audinio klijavimas", ["stiklo audinio"]),

    # GKP montavimas
    ("GKP montavimas ant lubų (standart)", ["gkp monatavimas ant lubu", "gkp montavimas ant lubu",
                                              "lubu is gkp", "lubu is gipso kartono"]),
    ("GKP montavimas ant lubų (virš 3m)", ["gkp ... virs 3m", "kai aukstis virs 3m"]),
    ("GKP nišų formavimas", ["nisu formavimas is gkp", "nisu is gkp", "nisu iš gkp"]),
    ("GKP pertvaros įrengimas", ["pertvaros irengimas", "pertvarele"]),
    ("GKP dėžučių formavimas", ["dezutes is gkp"]),
    ("GKP angokraščių apdirbimas", ["angokrasciu apdirbimas gkp"]),
    ("Laidų apsiuvimas garaže", ["laidu apsiuvimas"]),

    # Dažymas detalės
    ("Dažymo kampų montavimas", ["dazymo kampu"]),
    ("Durų angų paruošimas (beapvasdinėms)", ["duru angu paruosimas"]),
    ("Paslėptų durų staktų apdirbimas", ["pasleptu duru stakt"]),
    ("Durų varčios dažymas", ["duru varcios dazymas"]),
    ("Angokraščių glaistymas/dažymas", ["angokrasciu glaistymas"]),
    ("Moldingų dažymas", ["moldingu"]),
    ("Šviestuvų apdirbimas (gipsiniai)", ["gipsiniu sviestuvu"]),
    ("Difūzorių apdirbimas", ["difuzori"]),
    ("Revizinių durelių apdirbimas", ["reviziniu dureliu apdirbimas", "revizines dureles"]),
    ("LED nišų glaistymas/dažymas", ["nisu is gkp pasleptam led"]),
    ("LED profilių apdirbimas", ["led ptofili", "led profil"]),

    # Plytelės
    ("Plytelių klijavimas (1200×1200)", ["pliteliu klijavimas ant sienu ir grindu 1200*1200"]),
    ("Plytelių klijavimas (1200×600)", ["1200*600"]),
    ("Plytelių klijavimas standart", ["pliteliu klijavimas"]),
    ("Didžiaformačių plytelių klijavimas", ["didziaformaciu pliteliu"]),
    ("Plytelių pjovimas 45° kampu", ["pliteliu supjovimas 45", "pliteliu pjovimas 45"]),
    ("Lentynų iš plytelių dušo kabinoje", ["lentyneliu is pliteliu"]),
    ("Nuolydžio formavimas dušo kabinoje", ["nuolydzio formavimas"]),
    ("Hidroizoliacijos įrengimas", ["hidroizoliacijos"]),
    ("Skylių gręžimas plytelėse", ["skyliu grezimas pliteles", "skyliu grezimas pliteleje"]),
    ("Kampų silikonavimas", ["kampu silikon"]),
    ("Aliuminio kampo montavimas", ["aliuminio apdailinio kampo", "aliuminio kampas"]),
    ("Plytelių pripjovimas prie trapo", ["pripjovimas prie trapo"]),
    ("Garažo plytelės (medžiagos)", ["garazo pliteles"]),
    ("Išlyginamojo pylimas", ["islyginamojo pylimas", "islyginamojo sluoksnio"]),

    # Grindys
    ("Parketlenčių klijavimas eglutė", ["parketlenciu klijavimas"]),
    ("Parketlenčių klijavimas", ["parketlent"]),
    ("Laminato klojimas", ["laminato"]),
    ("Grindjuosčių montavimas", ["grindjuost"]),

    # Rekuperacija (P1 turi atskirą skyrių)
    ("Rekuperacijos darbai", ["rekuperacij"]),
    ("Ortakių montavimas", ["ortakis", "ortakiai"]),

    # Santechnika
    ("WC rėmo montavimas", ["wc ir bide remo", "wc remo"]),
    ("Maišytuvų montavimas", ["maisytuvo"]),
    ("Klozeto montavimas", ["klozeto"]),
    ("Gyvatuko montavimas", ["gyvatuko"]),
    ("Skalbimo mašinos sifonas", ["skalbimo masinos"]),

    # Kita
    ("Lubų pakabinimas (laiptinėje)", ["lubu is gipso kartono montavimas laiptin"]),
]


def canonicalize(aprasymas: str) -> str:
    n = normalize(aprasymas)
    for canon, patterns in CANONICAL_PATTERNS:
        for p in patterns:
            if p in n:
                return canon
    return aprasymas  # fallback — palieka originalų


def main():
    data = json.loads(IN.read_text(encoding="utf-8"))

    # canon_name → {project: kiekis}
    rows: dict[str, dict[str, list[tuple[str, float, str]]]] = defaultdict(lambda: defaultdict(list))

    for proj, parsed in data.items():
        for skyrius in parsed.get("skyriai", []):
            for eil in skyrius.get("eilutes", []):
                canon = canonicalize(eil["aprasymas"])
                vnt = eil.get("vnt") or "?"
                kiekis = eil.get("kiekis")
                rows[canon][proj].append((eil["aprasymas"], kiekis, vnt))

    # Susortinam: pirmiau tos, kurios pasikartoja daug projektų
    sorted_canons = sorted(rows.keys(), key=lambda c: -len(rows[c]))

    # V8 dabar grąžina šias eilutes (iš main.py v8_overrides):
    V8_KNOWS = {
        "GKP montavimas ant lubų (standart)": "gkp_lubu_standart_m2",
        "GKP montavimas ant lubų (virš 3m)": "gkp_lubu_virs_3m_m2",
        "Sienų/lubų glaistymas/dažymas": "dazymo_plotas_m2",
        "Dažymo kampų montavimas": "kampai_m",
        "Plytelių klijavimas standart": "plyteles_grindys+sienos",
        "Hidroizoliacijos įrengimas": "hidroizoliacijos_vnt",
        "Grindjuosčių montavimas": "grindjuostes_m",
    }

    # Markdown output
    out_lines = ["# Gap Analizė — Rangovo sąmatos vs V8\n",
                 "**Šaltinis:** `training-data/parsed_pasiulymai.json` (5 projektai, ~242 eilutės)\n",
                 "## Per projektus\n"]

    proj_totals = {p: 0 for p in ("P1","P2","P3","P4","P5")}
    for proj, parsed in data.items():
        n = sum(len(s["eilutes"]) for s in parsed["skyriai"])
        proj_totals[proj] = n
    out_lines.append("| Projektas | Eilutės | Skyriai |")
    out_lines.append("|-----------|---------|---------|")
    for proj, n in proj_totals.items():
        ns = len(data.get(proj, {}).get("skyriai", []))
        out_lines.append(f"| {proj} | {n} | {ns} |")

    out_lines.append("\n## Pozicijos — kurios per kiek projektų pasikartoja\n")
    out_lines.append("| Pozicija | P1 | P2 | P3 | P4 | P5 | V8 turi? |")
    out_lines.append("|----------|----|----|----|----|----|----------|")

    for canon in sorted_canons:
        proj_data = rows[canon]
        cells = []
        for p in ("P1","P2","P3","P4","P5"):
            if p in proj_data:
                # paimti SUMĄ jeigu kelios eilutės
                vals = [e[1] for e in proj_data[p] if e[1] is not None]
                vnts = [e[2] for e in proj_data[p]]
                vnt = vnts[0] if vnts else ""
                if vals:
                    s = sum(vals)
                    cells.append(f"{s:.1f} {vnt}")
                else:
                    cells.append("?")
            else:
                cells.append("—")
        v8 = "✅ " + V8_KNOWS[canon] if canon in V8_KNOWS else "❌"
        out_lines.append(f"| {canon} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {v8} |")

    # Detalūs neatpažinti aprašymai (kur canonicalize netinka)
    out_lines.append("\n## Neatpažinti / unikalūs aprašymai (top 30)\n")
    unknown = [(c, rows[c]) for c in sorted_canons if c not in [k for k,_ in CANONICAL_PATTERNS]]
    out_lines.append("| Aprašymas | Projektai |")
    out_lines.append("|-----------|-----------|")
    for canon, proj_data in unknown[:30]:
        proj_str = ", ".join(proj_data.keys())
        out_lines.append(f"| {canon[:80]} | {proj_str} |")

    OUT_MD.write_text("\n".join(out_lines), encoding="utf-8")

    # JSON irgi
    OUT_JSON.write_text(json.dumps({
        "by_canon": {c: {p: rows[c][p] for p in rows[c]} for c in sorted_canons},
        "v8_known": V8_KNOWS,
        "proj_totals": proj_totals,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] {OUT_MD}")
    print(f"[done] {OUT_JSON}")
    print(f"\nUnikalios pozicijos: {len(sorted_canons)}")
    print(f"Atpažintos canonical: {sum(1 for c,_ in CANONICAL_PATTERNS if c in rows)}")
    print(f"V8 jau turi: {sum(1 for c in V8_KNOWS if c in rows)} / {len(V8_KNOWS)}")


if __name__ == "__main__":
    main()
