#!/usr/bin/env python3
"""Reconcile the app's FULL emitted line set against the contractor's sąmata.

WHY (2026-07-29): `reconcile_sanitary_lines.py` proved the point on one family
(mixers). This is the same idea widened to every line the contractor bills, so
"coverage" stops being an impression and becomes a number: of his N priced
lines, how many have a counterpart in our kiekių žiniaraštis, how many of those
counterparts are honesty-CHECKLIST rows the user must still fill, and which
lines we genuinely do not produce at all.

Method — deliberately name-based, not number-based:
  · Zero API spend. Rebuilds `pozicijos[]` from the SAVED extract with today's
    deterministic builder (same tail `eval_harness --rescore --recompute` uses).
  · A CONCEPT maps a contractor line family onto the app line family that does
    the same work. Names differ between estimators; the concept table is where
    that translation is written down and reviewable, instead of being implied
    by a fuzzy string match that silently scores a real miss as a hit.
  · Several contractor lines may map onto ONE app line (he splits tiling by
    format, we aggregate by location) and vice versa. That is reported as
    `aggregated`, never hidden.

A concept with `app=None` is an ADMITTED gap: we know the work exists and we
know we do not produce it.

Usage:
    ./venv/bin/python scripts/reconcile_samata_lines.py            # berzas
    ./venv/bin/python scripts/reconcile_samata_lines.py --all
    ./venv/bin/python scripts/reconcile_samata_lines.py --unmapped # show ours
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))


def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


@dataclass
class Concept:
    key: str
    contractor: re.Pattern
    app: re.Pattern | None = None
    note: str = ""
    # Contractor lines matched / app lines matched — filled in at report time.
    c_rows: list = field(default_factory=list)
    a_rows: list = field(default_factory=list)


# ORDER MATTERS: the first concept whose `contractor` pattern hits wins, so the
# specific variants ("Didžiaformačių plytelių klijavimas") precede the generic
# ones ("plytelių klijavimas").
CONCEPTS: list[Concept] = [
    # ── Gipso kartono montavimas ────────────────────────────────────────────
    # NOTE the dėžutės/nišos variants precede the generic ceiling-GKP and
    # tiling patterns they would otherwise be swallowed by.
    # `\W+` not `\s+`: his line reads `GKP "dėžučių" motavimas` — quote glued to
    # the noun, and "motavimas" is his own typo for montavimas.
    Concept("gkp_dezutes_lubose", _rx(r"dėžuč\w*\W+m\w*tavimas ant lubų"),
            _rx(r"GKP „dėžučių“ montavimas ant lubų"), "checklist"),
    Concept("dezute_ortakiams", _rx(r"dėžut\w*\s+montavimas ortakiams"),
            _rx(r"Dėžutės montavimas ortakiams"), "checklist"),
    Concept("didziaformates", _rx(r"didžiaformač"),
            _rx(r"Didžiaformačių plytelių"),
            "emit'inama tik kai _plyteliu_specs pažymi didžiaformatę"),
    Concept("gkp_lubos", _rx(r"GKP.*ant lubų|gipso ?kartono lub"),
            _rx(r"GKP lubų montavimas"),
            "Jo skirstymas pagal karkaso aukštį = mūsų standartinis/virš 3 m."),
    Concept("nisos_pertvarose", _rx(r"niš\w*\s+pertvarose"),
            _rx(r"Nišų pertvarose įrengimas"), "checklist"),
    Concept("nisos_led_dazymas", _rx(r"niš\w*.*(glaistymas|dažymas)"),
            _rx(r"LED nišų (glaistymas|dažymas)")),
    Concept("nisos_led", _rx(r"niš\w*\s+formavimas|niš\w*.*(paslėptam|karnizam)"),
            _rx(r"Nišų formavimas GKP")),
    Concept("pertvaru_storinimas", _rx(r"pertvar\w*\s+storinimas"),
            _rx(r"Pertvarų storinimas"), "checklist"),
    # He calls the SAME work three ways across projects: "pertvaros
    # sutvirtinimas" (berzas), "dėžutčių iš GKP … tualetų mechanizmams"
    # (ciurliu/lazunu), "dėžutės iš GKP … WC mechanizmams" (objektas_b).
    Concept("pertvaros_sutvirtinimas",
            _rx(r"pertvar\w*\s+sutvirtinimas|dėžu\w*\W+iš gkp.*(wc|tualet)"),
            _rx(r"Pertvaros sutvirtinimas WC mechanizmams"),
            "perpavadinta 2026-07-29 į rangovo formuluotę"),
    Concept("revizines_dureles", _rx(r"revizini\w*\s+durel"),
            _rx(r"Reviziniai dureliai")),
    Concept("pasleptu_duru_staktos", _rx(r"paslėptų durų stakt"),
            _rx(r"Durų angų paruošimas beapvadinėms durims")),
    Concept("gk_klijavimas", _rx(r"gipso ?kartono klijavimas"),
            _rx(r"Gipso kartono klijavimas sienai išlyginti"), "checklist"),
    Concept("gkp_pertvaros", _rx(r"pertvar\w*\s+(montavimas|įrengimas)|GKP pertvar"),
            None, "GKP PERTVARŲ m² neskaičiuojam — modelyje tik lubų GKP"),
    Concept("difuzoriai_mont", _rx(r"difūzori\w*\s+montavimas"),
            _rx(r"Difūzorių montavimas")),
    Concept("difuzoriai_apd", _rx(r"difūzori\w*\s+apdirbimas"),
            _rx(r"Difūzorių (apdirbimas|montavimas ir apdirbimas)")),
    Concept("sviestuvai_mont", _rx(r"šviestuv\w*\s+montavimas"),
            _rx(r"šviestuvų montavimas")),
    Concept("sviestuvai_apd", _rx(r"šviestuv\w*\s+apdirbimas"),
            _rx(r"Šviestuvų apdirbimas")),
    Concept("track_mont", _rx(r"TRACK.*montavimas"),
            _rx(r"TRACK apšvietimo sistemos montavimas"), "checklist"),
    Concept("track_apd", _rx(r"TRACK.*apdirbimas"),
            _rx(r"TRACK apšvietimo sistemos apdirbimas"), "checklist"),
    Concept("angokrasciai", _rx(r"angokrašč"),
            _rx(r"Angokraščių (glaistymas|apdirbimas)"),
            "jis skiria sandarinimą nuo apdirbimo — mes glaistymą nuo GKP struktūros"),

    # ── Sienų lubų glaistymas dažymas ───────────────────────────────────────
    Concept("rotband", _rx(r"lyginimas sausu|rotband"), _rx(r"Rotband")),
    Concept("dazymas", _rx(r"glaistymas ?/ ?dažymas|glaistymas/dažymas"),
            _rx(r"glaistymas/dažymas"),
            "iki/virš 3 m eilutės atitinka 1:1"),
    # `beapva\w*din` — objektas_b nr 19 is typed "beapvasdinėms".
    Concept("duru_angos", _rx(r"beapva\w*din"), _rx(r"beapvadinėms durims")),
    Concept("dazymo_kampai", _rx(r"dažymo kampų"), _rx(r"Dažymo kampų montavimas")),
    Concept("molio_tinkas", _rx(r"molio tink"), _rx(r"molio tinku")),

    # ── Plytelių klijavimas ─────────────────────────────────────────────────
    Concept("plyteles", _rx(r"plytel\w*\s+klijavimas"),
            _rx(r"plytelių klijavimas"),
            "jis skirsto pagal formatą (120×60/120×120/90×90), mes pagal vietą"),
    Concept("lentyneles", _rx(r"lentynėl"), _rx(r"Lentynėlių iš plytelių")),
    Concept("nuolydis", _rx(r"nuolydžio formavimas"), _rx(r"Nuolydžio formavimas")),
    Concept("hidroizoliacija", _rx(r"hidroizoliacij"), _rx(r"Hidroizoliacijos įrengimas")),
    Concept("skyliu_grezimas", _rx(r"skyl\w*\s+gręžimas"), _rx(r"Skylių gręžimas")),
    Concept("latakai", _rx(r"latak"), _rx(r"latako montavimas")),
    Concept("silikonavimas", _rx(r"silikonavimas"), _rx(r"silikonavimas")),
    Concept("plyteliu_grindjuostes", _rx(r"grindjuosč\w*\s+supjovimas"),
            _rx(r"Plytelių grindjuosčių supjovimas"),
            "nauja 2026-07-29 — plytelėtų grindų patalpų grindjuostės"),
    Concept("pjovimas_45", _rx(r"45\s*[⁰°]|supjovimas 45|45\s*laipsn"),
            _rx(r"45° pjovimas")),
    Concept("fugavimas", _rx(r"fugav|glaistymas epoksid"), _rx(r"plytelių fugavimas")),

    # ── Grindys ─────────────────────────────────────────────────────────────
    Concept("isliginamasis", _rx(r"išlyginam\w*\s+(sluoksni|pylimas)|išlyginamojo"),
            _rx(r"Grindų išlyginamasis sluoksnis")),
    Concept("grindu_danga", _rx(r"pvc (dangos|grindų)|parket|laminat|guminės dangos"),
            _rx(r"Parketo / laminato klojimas")),
    Concept("grindjuostes_mdf",
            _rx(r"grindjuosč\w*\s+(klijavimas|montavimas|įrengimas)|įleistų grindjuosč"),
            _rx(r"Grindjuosčių sumontavimas")),

    # ── Santechnikos darbai ─────────────────────────────────────────────────
    Concept("lauko_ciaupas", _rx(r"lauko laistymo|lauko čiaup|vandens taš\w* laistymui"),
            None, "LAUKO įranga — interjero modulis skaito tik vidaus planus"),
    Concept("vonios_maisytuvas", _rx(r"vonios (maišytuv|sistem)"),
            _rx(r"vonios maišytuvo")),
    Concept("praustuvo_maisytuvas", _rx(r"praustuv\w*\s+(maišytuv|sistem)"),
            _rx(r"praustuvės maišytuvo")),
    Concept("duso_maisytuvas", _rx(r"dušo (maišytuv|sistem)"), _rx(r"dušo maišytuvo")),
    Concept("bide", _rx(r"bide\w*\s+dušiuk|bidė"), _rx(r"Bidė dušiuko"), "checklist"),
    Concept("wc_remas", _rx(r"WC rėmo"), _rx(r"WC rėmo montavimas")),
    Concept("klozetas", _rx(r"klozeto montavimas"), _rx(r"Klozeto montavimas")),
    Concept("praustuve", _rx(r"praustuv\w*\s+montavimas"), _rx(r"Praustuvės montavimas")),
    Concept("gyvatukas", _rx(r"gyvatuk"), _rx(r"Gyvatuko montavimas")),
    Concept("skalb_sifonas", _rx(r"skalbimo mašinos sifon"),
            _rx(r"Skalbimo mašinos sifono")),
    Concept("skalb_masina", _rx(r"skalbimo mašinos montavimas"),
            _rx(r"Skalbimo mašinos montavimas")),
    Concept("dziovykle", _rx(r"džiovykl"), None,
            "džiovyklės pajungimo eilutės neturim (skalbimo mašiną turim)"),
    Concept("san_taskai", _rx(r"santechnikos taškų"),
            _rx(r"Santechnikos taškų koregavimas")),
    Concept("san_medziagos", _rx(r"medžiagos.*montavimui|^medžiagos$"), None,
            "vienkartinė MEDŽIAGŲ eilutė — ne kiekių žiniaraščio pozicija"),
    Concept("plautuve", _rx(r"plautuv"), _rx(r"Plautuvės montavimas")),

    # ── Elektra / ventiliacija ──────────────────────────────────────────────
    Concept("skyliu_sviestuvams", _rx(r"skyl\w*\s+šviestuvams"),
            _rx(r"Skylių šviestuvams gręžimas")),
    Concept("rozetes", _rx(r"rozet\w*\W*/?\s*jungikl"),
            _rx(r"Rozetės / jungiklio pajungimas")),
    Concept("led_juosta", _rx(r"led juost"), _rx(r"LED juostos pajungimas")),
    Concept("ortakiai", _rx(r"ortaki\w*\s+(įrengimas|montavimas)|rekuperac"),
            _rx(r"Ortakių D\d+ mm montavimas")),
    Concept("vent_medziagos",
            _rx(r"^(ortakis|alkūnė|mova|trišakis|pereiga|balninė|statmena|"
                r"lankstus|apvali|perforuota|izoliacinė|aliuminio|aliuminė|"
                r"pūsto|pagalbinės)"),
            None, "ventiliacijos MEDŽIAGŲ specifikacija — mes emit'inam tik "
                  "montavimo darbus (ortakių m, izoliacija, tvirtinimas)"),

    # ── Statybvietės išlaidos ───────────────────────────────────────────────
    Concept("siuksles", _rx(r"šiukšl"), _rx(r"Šiukšlių išvežimas")),
    Concept("pastoliai", _rx(r"pastoli"), _rx(r"Pastolių nuoma")),
]

_SUBTOTAL = _rx(r"^viso\b")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def contractor_lines(slug: str) -> tuple[list[dict], int]:
    path = REPO / "ground_truth" / slug / "contractor_samata_parsed.json"
    if not path.exists():
        return [], 0
    raw = json.loads(path.read_text(encoding="utf-8")).get("line_items") or []
    priced = [it for it in raw if not _SUBTOTAL.match(_norm(it.get("name")))]
    return priced, len(raw)


# The line-coverage change of 2026-07-29, expressed as a control so `--baseline`
# can measure the SAME extract under the SAME concept table without the rows this
# change added. Anything else that moved between the two columns would be a
# different change and must be investigated, not averaged in.
_ADDED_2026_07_29 = _rx(
    r"GKP „dėžučių“ montavimas ant lubų"
    r"|Nišų pertvarose įrengimas"
    r"|Pertvarų storinimas \(LED"
    r"|Gipso kartono klijavimas sienai išlyginti"
    r"|Dėžutės montavimas ortakiams paslėpti"
    r"|TRACK apšvietimo sistemos"
    r"|Plytelių grindjuosčių supjovimas"
)
_RENAMED_2026_07_29 = {
    "Pertvaros sutvirtinimas WC mechanizmams montuoti (GKP dėžutė)":
        "Dėžučių iš GKP formavimas WC mechanizmams paslėpti",
}


def app_lines(slug: str, *, baseline: bool = False) -> list[dict]:
    from extractor.vision_call import _build_pozicijos_from_rooms
    path = REPO / "ground_truth" / slug / "ai_extract.json"
    if not path.exists():   # samata parsed but no cached extract (eg. sernu)
        return []
    parsed = json.loads(path.read_text(encoding="utf-8"))
    parsed = _build_pozicijos_from_rooms(parsed)
    poz = parsed.get("pozicijos") or []
    if baseline:
        poz = [{**p, "aprasymas": _RENAMED_2026_07_29.get(
                    _norm(p.get("aprasymas")), p.get("aprasymas"))}
               for p in poz if not _ADDED_2026_07_29.search(_norm(p.get("aprasymas")))]
    return poz


def reconcile(slug: str, *, baseline: bool = False) -> dict:
    priced, n_raw = contractor_lines(slug)
    ours = app_lines(slug, baseline=baseline)
    concepts = [Concept(c.key, c.contractor, c.app, c.note) for c in CONCEPTS]

    unmapped_contractor: list[dict] = []
    for it in priced:
        name = _norm(it.get("name"))
        for c in concepts:
            if c.contractor.search(name):
                c.c_rows.append(it)
                break
        else:
            unmapped_contractor.append(it)

    used_app: set[int] = set()
    for c in concepts:
        if c.app is None:
            continue
        for p in ours:
            if c.app.search(_norm(p.get("aprasymas"))):
                c.a_rows.append(p)
                used_app.add(id(p))

    rows = []
    for c in concepts:
        if not c.c_rows:
            continue
        checklist = [p for p in c.a_rows if p.get("saltinis") == "checklist"]
        if not c.a_rows:
            status = "MISSING"
        elif len(checklist) == len(c.a_rows):
            status = "CHECKLIST"
        elif len(c.c_rows) > 1 or len(c.a_rows) > len(c.c_rows):
            status = "AGGREGATED"
        else:
            status = "OK"
        rows.append({"concept": c, "status": status, "checklist": checklist})

    n_missing = sum(len(r["concept"].c_rows) for r in rows if r["status"] == "MISSING")
    n_missing += len(unmapped_contractor)
    n_checklist = sum(len(r["concept"].c_rows) for r in rows if r["status"] == "CHECKLIST")
    return {
        "slug": slug, "n_raw": n_raw, "n_priced": len(priced),
        "rows": rows, "unmapped_contractor": unmapped_contractor,
        "ours": ours, "used_app": used_app,
        "n_missing": n_missing, "n_checklist": n_checklist,
        "n_covered": len(priced) - n_missing,
    }


def report(slug: str, show_unmapped_app: bool = False,
           baseline: bool = False) -> dict | None:
    r = reconcile(slug, baseline=baseline)
    if not r["n_priced"]:
        print(f"\n=== {slug}: no contractor samata parsed — skipped ===")
        return None
    print(f"\n{'=' * 96}\n{slug}  —  {r['n_raw']} eilutės faile "
          f"({r['n_priced']} įkainotos + {r['n_raw'] - r['n_priced']} „Viso už skyrių“)"
          f"\n{'=' * 96}")
    print(f"{'nr':>4}  {'contractor line':<52} {'status':<11} our line")
    for row in sorted(r["rows"], key=lambda x: _sort_nr(x["concept"].c_rows[0])):
        c = row["concept"]
        for i, it in enumerate(c.c_rows):
            ours_txt = ""
            if i == 0:
                ours_txt = " · ".join(_norm(p.get("aprasymas"))[:46] for p in c.a_rows[:2])
                if len(c.a_rows) > 2:
                    ours_txt += f" (+{len(c.a_rows) - 2})"
                ours_txt = ours_txt or f"— {c.note or 'nėra'}"
            print(f"{str(it.get('nr')):>4}  {_norm(it.get('name'))[:52]:<52} "
                  f"{row['status'] if i == 0 else '':<11} {ours_txt}")
    for it in r["unmapped_contractor"]:
        print(f"{str(it.get('nr')):>4}  {_norm(it.get('name'))[:52]:<52} "
              f"{'UNMAPPED':<11} — nėra koncepto")

    print(f"\n  ĮKAINOTOS EILUTĖS: {r['n_priced']}")
    print(f"    · turi atitikmenį      {r['n_covered']:>3}  "
          f"({r['n_covered'] / r['n_priced'] * 100:.0f}%)")
    print(f"      iš jų checklist      {r['n_checklist']:>3}  "
          f"(kiekis=null, vartotojas suveda)")
    print(f"    · be atitikmens        {r['n_missing']:>3}")
    if show_unmapped_app:
        extra = [p for p in r["ours"] if id(p) not in r["used_app"]]
        print(f"\n  MŪSŲ EILUTĖS BE RANGOVO ATITIKMENS ({len(extra)} iš {len(r['ours'])}):")
        for p in extra:
            print(f"      {str(p.get('skyrius'))[:26]:<26} {_norm(p.get('aprasymas'))[:56]:<56} "
                  f"{p.get('kiekis')} {p.get('vnt')}")
    return r


def _sort_nr(it: dict) -> tuple:
    nr = str(it.get("nr") or "")
    return (int(nr) if nr.isdigit() else 9999, nr)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    show = "--unmapped" in sys.argv
    baseline = "--baseline" in sys.argv
    if "--all" in sys.argv:
        slugs = sorted(p.parent.name for p in
                       (REPO / "ground_truth").glob("*/contractor_samata_parsed.json"))
    else:
        slugs = args or ["berzas"]
    if "--delta" in sys.argv:  # before/after on the SAME extract + concept table
        print(f"{'project':<14}{'priced':>7}{'before':>8}{'after':>7}{'Δ':>5}"
              f"{'checklist':>11}")
        for slug in slugs:
            if not (REPO / "ground_truth" / slug / "ai_extract.json").exists():
                continue
            b, a = reconcile(slug, baseline=True), reconcile(slug)
            if not a["n_priced"]:
                continue
            print(f"{slug:<14}{a['n_priced']:>7}{b['n_covered']:>8}"
                  f"{a['n_covered']:>7}{a['n_covered'] - b['n_covered']:>+5}"
                  f"{a['n_checklist']:>11}")
        return 0
    totals = [0, 0, 0]
    for slug in slugs:
        r = report(slug, show, baseline)
        if r:
            totals[0] += r["n_priced"]
            totals[1] += r["n_covered"]
            totals[2] += r["n_checklist"]
    if len(slugs) > 1 and totals[0]:
        print(f"\n{'=' * 96}\nVISO: {totals[1]}/{totals[0]} eilučių padengta "
              f"({totals[1] / totals[0] * 100:.0f}%), iš jų {totals[2]} checklist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
