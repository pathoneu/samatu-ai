"""A stand-in for the Anthropic client that answers every call `extract_interior`
makes from what a paid run already returned — the golden replay of the paid
pipeline (audit 2026-09-29, testing-eval-3).

The client is installed in place of `anthropic.Anthropic`, so the readers that
build their own client (doors, door types, fixtures, niches, apdailos) get it as
well as the ones handed the shared one (Pass-1 rounds, adjacency, zoom,
eksplikacija). Each call is attributed to the reader that made it by the
calling function, counted, and answered from that reader's queue; a call no
queue expects is recorded in `unexpected` and refused. No network: the real
client class refuses to be built and every socket refuses to connect while the
stub is installed.

What a paid run leaves behind is not the raw answers, so every answer here says
where it comes from (`Answer.source`):

  stored   — the model's own answer, kept verbatim: the VisionCache files the
             adjacency and niche readers wrote during the run, a room's
             `_zoom` (stored unchanged by `_apply_zoom_refinements`).
  derived  — rebuilt from the stored extract so that the reader's merge gives
             back exactly what the run stored: the Pass-1 rounds (the voted
             rooms with each round's `_vote` values), the door list (the doors
             the merge placed), the fixture list (`_sanitary_prietaisai` + the
             counts in the run's event log), the door-type answer (the voted
             reader counts).
  synthetic — nothing of it was kept; the value is chosen to reproduce the
             stored outcome and each is named in `OBJEKTAS_H_SYNTHETIC`.
"""
from __future__ import annotations

import copy
import json
import re
import socket
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from anthropic.types import Message, TextBlock, Usage

REPO_ROOT = Path(__file__).resolve().parents[2]

# reader ← (module, function) of the frame that called the client
_READERS_BY_FUNCTION = {
    ("extractor.vision_call", "_run_pass1_once"): "pass1",
    ("extractor.vision_call", "_vision_zoom_room"): "zoom",
    ("extractor.vision_call", "_reread_eksplikacija_on_pages"): "eksplikacija_retry",
}
_READERS_BY_MODULE = {
    "extractor.eksplikacija_reader": "eksplikacija",
    "extractor.vision.adjacency_extractor": "adjacency",
    "extractor.vision.niche_locator": "niche",
    "extractor.doors_reader": "doors",
    "extractor.door_type_reader": "door_type",
    "extractor.sanitary_fixture_reader": "fixtures",
    "extractor.apdailos_reader": "apdailos",
    "extractor.verify_pass": "verify",
    "extractor.agentic_crop": "zoom_agentic",
    "extractor.wall_elevation": "wall_elevation",
}


@dataclass
class Answer:
    """One model answer: the JSON (or text) the reader receives, the usage the
    call reports, and where the answer comes from (stored / derived / synthetic)."""
    payload: Any
    source: str
    usage: dict = field(default_factory=dict)
    note: str = ""

    def text(self) -> str:
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload, ensure_ascii=False)


def _caller_reader() -> tuple[str, str]:
    """(reader, "module.function") of the first frame outside this module."""
    frame = sys._getframe(1)
    while frame is not None:
        module = frame.f_globals.get("__name__", "")
        if module != __name__:
            func = frame.f_code.co_name
            reader = (_READERS_BY_FUNCTION.get((module, func))
                      or _READERS_BY_MODULE.get(module)
                      or f"{module}.{func}")
            return reader, f"{module}.{func}"
        frame = frame.f_back
    return "unknown", "unknown"


def _message(answer: Answer, model: str | None) -> Message:
    u = answer.usage or {}
    return Message(
        id="msg_golden_replay", type="message", role="assistant", model=model or "stub",
        content=[TextBlock(type="text", text=answer.text())],
        stop_reason="end_turn", stop_sequence=None,
        usage=Usage(input_tokens=int(u.get("input_tokens") or 0),
                    output_tokens=int(u.get("output_tokens") or 0),
                    cache_read_input_tokens=int(u.get("cache_read_tokens") or 0),
                    cache_creation_input_tokens=int(u.get("cache_write_tokens") or 0)))


class _Stream:
    def __init__(self, message: Message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self) -> Message:
        return self._message


class StubAnthropic:
    """The shared client every `anthropic.Anthropic(...)` returns while installed.

    `answers` maps a reader to a list of Answers (served in call order) or to a
    callable(request_kwargs) → Answer (for answers chosen by the request, like a
    zoom call's room). `calls` counts the calls per reader; `log` keeps
    (reader, caller, source) per call; `unexpected` the calls nobody expected."""

    def __init__(self, answers: dict[str, list[Answer] | Callable[[dict], Answer]]):
        self._answers = {k: (list(v) if isinstance(v, list) else v) for k, v in answers.items()}
        self.calls: Counter = Counter()
        self.log: list[tuple[str, str, str]] = []
        self.unexpected: list[str] = []
        self.constructed: list[dict] = []

    # the SDK surface the readers use
    def with_options(self, **_kw):
        return self

    @property
    def messages(self):
        return self

    def create(self, **kwargs) -> Message:
        return self._answer(kwargs)

    def stream(self, **kwargs) -> _Stream:
        return _Stream(self._answer(kwargs))

    def _answer(self, kwargs: dict) -> Message:
        reader, caller = _caller_reader()
        self.calls[reader] += 1
        source = self._answers.get(reader)
        if callable(source):
            answer = source(kwargs)
        elif source:
            answer = source.pop(0)
        else:
            self.unexpected.append(f"{reader} (from {caller})")
            raise AssertionError(f"golden replay: no stored answer for a {reader} call from {caller}")
        self.log.append((reader, caller, answer.source))
        return _message(answer, kwargs.get("model"))

    def leftover(self) -> dict[str, int]:
        """Queued answers nobody asked for — a reader that stopped calling."""
        return {k: len(v) for k, v in self._answers.items() if isinstance(v, list) and v}


def install(monkeypatch, client: StubAnthropic, cache_root: Path) -> None:
    """Put `client` in place of every Anthropic client and keep the run off the
    network and off the shared VisionCache directory."""
    import anthropic
    import anthropic._client as _real
    import httpx
    from extractor.vision._cache import VisionCache

    def _factory(*_a, **kwargs):
        client.constructed.append(dict(kwargs))
        return client

    def _refuse(*_a, **_k):
        raise AssertionError("golden replay: a real Anthropic client was constructed")

    def _no_network(*_a, **_k):
        raise AssertionError("golden replay: a network connection was attempted")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "golden-replay-no-api-calls")
    monkeypatch.setattr(anthropic, "Anthropic", _factory)
    monkeypatch.setattr(anthropic, "Client", _factory, raising=False)
    monkeypatch.setattr(_real.Anthropic, "__init__", _refuse)
    monkeypatch.setattr(_real.AsyncAnthropic, "__init__", _refuse)
    monkeypatch.setattr(httpx.Client, "send", _no_network)
    monkeypatch.setattr(httpx.AsyncClient, "send", _no_network)
    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _no_network)
    # The adjacency and niche readers look in the VisionCache first and write to
    # it after a call: an empty directory of the test's own makes every one of
    # them call the stub, and nothing lands in the developer's cache.
    monkeypatch.setattr(VisionCache.__init__, "__defaults__", (cache_root, "default"))


# ── objektas_h: the paid run of 2026-09-05 ───────────────────────────────────
OBJEKTAS_H_EXTRACT = REPO_ROOT / "ground_truth" / "objektas_h" / "ai_extract.json"
OBJEKTAS_H_META = REPO_ROOT / "ground_truth" / "objektas_h" / "ai_extract_meta.json"
# What the adjacency and niche readers cached during that run (gitignored, local).
_CACHE = REPO_ROOT / ".vision_cache"
OBJEKTAS_H_CACHED = {
    "adjacency": _CACHE / "room_adjacency" / "0756cb4392f0ab3f6527fa74ba3df57bfece755670fbda2be76aaec9f7e6134e.json",
    "niche_primary": _CACHE / "niche_locator" / "72cfb0c1b149e1dafaf4efd0722c1a81173deff5a6a6df60900f28783063ae93.json",
    "niche_backfill": _CACHE / "niche_locator" / "8b6821a1e2c71e5a576dc9af17d4c50935a47a94dfb32259b02393721686e4c6.json",
}
# Every value the stored material does not hold, and what stands in for it.
OBJEKTAS_H_SYNTHETIC = {
    "pass1 lubu_aukstis_saltinis": "„default_fallback\" — the run's own warning says no height was read",
    "pass1 detected_symbols_summary.dusai": "0 — the stored 2 is the fixture reader's raise; any value below 2 reconciles to 2",
    "pass1 plotas_saltinis": "„eksplikacija\" — overwritten by the table merge either way",
    "zoom room 01": "a low-confidence answer — the run attempted room 01, applied nothing and stored nothing",
    "door_type standartines_count / stumdomos_count": "0 — not kept; nothing downstream bills them",
}

# What the model returns for a Pass-1 room and the whole answer (prompt.py's
# schema) — everything else on a stored room a later step added, and adds again
# itself; likewise the element keys a later step writes.
_PASS1_ROOM_KEYS = ("nr", "pavadinimas", "paskirtis", "puslapio_nr", "bbox_pct", "polygon_pct",
                    "plotas_m2", "plotas_saltinis", "perimetras_m", "lubu_aukstis_m",
                    "lubu_aukstis_saltinis", "lubu_tipas", "plyteles_sienos_aukstis_m",
                    "elementai", "confidence", "pastabos")
_PASS1_TOP_KEYS = ("archetipas", "bendras_plotas_m2", "scale_source_page", "eksplikacija_source_page",
                   "puslapiai", "durys_total", "langai_total", "pastabos",
                   "inferred_paint_class", "inferred_paint_class_evidence")
_PIPELINE_ELEMENT_KEYS = ("_exterior",)
_DOORS = ("duris", "pasleptos_duris")


def objektas_h_material_missing() -> str | None:
    """Why the stored material is not on this machine, or None."""
    for path in (OBJEKTAS_H_EXTRACT, OBJEKTAS_H_META, *OBJEKTAS_H_CACHED.values()):
        if not path.is_file():
            return f"{path.relative_to(REPO_ROOT)} is not on this machine"
    return None


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extra_calls(frozen: dict, reader: str) -> list[dict]:
    return [c for c in ((frozen.get("_meta") or {}).get("extra_calls") or []) if c.get("reader") == reader]


def _vision_warnings(frozen: dict) -> list[dict]:
    """The model's own warnings: level + message (+ room), none the pipeline wrote."""
    out = []
    for w in frozen.get("warnings") or []:
        if not isinstance(w, dict) or set(w) - {"level", "message", "patalpa_nr"}:
            continue
        if str(w.get("message") or "").startswith("Apdailos/išklotinių lapas nenuskaitytas"):
            continue                          # _warn_apdailos_degraded — the pipeline's own
        out.append(dict(w))
    return out


def _rep_round(room: dict) -> int:
    """The round the voter takes the room's elements from: perimeter closest to the median."""
    vals = (((room.get("_vote") or {}).get("perimetras_m") or {}).get("values")) or []
    if not vals:
        return 0
    med = sorted(vals)[len(vals) // 2]
    return min(range(len(vals)), key=lambda i: abs(float(vals[i]) - med))


def _pass1_rounds(frozen: dict, n: int = 3) -> list[dict]:
    """The Pass-1 rounds whose vote is the stored consensus (derived): each
    round carries that round's voted values, the elements every round shared,
    and — absent from the representative round only — an element the voter
    could only rebuild bare (a type the representative did not list)."""
    top = {k: copy.deepcopy(frozen.get(k)) for k in _PASS1_TOP_KEYS if k in frozen}
    symbols = dict(frozen.get("detected_symbols_summary") or {})
    symbols.pop("vonios_kubilai", None)                       # written by the fixture reconcile
    for key in (frozen.get("_meta") or {}).get("fixtures_raised") or []:
        symbols[key] = 0                                       # synthetic, see OBJEKTAS_H_SYNTHETIC
    rounds = []
    for k in range(n):
        rooms = []
        for r in frozen.get("patalpos") or []:
            room = {key: copy.deepcopy(r[key]) for key in _PASS1_ROOM_KEYS if key in r}
            if r.get("polygon_source") == "synthesized_from_bbox":
                room.pop("polygon_pct", None)                  # the prepass drew it from the box
            for f in ("perimetras_m", "lubu_aukstis_m", "plotas_m2"):
                vals = (((r.get("_vote") or {}).get(f) or {}).get("values")) or []
                if len(vals) == n:
                    room[f] = vals[k]
            room["plotas_saltinis"] = "eksplikacija"
            room["lubu_aukstis_saltinis"] = "default_fallback"
            rep = _rep_round(r)
            elements = []
            for e in r.get("elementai") or []:
                if e.get("_source") == "statistical_inference":
                    continue                                   # niche inference adds it again
                if set(e) == {"tipas", "kiekis"} and k == rep:
                    continue                                   # the voter rebuilt it bare
                elements.append({key: v for key, v in e.items() if key not in _PIPELINE_ELEMENT_KEYS})
            room["elementai"] = elements
            rooms.append(room)
        rounds.append({**copy.deepcopy(top), "patalpos": rooms,
                       "detected_symbols_summary": dict(symbols),
                       "warnings": _vision_warnings(frozen)})
    return rounds


def _doors_answer(frozen: dict) -> dict:
    """The door list whose merge places exactly the stored doors (derived)."""
    doors = []
    for r in frozen.get("patalpos") or []:
        for e in r.get("elementai") or []:
            if (e.get("tipas") or "") not in _DOORS:
                continue
            for _ in range(int(e.get("kiekis") or 1)):
                doors.append({
                    "id": f"d{len(doors) + 1}",
                    "tipas": "pasleptos" if e["tipas"] == "pasleptos_duris" else "standart",
                    "plotis_mm": e.get("plotis_mm"), "aukstis_mm": e.get("aukstis_mm"),
                    "between": [r["nr"], "exterior"] if e.get("_exterior") else [r["nr"]],
                    "pastabos": "",
                })
    ext = sum(1 for d in doors if "exterior" in d["between"])
    return {"doors": doors, "total_count": len(doors), "interior_count": len(doors) - ext,
            "exterior_count": ext}


def _fixture_counts(meta_log: dict) -> dict:
    for ev in meta_log.get("metas") or []:
        if ev.get("event") == "fixtures_completed":
            return dict(ev.get("counts") or {})
    return {}


def objektas_h_answers(frozen: dict, meta_log: dict) -> dict[str, Any]:
    """Every answer the 2026-09-05 objektas_h run received, per reader."""
    metas = frozen.get("_meta") or {}
    rounds = _pass1_rounds(frozen)
    vm = metas.get("voting_models") or []
    pass1 = [Answer(rounds[i], "derived", usage=vm[i] if i < len(vm) else {},
                    note="voted rooms with this round's _vote values")
             for i in range(len(rounds))]

    adjacency = Answer(_load(OBJEKTAS_H_CACHED["adjacency"]), "stored",
                       usage=(_extra_calls(frozen, "adjacency") or [{}])[0])
    niche_usage = _extra_calls(frozen, "niche") + [{}, {}]
    niche = [Answer(_load(OBJEKTAS_H_CACHED["niche_primary"]), "stored", usage=niche_usage[0],
                    note="ceiling plan (primary)"),
             Answer(_load(OBJEKTAS_H_CACHED["niche_backfill"]), "stored", usage=niche_usage[1],
                    note="lighting plan (backfill)")]

    zoom_by_nr = {str(r["nr"]): r["_zoom"] for r in frozen.get("patalpos") or [] if r.get("_zoom")}
    zoom_usage = list(_extra_calls(frozen, "zoom"))

    def zoom(kwargs: dict) -> Answer:
        text = " ".join(b.get("text", "") for m in kwargs.get("messages") or []
                        for b in (m.get("content") or []) if isinstance(b, dict))
        found = re.search(r'"nr":\s*"([^"]+)"', text)
        nr = found.group(1) if found else "?"
        usage = zoom_usage.pop(0) if zoom_usage else {}
        if nr in zoom_by_nr:
            return Answer(zoom_by_nr[nr], "stored", usage=usage, note=f"room {nr}")
        return Answer({"patalpa_nr": nr, "confidence_zoom": "low"}, "synthetic", usage=usage,
                      note=f"room {nr}: nothing stored")

    door_type_reads = ((frozen.get("_door_types") or {}).get("_vote") or {}).get("beapvadines_values") or [0, 0, 0]
    dt_usage = _extra_calls(frozen, "door_type") + [{}] * 3
    door_type = [Answer({"doors": [], "beapvadines_count": v, "standartines_count": 0, "stumdomos_count": 0,
                         "bendras_tipas": (frozen.get("_door_types") or {}).get("bendras_tipas")},
                        "derived", usage=dt_usage[i], note="the voted reader count")
                 for i, v in enumerate(door_type_reads)]

    counts = _fixture_counts(meta_log)
    fx_payload = {"prietaisai": copy.deepcopy(frozen.get("_sanitary_prietaisai") or []),
                  **{f"{k}_count": v for k, v in counts.items()}, "pastabos": ""}
    fx_usage = _extra_calls(frozen, "fixtures") + [{}] * 3
    fixtures = [Answer(fx_payload, "derived", usage=fx_usage[i],
                       note="stored enumeration + the voted counts of the run's event log")
                for i in range(3)]

    return {
        "pass1": pass1,
        "adjacency": [adjacency],
        "zoom": zoom,
        "doors": [Answer(_doors_answer(frozen), "derived",
                         usage=(_extra_calls(frozen, "doors") or [{}])[0], note="the doors the merge placed")],
        "door_type": door_type,
        "fixtures": fixtures,
        "niche": niche,
    }
