"""GET /api/projects/{project_id}/rows/{row_id}/sudetis — what a work row is made of.

The composition („sudėtis") of one darbu_sarasas line (togal-v2 W9): the
labour itself, the materials by norm with waste, each with a plain-LT sentence
(„norma 1,25 kg/m² × 308,32 m² = 385,40 kg").

It EXPLAINS rows that already exist; it never writes a quantity and never
becomes a second truth:
  * a material the engine already put in „Medžiagos" (`susijes_darbas` = this
    row's label) is shown with THAT row's quantity. The norm is stated only when
    norma × kiekis × (1 + atliekos) reproduces it within rounding; otherwise
    the sentence says the quantity was summed room by room;
  * a material of the engine's that no assembly names is still listed
    („kita medžiaga"), so the composition is complete;
  * a component of HIS assembly that has no Medžiagos row is computed from his
    norm and says so („Medžiagų skyriuje tokios eilutės nėra").

Which assembly: the row's `rinkinys_id` (his choice, written by the browser when
he applies one), else the default whose template matches the row's label.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request

import auth as _auth
import db as _db
from api.assemblies_default import (DEFAULT_PREFIX, build_default_assemblies,
                                    default_by_id, kodas_for_enum)
from extractor.universal_rules import lt_num

log = logging.getLogger("samatu.sudetis")

router = APIRouter(prefix="/api/projects", tags=["sudetis"])

SK_MEDZIAGOS = "Medžiagos"
_UNIT_LT = {"m2": "m²", "m3": "m³", "vnt": "vnt.", "m": "m", "kg": "kg", "l": "l"}


def unit_lt(vnt: Any) -> str:
    v = str(vnt or "").strip()
    return _UNIT_LT.get(v.lower().rstrip("."), v)


def _f(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _num(v: float) -> str:
    """Up to 4 decimals, trailing zeros dropped, LT comma: 1.25 → „1,25", 0.142857 → „0,1429"."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if s else "0"


def _template_rx(template: str) -> re.Pattern | None:
    if not template:
        return None
    parts = template.split("{vieta}")
    if len(parts) > 2:
        return None
    if len(parts) == 1:
        return re.compile("^" + re.escape(template) + "$")
    return re.compile("^" + re.escape(parts[0]) + "(.*?)" + re.escape(parts[1]) + "$")


def match_template(template: str, label: str) -> str | None:
    """The `{vieta}` part of `label` when it fits `template` ("" when the
    template has none), else None."""
    rx = _template_rx(template)
    m = rx.match(label.strip()) if rx else None
    if not m:
        return None
    return m.group(1) if m.groups() else ""


def apply_rounding(value: float, apvalinimas: str | None, minimumas: float | None) -> float:
    raw = value
    if apvalinimas == "aukstyn":
        value = math.ceil(value - 1e-9)
    elif apvalinimas == "zemyn":
        value = math.floor(value + 1e-9)
    elif apvalinimas == "artimiausias":
        value = round(value)
    if minimumas is not None and raw > 0:
        value = max(value, minimumas)
    return round(value, 2)


def _reproduces(expected: float, actual: float) -> bool:
    """Within the rounding the engine applies (per-room cents, one decimal on
    ducts, whole units)."""
    return abs(expected - actual) <= max(0.06, 0.003 * abs(actual))


def _project_choices(project: dict) -> dict[str, Any]:
    """The putty Q-level and paint class the engine used for this project."""
    from extractor.vision_call import _resolve_paint_class_from_prefs, putty_q_level
    ov = project.get("_overrides") if isinstance(project.get("_overrides"), dict) else {}
    pc = next((r.get("_paint_class") for r in (project.get("patalpos") or [])
               if isinstance(r, dict) and r.get("_paint_class") in (1, 2, 3)), None)
    return {"q_level": putty_q_level(ov) or "Q2",
            "paint_class": pc if pc is not None else _resolve_paint_class_from_prefs(ov)}


def find_assembly(row: dict, project: dict, own: list[dict]) -> tuple[dict | None, str]:
    """(assembly, vieta). His explicit choice first, then the default by label."""
    choices = _project_choices(project)
    label = str(row.get("aprasymas") or row.get("pavadinimas") or "")
    rid = row.get("rinkinys_id")
    if isinstance(rid, str) and rid:
        a = (default_by_id(rid, **choices) if rid.startswith(DEFAULT_PREFIX)
             else next((x for x in own if x.get("id") == rid), None))
        if a:
            vieta = match_template((a.get("taikoma") or {}).get("aprasymas") or "", label)
            return a, vieta or ""
    for a in build_default_assemblies(**choices):
        vieta = match_template(a["taikoma"]["aprasymas"], label)
        if vieta is not None:
            return a, vieta
    return None, ""


def _material_rows_for(label: str, rows: list[dict]) -> list[dict]:
    return [r for r in rows if isinstance(r, dict)
            and (r.get("_medziaga") or r.get("skyrius") == SK_MEDZIAGOS)
            and str(r.get("susijes_darbas") or "").strip() == label.strip()]


def _name_matches(name: str, row_label: str) -> bool:
    lab = row_label.strip()
    return lab == name or lab.startswith(name + " — ")


def build_sudetis(project: dict, row_id: str, own: list[dict] | None = None) -> dict | None:
    rows = [r for r in (project.get("darbu_sarasas") or []) if isinstance(r, dict)]
    row = next((r for r in rows if str(r.get("id") or "") == str(row_id)), None)
    if row is None:
        return None
    label = str(row.get("aprasymas") or row.get("pavadinimas") or "").strip()
    vnt = unit_lt(row.get("vnt") or row.get("mato_vnt"))
    kiekis = _f(row.get("kiekis"))
    is_material = bool(row.get("_medziaga")) or row.get("skyrius") == SK_MEDZIAGOS
    assembly, vieta = (None, "") if is_material else find_assembly(row, project, own or [])
    materials = [] if is_material else _material_rows_for(label, rows)
    used: set[int] = set()
    out: list[dict] = []

    for comp in (assembly or {}).get("komponentai") or []:
        name = str(comp.get("pavadinimas") or "").replace("{vieta}", vieta)
        norma = _f(comp.get("norma")) or 0.0
        waste = _f(comp.get("atliekos_proc")) or 0.0
        c_vnt = unit_lt(comp.get("vnt"))
        entry = {"rusis": comp.get("rusis"), "pavadinimas": name, "vnt": c_vnt,
                 "norma": norma, "atliekos_proc": waste, "kaina": comp.get("kaina"),
                 "eilutes_id": None, "is_eilutes": False, "kiekis": None, "sakinys": ""}
        if comp.get("rusis") == "darbas":
            entry.update(pavadinimas=label, vnt=vnt, kiekis=kiekis,
                         sakinys=(f"{lt_num(kiekis)} {vnt} — eilutės kiekis" if kiekis is not None
                                  else "Eilutės kiekis dar neįvestas"))
            out.append(entry)
            continue
        expected = (apply_rounding(norma * kiekis * (1 + waste / 100.0),
                                   comp.get("apvalinimas"), _f(comp.get("minimumas")))
                    if kiekis is not None else None)
        formula = (f"norma {_num(norma)} {c_vnt}/{vnt} × {lt_num(kiekis)} {vnt}"
                   + (f" × atliekos {_num(waste)} %" if waste else "")
                   + (" (apvalinta aukštyn)" if comp.get("apvalinimas") == "aukstyn" else "")
                   if kiekis is not None else "")
        hit = next((i for i, m in enumerate(materials)
                    if i not in used and _name_matches(name, str(m.get("aprasymas") or ""))), None)
        if hit is not None:
            used.add(hit)
            m = materials[hit]
            actual = _f(m.get("kiekis"))
            entry.update(pavadinimas=str(m.get("aprasymas")), eilutes_id=m.get("id"),
                         is_eilutes=True, kiekis=actual, vnt=unit_lt(m.get("vnt")) or c_vnt)
            if expected is not None and actual is not None and _reproduces(expected, actual):
                entry["sakinys"] = f"{formula} = {lt_num(actual)} {entry['vnt']}"
            else:
                entry.update(norma=None, atliekos_proc=None,
                             sakinys=(f"{lt_num(actual)} {entry['vnt']} — kiekis sudėtas pagal "
                                      "patalpas, kaip eilutėje „Medžiagos“"
                                      if actual is not None else "Kiekis neapskaičiuotas"))
        else:
            entry.update(kiekis=expected,
                         sakinys=(f"{formula} = {lt_num(expected)} {c_vnt} — Medžiagų skyriuje "
                                  "tokios eilutės nėra" if expected is not None
                                  else "Eilutės kiekis dar neįvestas"))
        out.append(entry)

    for i, m in enumerate(materials):
        if i in used:
            continue
        actual = _f(m.get("kiekis"))
        m_vnt = unit_lt(m.get("vnt"))
        out.append({"rusis": "medziaga", "pavadinimas": str(m.get("aprasymas") or ""),
                    "vnt": m_vnt, "norma": None, "atliekos_proc": None, "kaina": None,
                    "eilutes_id": m.get("id"), "is_eilutes": True, "kiekis": actual,
                    "sakinys": (f"{lt_num(actual)} {m_vnt} — kiekis iš skaičiavimo pagal patalpas"
                                if actual is not None else "Kiekis neapskaičiuotas")})

    if not out:
        out.append({"rusis": "darbas", "pavadinimas": label, "vnt": vnt, "norma": 1.0,
                    "atliekos_proc": 0.0, "kaina": None, "eilutes_id": None,
                    "is_eilutes": False, "kiekis": kiekis,
                    "sakinys": (f"{lt_num(kiekis)} {vnt} — eilutės kiekis" if kiekis is not None
                                else "Eilutės kiekis dar neįvestas")})
    kodas = row.get("kodas") or (assembly or {}).get("kodas") or kodas_for_enum(row.get("skyrius_enum"))
    return {
        "eilute": {"id": row.get("id"), "aprasymas": label, "vnt": vnt, "kiekis": kiekis,
                   "kodas": kodas},
        "rinkinys": ({"id": assembly["id"], "name": assembly.get("name"),
                      "is_default": bool(assembly.get("is_default")),
                      "kodas": assembly.get("kodas"), "pastaba": assembly.get("pastaba")}
                     if assembly else None),
        "medziaga": is_material,
        "komponentai": out,
    }


# Plain `def`: a sqlite read plus a JSON parse, like /rooms/{nr}/facts.
@router.get("/{project_id}/rows/{row_id}/sudetis")
def api_row_sudetis(request: Request, project_id: str, row_id: str) -> dict[str, Any]:
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = _db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(status_code=404, detail="Projektas nerastas")
    try:
        own = _db.list_assemblies(user_id=user["id"])
    except Exception as exc:  # noqa: BLE001 — his own sets are an extra, the defaults still explain
        log.warning("sudetis: own assemblies unreadable user=%s: %r", user.get("id"), exc)
        own = []
    try:
        payload = build_sudetis(project, row_id, own)
    except Exception as exc:  # noqa: BLE001 — a malformed legacy blob is not a 500 trace
        log.error("sudetis failed project=%s row=%s: %r", project_id, row_id, exc)
        raise HTTPException(status_code=500, detail="Nepavyko sudaryti sudėties") from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Eilutė nerasta")
    return payload
