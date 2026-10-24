"""/api/projects/{project_id}/detect-run — „Perskaityti lapą": the €0 reading of
the drawing as a job with named stages (capability A of the Togal-v2 programme,
docs/superpowers/plans/2026-10-16-togal-v2-program.md; Togal's states in
docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md §3).

POST {pages: [n…] | "all", features: {plotai, konturai, sienos, angos, grindys}}
     → {job, stage, stages, …}: the reading starts in a background thread.
GET  /detect-run/{job} → {stage, stages: [{id, label_lt, status, started,
     finished, note}], per_page, result_ready, result?}.

What is read is EXACTLY the free re-read (api/free_reread.read_drawing: the
geometry lane, the door schedule, the vector symbols) — no Vision call, no lane
logic of its own. The stages are the lane's own: `apply_geometry(on_stage=)`
says which step it has reached. The stages are in the order the lane runs them — openings BEFORE walls, because a wall's chain of
strings has a hole where its door is (geometry_lane: „The openings come BEFORE
the walls are added").

The server SAVES NOTHING, as with the free re-read: the finished result has
the free re-read's shape, and the browser lands it through the same merge
(lib/freeReread.mergeFreeReread → /recompute-interior), which is where his
verified rooms, typed numbers and corrected outlines are kept. „kiekiai" is
that last step; the server hands it over („perduota") and the browser
finishes it.

A sheet and a feature choice narrow what LANDS, never what is read: the lane
reads the whole plan (it needs every sheet of a plan to align and add up
strings) and then the rooms outside the chosen sheets' plan, and the keys of
features he did not choose, are put back as they were — and so are their
entries in `_meta.geometrija` (a per-room entry names a room only when that
room's key landed; `_geometry_meta`). A narrowed result keeps the project's
stored lane version, so the full free re-read is still offered. Every snapshot
says so in `skaitoma_lt`.
"""
from __future__ import annotations

import copy
import json
import logging
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from api import free_reread as _fr
from extractor import geometry_lane as _gl

log = logging.getLogger("samatu.detect_run")

router = APIRouter(prefix="/api/projects", tags=["detect-run"])

# (id, label, what the stage reads — shown while it runs, the processing-time education Togal shows as a video)
STAGES: tuple[tuple[str, str, str], ...] = (
    ("mastelis", "Mastelis",
     "Skaitomi ant brėžinio linijų užrašyti matmenys. Iš linijos ilgio lape ir parašyto skaičiaus nustatomas kiekvieno lapo mastelis."),
    ("tekstas", "Tekstas",
     "Lape ieškoma patalpų numerių ir plotų užrašų — taip sužinoma, kur stovi kiekviena eksplikacijos patalpa."),
    ("lenteles", "Lentelės",
     "Perskaitomos brėžinio lentelės — durų, langų ir apdailos žiniaraščiai. Kiekviena eilutė pažymima ten, kur ji "
     "stovi lape, kad galėtumėte ją pamatyti brėžinyje."),
    ("planas", "Planas",
     "Lapai, kuriuose nubraižytas tas pats planas, sutapdinami pagal tas pačias sienas, kad kiekvienai patalpai būtų surinkti visų lapų užrašai."),
    ("konturai", "Kontūrai",
     "Iš vektorinių sienų randamas kiekvienos patalpos kontūras. Jūsų pataisyti ar nubraižyti kontūrai nekeičiami."),
    ("angos", "Angos",
     "Sienose ieškoma tarpų, durų varčių lankų ir langų stiklo linijų — taip randamos durys ir langai."),
    ("sienos", "Sienos",
     "Kiekvienos sienos ilgis sudedamas iš plane užrašytų matmenų. Kur jų nėra, ilgis įvertinamas iš kontūro ir taip pažymimas."),
    ("grindys", "Grindys",
     "Grindų plane perskaitoma, kokia danga nubraižyta kiekvienoje patalpoje."),
    ("kiekiai", "Kiekiai",
     "Perskaitomas durų žiniaraštis ir brėžinio simboliai, tada kiekiai perskaičiuojami pagal naujus duomenis."),
)
STAGE_IDS = tuple(s[0] for s in STAGES)
LANE_STAGES = STAGE_IDS[:-1]

FEATURES = ("plotai", "konturai", "sienos", "angos", "grindys")
# What a feature needs read first: walls are added up along an outline, openings are read in an outline's walls —
# and an outline brings its openings, which the lane writes in the frame of that outline (a stored openings record
# under today's outline would not match it on the check sheet).
REQUIRES = {"konturai": ("plotai", "angos"), "sienos": ("konturai",), "angos": ("konturai",), "grindys": ("plotai",)}
# The stages a feature's result comes from (mastelis and kiekiai always run)
FEATURE_STAGES = {"plotai": ("tekstas", "planas"), "konturai": ("konturai",), "angos": ("angos",),
                  "sienos": ("sienos",), "grindys": ("grindys",)}
# The room keys each feature writes — put back as they were when the feature is not chosen
FEATURE_KEYS = {
    "plotai": ("_vieta",),
    "konturai": ("polygon_pct", "polygon_source", "_konturas", "_atvira_erdve", "_konturo_priezastis", "_konturo_siulymas"),
    "sienos": tuple(_gl.PERIMETER_KEYS) + (_gl.PAIR_PROPOSAL, "_perimetras_matmenys"),
    "angos": ("_angos_sienose",),
    "grindys": tuple(_gl.FLOOR_KEYS) + ("_grindu_dangos_dvi",),
}

WALL_OUTLINES = ("vektoriniai_konturai", "sienu_konturas", "corrected", "manual")
HIS_OUTLINES = ("corrected", "manual")
FROM_DIMENSIONS = ("matmenu_eilutes", "plano_matmenys")

JOB_TTL_S = 30 * 60
MAX_PAGES = 500
FAILED_BEFORE = "Neatlikta — ankstesnis etapas nepavyko."
NOT_CHOSEN = "Nepasirinkta — šio etapo rezultatas nepritaikomas."
LANE_FAILED = "Šio etapo skaitymas nepavyko — projekte niekas nepakeista."
HANDED_OVER = "Perskaičiuojama naršyklėje."
# What „per sheet" means, on every snapshot: the pill and the toast never present a whole-drawing read as one sheet's
SKAITOMA_LT = ("Skaitomas visas brėžinys — lapai sutapdinami ir sienų matmenys sudedami per visus lapus; "
               "pritaikoma tik pasirinktam lapui ir pasirinktoms funkcijoms.")

def _now() -> float:
    return round(time.time(), 3)


class _Job:
    def __init__(self, project_id: str, pages, features: set[str], added: list[str]):
        self.id = uuid.uuid4().hex
        self.project_id = project_id
        self.pages = pages                     # list[int] or "all"
        self.features = features
        self.added = added
        self.created = _now()
        self.finished: float | None = None
        self.lock = threading.Lock()
        self.cursor = -1
        self.stages = [{"id": sid, "label_lt": label, "about_lt": about, "status": "pending",
                        "started": None, "finished": None, "note": None} for sid, label, about in STAGES]
        self.per_page: dict = {}
        self.result: dict | None = None
        self.error: str | None = None

    def _chosen(self, sid: str) -> bool:
        return any(sid in FEATURE_STAGES[f] for f in self.features) or sid in ("mastelis", "lenteles", "kiekiai")

    def enter(self, sid: str) -> None:
        idx = STAGE_IDS.index(sid)
        with self.lock:
            if idx <= self.cursor:
                return
            t = _now()
            for i in range(max(self.cursor, 0), idx):
                s = self.stages[i]
                if s["status"] in ("pending", "running"):
                    s["status"] = "done" if self._chosen(s["id"]) else "skipped"
                    s["started"] = s["started"] or t
                    s["finished"] = t
            s = self.stages[idx]
            s["status"] = "running" if self._chosen(sid) else "skipped"
            s["started"] = t
            if s["status"] == "skipped":
                s["note"] = NOT_CHOSEN
            self.cursor = idx

    def fail_current(self, note: str) -> None:
        with self.lock:
            idx = min(max(self.cursor, 0), len(self.stages) - 1)
            t = _now()
            cur = self.stages[idx]
            cur["status"], cur["note"] = "failed", note
            cur["started"] = cur["started"] or t
            cur["finished"] = t
            for s in self.stages[idx + 1:]:
                s["status"], s["note"] = "skipped", FAILED_BEFORE
            self.cursor = len(self.stages)
            self.error = note
            self.finished = t

    def snapshot(self, *, with_result: bool) -> dict:
        with self.lock:
            running = next((s["id"] for s in self.stages if s["status"] in ("running", "perduota")), None)
            current = running or (self.stages[self.cursor]["id"] if 0 <= self.cursor < len(self.stages) else None)
            out = {
                "job": self.id,
                "stage": current,
                "stages": copy.deepcopy(self.stages),
                "per_page": copy.deepcopy(self.per_page),
                "pages": self.pages,
                "features": sorted(self.features, key=FEATURES.index),
                "features_added": list(self.added),
                "skaitoma_lt": SKAITOMA_LT,
                "result_ready": self.result is not None,
                "failed": self.error is not None,
                "created": self.created,
                "finished": self.finished,
            }
            if with_result and self.result is not None:
                out["result"] = self.result
            return out


_jobs: dict[str, _Job] = {}
_jobs_lock = threading.Lock()


def _purge(now: float | None = None) -> None:
    now = now or time.time()
    with _jobs_lock:
        for jid in [j for j, job in _jobs.items() if now - (job.finished or job.created) > JOB_TTL_S]:
            _jobs.pop(jid, None)


# ── what lands ──────────────────────────────────────────────────────────────

def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def _room_page(room: dict) -> int | None:
    for v in ((room.get("_vieta") or {}).get("page") if isinstance(room.get("_vieta"), dict) else None,
              (room.get("_konturas") or {}).get("page") if isinstance(room.get("_konturas"), dict) else None,
              room.get("puslapio_nr")):
        try:
            if v is not None:
                return int(v)
        except (TypeError, ValueError):
            continue
    return None


def _plan_pages(pages, groups) -> set[int] | None:
    """The chosen sheets and every sheet of the plan they belong to (`_meta.geometrija.grupes`); None = all."""
    if pages == "all":
        return None
    chosen = set(pages)
    out = set(chosen)
    for g in groups or []:
        members = {int(p) for p in g}
        if members & chosen:
            out |= members
    return out


def _close_features(chosen: set[str]) -> tuple[set[str], list[str]]:
    out = set(chosen) | {"plotai"}                        # nothing is read without knowing where the rooms are
    changed = True
    while changed:
        changed = False
        for f in list(out):
            for need in REQUIRES.get(f, ()):
                if need not in out:
                    out.add(need)
                    changed = True
    return out, sorted(out - set(chosen), key=FEATURES.index)


def _restore(room: dict, before: dict, keys) -> None:
    for k in keys:
        if k in before:
            room[k] = copy.deepcopy(before[k])
        else:
            room.pop(k, None)


# Per-room entries of `_meta.geometrija`, by the feature whose keys they describe
META_ROOM_LISTS = {"konturai": "konturai", "konturu_siulymai": "konturai",
                   "perimetrai_sudeti": "sienos", "perimetrai_tusti": "sienos", "perimetrai_atmesti": "sienos",
                   "poros_patvirtintos": "sienos", "poros_atmestos": "sienos", "angos_sienose": "angos"}
META_ROOM_DICTS = {"konturu_priezastys": "konturai"}
META_GROUP_LISTS = {"atviros_erdves": "konturai", "skirtingu_lapu_erdves": "konturai", "ribos_nepasiulytos": "konturai"}
FLOOR_ROOM_LISTS = ("dvi_dangos",)


def _geometry_meta(new: dict, stored: dict, landed, rooms: list) -> dict:
    """The new read's `_meta.geometrija` with every per-room entry taken from the read only for a room whose key
    LANDED in this result, and from the stored record for every other room; a group entry (an open space, a
    proposed boundary) comes from the read when all its rooms landed, from the stored record when none did, and is
    dropped when they are mixed. Sheet-level facts (scales, alignment, sheets) come from the read. Counts derived
    from rooms (`vietos`, `nupiesta`) are counted again on the rooms as they land."""
    out = copy.deepcopy(new)
    stored = stored if isinstance(stored, dict) else {}

    def nrs(v):
        return [str(x) for x in v] if isinstance(v, list) else []

    for key, feat in META_ROOM_LISTS.items():
        merged = [n for n in nrs(new.get(key)) if landed(n, feat)] + [n for n in nrs(stored.get(key)) if not landed(n, feat)]
        out[key] = list(dict.fromkeys(merged))
    for key, feat in META_ROOM_DICTS.items():
        a = new.get(key) if isinstance(new.get(key), dict) else {}
        b = stored.get(key) if isinstance(stored.get(key), dict) else {}
        out[key] = {**{n: v for n, v in b.items() if not landed(n, feat)}, **{n: v for n, v in a.items() if landed(n, feat)}}

    for key, feat in META_GROUP_LISTS.items():
        keep = [g for g in (new.get(key) or []) if g and all(landed(str(n), feat) for n in g)]
        keep += [g for g in (stored.get(key) or []) if g and not any(landed(str(n), feat) for n in g)]
        out[key] = keep
    out["ribos"] = ([g for g in (new.get("ribos") or []) if all(landed(str(n), "konturai") for n in g.get("nariai") or [])]
                    + [g for g in (stored.get("ribos") or []) if not any(landed(str(n), "konturai") for n in g.get("nariai") or [])])
    nf = new.get("grindu_dangos") if isinstance(new.get("grindu_dangos"), dict) else {}
    sf = stored.get("grindu_dangos") if isinstance(stored.get("grindu_dangos"), dict) else {}
    floors = copy.deepcopy(nf)
    a, b = nf.get("perskaityta") or {}, sf.get("perskaityta") or {}
    floors["perskaityta"] = {**{n: v for n, v in b.items() if not landed(n, "grindys")}, **{n: v for n, v in a.items() if landed(n, "grindys")}}
    for key in FLOOR_ROOM_LISTS:
        merged = [n for n in nrs(nf.get(key)) if landed(n, "grindys")] + [n for n in nrs(sf.get(key)) if not landed(n, "grindys")]
        floors[key] = sorted(set(merged))
    out["grindu_dangos"] = floors
    # counted again on the rooms as they land (geometry_lane: `vietos` per source, `nupiesta` per drawn kind)
    vietos: dict = {}
    drawn = {"langai": 0, "durys": 0, "be_tarpo": 0}
    for r in rooms:
        if not isinstance(r, dict):
            continue
        v = r.get("_vieta") if isinstance(r.get("_vieta"), dict) else None
        if v and v.get("saltinis"):
            vietos[v["saltinis"]] = vietos.get(v["saltinis"], 0) + 1
        rec = r.get("_angos_sienose") if isinstance(r.get("_angos_sienose"), dict) else {}
        for o in rec.get("angos") or []:
            if o.get("nupiesta") == "langas":
                drawn["langai"] += 1
            elif o.get("nupiesta") == "durys":
                drawn["durys"] += 1
            if o.get("be_tarpo"):
                drawn["be_tarpo"] += 1
    out["vietos"] = vietos
    out["nupiesta"] = drawn
    return out


def narrow(project: dict, result: dict, pages, features: set[str]) -> tuple[dict, list[str]]:
    """The read narrowed to the chosen sheets' plan and the chosen features. Returns (result, in-scope room nrs).
    Rooms outside go back exactly as stored; inside, a feature not chosen keeps its stored keys."""
    out = dict(result)
    geo = ((result.get("_meta") or {}).get("geometrija") or {}) if isinstance(result.get("_meta"), dict) else {}
    scope_pages = _plan_pages(pages, geo.get("grupes"))
    before = {_nr(r): r for r in (project.get("patalpos") or []) if isinstance(r, dict) and _nr(r)}
    # rooms the read re-keyed to the drawing's numbers (free_reread.renumber_rooms): found under their stored key
    renum = result.get("_perkeisti_numeriai") if isinstance(result.get("_perkeisti_numeriai"), dict) else {}
    stored_key = {str(new): str(old) for old, new in renum.items()}
    rooms, in_scope, left_out = [], [], 0
    for r in result.get("patalpos") or []:
        if not isinstance(r, dict):
            rooms.append(r)
            continue
        old = before.get(_nr(r)) or before.get(stored_key.get(_nr(r), ""))
        page = _room_page(r)
        inside = scope_pages is None or (page is not None and page in scope_pages)
        if not inside and old is not None:
            kept = copy.deepcopy(old)
            for k in ("nr", "_vienetas", "_nr_brezinyje", "_modelio_nr"):     # the identity is the drawing's
                if k in r:
                    kept[k] = r[k]
            rooms.append(kept)
            left_out += 1
            continue
        room = copy.deepcopy(r)
        if old is not None:
            for f in FEATURES:
                if f not in features:
                    _restore(room, old, FEATURE_KEYS[f])
        rooms.append(room)
        if _nr(room):
            in_scope.append(_nr(room))
    out["patalpos"] = rooms
    if "angos" not in features:
        out.pop("_duru_ziniarastis", None)
        out.pop("_langu_ziniarastis", None)
    if "grindys" not in features:
        out.pop("_apdailos_lentele", None)
    # a sheet whose plan holds every room is the whole read: only a room left out, or a feature not chosen, narrows it
    narrowed = left_out > 0 or set(features) != set(FEATURES)
    if narrowed and isinstance(out.get("_meta"), dict) and isinstance(out["_meta"].get("geometrija"), dict):
        stored_geo = ((project.get("_meta") or {}).get("geometrija") or {}) if isinstance(project.get("_meta"), dict) else {}
        stored_geo = stored_geo if isinstance(stored_geo, dict) else {}
        scope = set(in_scope)

        def landed(nr: str, feature: str) -> bool:
            return nr in scope and feature in features

        meta = dict(out["_meta"])
        meta["geometrija"] = {**_geometry_meta(meta["geometrija"], stored_geo, landed, rooms), "versija": stored_geo.get("versija")}
        out["_meta"] = meta
    out["taikymas"] = {"puslapiai": pages, "funkcijos": sorted(features, key=FEATURES.index), "patalpos": in_scope}
    return out, in_scope


def openings_count(rooms: list[dict]) -> dict:
    """Openings read in the outlined rooms' walls; a door between two outlined rooms is listed from both sides and
    counted once (from the lower room number)."""
    outlined = {_nr(r) for r in rooms if isinstance(r.get("_angos_sienose"), dict)}
    total = langai = durys = 0
    for r in rooms:
        rec = r.get("_angos_sienose") if isinstance(r.get("_angos_sienose"), dict) else {}
        for a in rec.get("angos") or []:
            beyond = str(a.get("i") or "")
            if beyond in outlined and beyond < _nr(r):
                continue
            total += 1
            if a.get("nupiesta") == "langas":
                langai += 1
            elif a.get("nupiesta") == "durys":
                durys += 1
    return {"angos": total, "langai": langai, "durys": durys}


def _lt_list(nums: list[int]) -> str:
    nums = sorted(set(nums))
    if not nums:
        return ""
    if len(nums) > 2 and nums == list(range(nums[0], nums[-1] + 1)):
        return f"{nums[0]}–{nums[-1]}"
    return ", ".join(str(n) for n in nums)


def _lt(n: int, one: str, few: str, many: str) -> str:
    """„1 kontūras", „3 kontūrai", „11 kontūrų" (lib/ltPlural.js)."""
    last, last_two = n % 10, n % 100
    word = many if (10 <= last_two <= 19 or last == 0) else one if last == 1 else few
    return f"{n} {word}"


def _of_rooms(n: int) -> str:
    """„iš 1 patalpos", „iš 11 patalpų" — the genitive after „iš"."""
    return f"iš {n} " + ("patalpos" if n % 10 == 1 and n % 100 != 11 else "patalpų")


_SCHEDULE_LT = {"durys": "durų žiniaraštis", "langai": "langų žiniaraštis", "apdaila": "apdailos lentelė",
                "plyteles": "plytelių specifikacija", "eksplikacija": "patalpų eksplikacija"}


def tables_note(result: dict) -> str:
    """The „lentelės" stage's note: which schedules were read (with how many rows and on which sheet), or why
    none was."""
    meta = ((result.get("_meta") or {}).get("lenteles") or {}) if isinstance(result.get("_meta"), dict) else {}
    found = []
    for kind, s in (meta.get("ziniarasciai") or {}).items():
        if not isinstance(s, dict) or kind not in _SCHEDULE_LT:
            continue
        pages = s.get("pages") or [s.get("page")]
        where = f"{pages[0]} lape" if len(pages) == 1 else "lapuose " + ", ".join(str(p) for p in pages)
        found.append(f"{_SCHEDULE_LT[kind]} ({_lt(int(s.get('eilutes') or 0), 'eilutė', 'eilutės', 'eilučių')}, {where})")
    if found:
        return "Perskaityta: " + "; ".join(found) + "."
    if meta.get("status") == "no_text":
        return "Brėžinio lapuose nėra teksto sluoksnio — lentelių perskaityti negalima."
    n = sum(len(v or []) for v in (meta.get("lenteles") or {}).values())
    if n:
        return f"Rasta lentelių: {n}, bet nė viena nėra durų, langų ar apdailos žiniaraštis."
    return "Durų, langų ar apdailos lentelių brėžinyje nerasta."


def stage_notes(result: dict, in_scope: list[str], pages) -> dict[str, str]:
    geo = ((result.get("_meta") or {}).get("geometrija") or {}) if isinstance(result.get("_meta"), dict) else {}
    rooms = [r for r in result.get("patalpos") or [] if isinstance(r, dict) and _nr(r) in set(in_scope)]
    n = len(rooms)
    notes: dict[str, str] = {}
    scales = geo.get("masteliai") or {}
    look = [str(p) for p in (pages if pages != "all" else sorted(int(k) for k in scales))]
    found = sorted({int(scales[p]["mastelis"]) for p in look if isinstance(scales.get(p), dict) and scales[p].get("mastelis")})
    if found:
        notes["mastelis"] = "Mastelis iš matmenų: " + ", ".join(f"1:{m}" for m in found) + (
            f" ({len([p for p in look if p in scales])} lap.)" if len(look) > 1 else "")
    else:
        notes["mastelis"] = "Šiame lape matmenų užrašų nerasta — mastelis neperskaitytas; jį galite nustatyti matavimo įrankiu."
    located = [r for r in rooms if isinstance(r.get("_vieta"), dict)]
    notes["tekstas"] = (f"Rasta {len(located)} {_of_rooms(n)} pagal numerį ar plotą lape." if n
                        else "Šiame lape eksplikacijos patalpų nerasta.")
    notes["lenteles"] = tables_note(result)
    groups = [sorted(int(p) for p in g) for g in geo.get("grupes") or []]
    if pages != "all":
        mine = [g for g in groups if set(g) & set(pages)]
        if mine and len(mine[0]) > 1:
            notes["planas"] = f"Lapai {_lt_list(mine[0])} sutapdinti kaip vienas planas."
        elif mine:
            notes["planas"] = f"Lapas {mine[0][0]} — atskiras planas."
        else:
            notes["planas"] = "Šis lapas nėra patalpų planas — patalpos jame neskaitomos."
    else:
        notes["planas"] = f"Planų: {len(groups)}." if groups else "Patalpų plano nerasta."
    traced = [r for r in rooms if str(r.get("polygon_source") or "") == "vektoriniai_konturai"]
    his = [r for r in rooms if str(r.get("polygon_source") or "") in HIS_OUTLINES]
    without = [r for r in rooms if str(r.get("polygon_source") or "") not in WALL_OUTLINES]
    parts = [_lt(len(traced), "kontūras", "kontūrai", "kontūrų") + " iš sienų"]
    if his:
        parts.append(f"jūsų pataisytų palikta: {len(his)}")
    if without:
        parts.append(f"be kontūro: {len(without)}")
    notes["konturai"] = ", ".join(parts) + "."
    oc = openings_count(rooms)
    notes["angos"] = (_lt(oc["angos"], "anga", "angos", "angų") + f" (langų: {oc['langai']}, durų: {oc['durys']})."
                      if oc["angos"] else "Sienose angų nerasta.")
    dims = [r for r in rooms if str(r.get("perimetras_saltinis") or "") in FROM_DIMENSIONS]
    est = [r for r in rooms if str(r.get("perimetras_saltinis") or "") in _gl.ESTIMATES]
    notes["sienos"] = (_lt(len(dims), "perimetras", "perimetrai", "perimetrų") + " iš matmenų"
                      + (f", įvertinta iš kontūro: {len(est)}" if est else "") + ".")
    floors = [r for r in rooms if str(r.get("grindu_danga_saltinis") or "") == _gl.FLOOR_PLAN_SOURCE]
    notes["grindys"] = (f"Danga perskaityta {len(floors)} {_of_rooms(n)}." if floors
                        else "Grindų plane dangų neperskaityta.")
    return notes


def per_page(result: dict, in_scope: list[str], pages) -> dict:
    geo = ((result.get("_meta") or {}).get("geometrija") or {}) if isinstance(result.get("_meta"), dict) else {}
    scales = geo.get("masteliai") or {}
    rooms = [r for r in result.get("patalpos") or [] if isinstance(r, dict) and _nr(r) in set(in_scope)]
    want = pages if pages != "all" else sorted({p for p in (_room_page(r) for r in rooms) if p is not None})
    out = {}
    for p in want:
        on = [r for r in rooms if _room_page(r) == p]
        sc = scales.get(str(p)) if isinstance(scales.get(str(p)), dict) else None
        out[str(p)] = {
            "mastelis": int(sc["mastelis"]) if sc and sc.get("mastelis") else None,
            "patalpos": [_nr(r) for r in on],
            "konturai": sum(1 for r in on if str(r.get("polygon_source") or "") in WALL_OUTLINES),
            "perimetrai": sum(1 for r in on if str(r.get("perimetras_saltinis") or "") in FROM_DIMENSIONS),
            "angos": openings_count(on)["angos"],
            "grindys": sum(1 for r in on if str(r.get("grindu_danga_saltinis") or "") == _gl.FLOOR_PLAN_SOURCE),
        }
    return out


# ── the job ─────────────────────────────────────────────────────────────────

def _run(job: _Job, project: dict, pdf_bytes: bytes) -> None:
    try:
        job.enter("mastelis")
        try:
            out = _fr.read_drawing(project, pdf_bytes, on_stage=job.enter)
        except Exception as exc:  # noqa: BLE001 — read_drawing never raises; if it does, the stage says so
            log.error("detect-run read failed for %s: %r", job.project_id, exc)
            job.fail_current(LANE_FAILED)
            return
        if out.get("lane") == "failed":
            job.fail_current(LANE_FAILED)
            return
        narrowed, in_scope = narrow(project, out, job.pages, job.features)
        notes = stage_notes(narrowed, in_scope, job.pages)
        with job.lock:
            t = _now()
            for s in job.stages:
                if s["id"] == "kiekiai":
                    # the browser lands the read and rebuilds the rows (the same path every room edit takes)
                    s["status"], s["started"] = "perduota", s["started"] or t
                    s["note"] = HANDED_OVER
                    continue
                if s["status"] in ("pending", "running"):
                    s["status"] = "done" if job._chosen(s["id"]) else "skipped"
                    s["started"] = s["started"] or t
                    s["finished"] = t
                if s["status"] == "done":
                    s["note"] = notes.get(s["id"])
                elif s["status"] == "skipped" and not s["note"]:
                    s["note"] = NOT_CHOSEN
            job.cursor = STAGE_IDS.index("kiekiai")
            job.per_page = per_page(narrowed, in_scope, job.pages)
            job.result = narrowed
            job.finished = t
    except Exception as exc:  # noqa: BLE001 — a background thread has no one to raise to
        log.exception("detect-run job %s crashed", job.id)
        job.fail_current(f"{LANE_FAILED} ({type(exc).__name__})")
    finally:
        with _fr._running_lock:
            _fr._running.discard(job.project_id)


def _page_count(pdf_bytes: bytes) -> int | None:
    """The drawing's number of sheets (PDFium, under the process-wide lock); None when it cannot be told."""
    try:
        import pypdfium2 as pdfium
        from extractor.pdfium_guard import PDFIUM_LOCK
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_bytes)
            try:
                return len(doc)
            finally:
                doc.close()
    except Exception as exc:  # noqa: BLE001 — an unreadable count is checked by the lane itself, not here
        log.warning("detect-run page count failed: %r", exc)
        return None


def _parse_body(body) -> tuple[object, set[str], list[str]]:
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Netinkama užklausa")
    unknown = set(body) - {"pages", "features"}
    if unknown:
        raise HTTPException(status_code=400, detail=f"Nežinomi laukai: {', '.join(sorted(unknown))}")
    pages = body.get("pages", "all")
    if pages in ("all", "visi", None):
        pages = "all"
    elif isinstance(pages, list) and pages and len(pages) <= MAX_PAGES and all(
            isinstance(p, int) and not isinstance(p, bool) and p >= 1 for p in pages):
        pages = sorted(set(pages))
    else:
        raise HTTPException(status_code=400, detail="Lapai turi būti sąrašas lapų numerių (nuo 1) arba „all“")
    feats = body.get("features")
    if feats is None:
        chosen = set(FEATURES)
    elif isinstance(feats, dict) and set(feats) <= set(FEATURES) and all(isinstance(v, bool) for v in feats.values()):
        chosen = {f for f in FEATURES if feats.get(f, False)}
    else:
        raise HTTPException(status_code=400, detail=f"Funkcijos: {{{', '.join(FEATURES)}}} su reikšmėmis true/false")
    if not chosen:
        raise HTTPException(status_code=400, detail="Pasirinkite bent vieną, ką skaityti")
    features, added = _close_features(chosen)
    return pages, features, added


@router.post("/{project_id}/detect-run")
async def api_detect_run_start(request: Request, project_id: str):
    project = _fr._project_for(request, project_id)          # ownership BEFORE the body is looked at
    raw = await request.body()
    try:
        body = json.loads(raw) if raw else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Netinkama užklausa")
    pages, features, added = _parse_body(body)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "free_reread")

    _purge()
    with _fr._running_lock:
        if project_id in _fr._running:
            with _jobs_lock:
                live = next((j for j in _jobs.values() if j.project_id == project_id and j.finished is None), None)
            if live is not None:                               # his own run, from another tab: follow it
                return {**live.snapshot(with_result=False), "already_running": True}
            raise HTTPException(status_code=409, detail="Šis projektas jau skaitomas — palaukite, kol baigs.")
        _fr._running.add(project_id)
    try:
        from storage import get_storage, pdf_key
        try:
            pdf_bytes = await run_in_threadpool(get_storage().get, pdf_key(project_id))
        except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
            log.warning("detect-run pdf fetch failed for %s: %r", project_id, exc)
            raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail=_fr.NO_PDF)
        if pages != "all":
            count = await run_in_threadpool(_page_count, pdf_bytes)
            beyond = [p for p in pages if count is not None and p > count]
            if beyond:
                raise HTTPException(status_code=400, detail=f"Lapo {beyond[0]} brėžinyje nėra (lapų: {count})")
        job = _Job(project_id, pages, features, added)
        with _jobs_lock:
            _jobs[job.id] = job
        threading.Thread(target=_run, args=(job, project, pdf_bytes), name=f"detect-run-{job.id[:8]}", daemon=True).start()
    except BaseException:
        with _fr._running_lock:
            _fr._running.discard(project_id)
        raise
    return job.snapshot(with_result=False)


@router.get("/{project_id}/detect-run/{job_id}")
def api_detect_run_status(request: Request, project_id: str, job_id: str):
    _fr._project_for(request, project_id)
    _purge()
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Skaitymas nerastas — galbūt jis baigėsi seniau nei prieš 30 min.")
    return job.snapshot(with_result=True)
