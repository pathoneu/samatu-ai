"""Narrow Pass-1 (v4, 2026-10-27 — founder decision after the no-vision gate failed).

OFF by default — set `SAMATU_PASS1_NARROW=1` to enable. The flag unset ⇒ nothing changes
(`extract_interior` runs today's full Pass-1 unchanged).

Why: the full Pass-1 on objektas_h costs ~510 s across 3 voting rounds (one 170-s call per round,
~10 000 output tokens each) plus 87 s of zoom that applied 0 refinements, in a prompt that re-asks
for fields the deterministic lanes already read: `plotas_m2`, `perimetras_m`, `lubu_aukstis_m`,
`paskirtis` and all totals. The no-vision route (`extractor/no_vision_route.py`) tried removing
Pass-1 entirely on vector PDFs and failed the gate (totals 57,50 → 65,86 %; row scorecard 32/32 →
25/32) because the per-room OPENING / HIDDEN DOOR / LED NICHE / BUILT-IN / CEILING TYPE fields
only a picture carries went blank. Narrow Pass-1 keeps the picture call but asks for ONLY those
fields; the room list, areas and primitives come from the drawing's text table BEFORE Vision.

Flow:
  1. The sheets' kinds from their text (`text/page_kind.page_kinds`). No `floor_plan` kind ⇒
     fall open: today's Pass-1 Vision runs unchanged, `_meta.pass1_narrow.reason =
     "no_floor_plan_kind"`.
  2. The room table from the drawing's text (`pdfplumber_eksplikacija` → `text.schema_llm`
     fallback). No rows ⇒ fall open: today's Pass-1 Vision runs unchanged,
     `_meta.pass1_narrow.reason = "no_room_list_in_text"`.
  3. Pass-1 ONE round (default) on the floor / ceiling / furniture plans + the door/window
     schedule only (`select_pass1_pages` vendor/photo exclusions on top). The prompt lists every
     table room with `nr + pavadinimas + plotas_m2` and asks for `puslapio_nr`, `bbox_pct`,
     `lubu_tipas`, `elementai[]`, `rasta: bool` per room. `SAMATU_PASS1_NARROW_VOTES=3` brings
     back the voter so the gate script can compare 1 vs 3 rounds.
  4. Merge: `parsed["patalpos"]` is built from the TABLE rooms (areas never move); the model's
     answer writes only `puslapio_nr`, `bbox_pct`, `lubu_tipas`, `elementai`, `_pass1_narrow_rasta`.
  5. Zoom is SKIPPED (areas are table facts; `_meta.zoom_skipped_via_eksplikacija = n_rooms`,
     `zoom_attempted = 0`).
  6. Everything downstream runs exactly as today: drawing lanes, `apply_apdailos`,
     `apply_door_types`, heights, scans, `_recompute_per_room_via_python` (which internally runs
     `reconcile_openings_with_walls` through `universal_rules`), `_build_pozicijos_from_rooms`,
     santrauka, sanity.

Gate (NOT run from this task, no credit for paid runs):
    `scripts/pass1_narrow_gate.sh` reads a fresh extract with `SAMATU_PASS1_NARROW=1` for each of
    the six corpus projects and scores it against the sąmata (`eval_harness.py --totals-only
    --recompute`) and the reading scorecard. Expected runtime arithmetic (objektas_h baseline
    735,4 s): one narrow round ~50–60 s, zoom 0 s, the remaining Vision readers (doors 37,87 s,
    fixtures 20,87 s, door_types 11,37 s) ≈ 70 s → ~150 s total. Estimate — mark it so.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Callable

log = logging.getLogger("samatu.pass1_narrow")

# ─── Flag ─────────────────────────────────────────────────────────────────────
NARROW_ENV = "SAMATU_PASS1_NARROW"
NARROW_VOTES_ENV = "SAMATU_PASS1_NARROW_VOTES"


def narrow_enabled() -> bool:
    """`SAMATU_PASS1_NARROW=1` turns the narrow route on. Any other value or absent ⇒ off."""
    return os.environ.get(NARROW_ENV) == "1"


def narrow_votes() -> int:
    """`SAMATU_PASS1_NARROW_VOTES` (int ≥ 1, default 1) — how many rounds the narrow Pass-1 runs.
    Narrow mode defaults to ONE round regardless of `ENABLE_EXTRACTION_VOTING`."""
    raw = os.environ.get(NARROW_VOTES_ENV)
    if not raw:
        return 1
    try:
        n = int(raw)
    except ValueError:
        return 1
    return max(1, n)


# ─── Sentinel for the fall-open paths ─────────────────────────────────────────
class NarrowFallOpen:
    """`extract_interior_narrow` returned this ⇒ the caller runs today's full Pass-1 Vision and
    stamps the reason on `_meta.pass1_narrow` at the end."""

    __slots__ = ("reason", "meta")

    def __init__(self, reason: str, meta: dict):
        self.reason = reason
        self.meta = meta


# ─── Furniture-plan title (floor_plan + ceiling_plan are kinds already) ───────
# `text/page_kind.py` folds the sheet's text to upper-case ASCII (NFKD, no accents) before matching
# its own title regexes — do the same here. `page_kinds()` returns the matched title words in
# `tekstas` already folded, so we match against that.
_FURNITURE_TITLE_RX = re.compile(r"\bBALD\w*\b.*\b(PLANAS|ISDESTYM|IRANGOS)\b")


# ─── The narrow output schema (TypeScript signature inside the system prompt) ─
NARROW_SCHEMA_KEYS = {
    "patalpos": ("rasta", "puslapio_nr", "bbox_pct", "lubu_tipas", "elementai"),
    "elementai": ("tipas", "kiekis", "plotis_mm", "aukstis_mm", "ilgis_m"),
}


# Lifted verbatim from `prompt.SYSTEM_TEXT` sections <symbol_recognition> (doors, windows, LED
# niches, lubu_tipas) and the bbox_pct guidance. Changes to prompt.py's own texts must be matched
# here; the gate re-runs this prompt whenever the vocabulary moves.
NARROW_SYSTEM_TEXT = """<role>
Tu esi profesionalus Lietuvos vidaus apdailos brėžinių SKAITYTOJAS.

**Patalpų sąrašas ir plotai TAU DUOTI** iš brėžinio paties lentelės — jų NESKAIČIUOK, NEKEISK,
NEPERVADINK. Kiekvienai duotai patalpai paprašoma tik tai, ko DETERMINISTINIS kodas neperskaito iš
teksto ar vektorinės geometrijos:

- `puslapio_nr` + `bbox_pct` — patalpos vieta FLOOR PLAN'e (ne elevation, ne pjūvis, ne mazgas).
- `lubu_tipas` — iš lubų plano arba specifikacijos.
- `elementai[]` — langai, durys (su standart / paslėptos / slankiojamos atskyrimu), LED nišos,
  stoglangiai, kolonos, atsikišimai, built-in spintos. Kiekvienam elementui — matmenys mm (LED
  nišai — ilgis metrais).
- `rasta: false` — jei duotos patalpos negali rasti FLOOR PLAN'e. Nedaryk „geriausio spėjimo"
  tokiais atvejais — grąžink `rasta: false` ir tuščius laukus.

Jei duotos patalpos TAVO ĮVESTYJE nematyti (pvz. jos planas buvo nuleistas iš įvesties) — tai yra
`rasta: false`, ne klaida.

Atsakyk **TIK** JSON pagal pateiktą schemą. Jokio paaiškinimo, jokio markdown.
</role>

<symbol_recognition>

**Durys (plan view):**
- Standartinės atdaromosios: ketvirčio apskritimo lankas + plonas stačiakampis (varčia). Tipas `duris`.
- Slankiojamosios: stačiakampis + brūkšninis stačiakampis (kelio padėtis), nėra lanko. Tipas `duris`
  (varčios tipas durų žiniaraščio lentelėje).
- Paslėptos (beapvadinės): paprastas tarpas sienoje BE lanko, žymėjimas "beapvadinės" / "paslėptos".
  Tipas `pasleptos_duris`.
- Anotacija greta: `900×2100` = 900mm × 2100mm.

**Langai (plan view):**
- Dvi paralelinės linijos kertančios sienos storį. Tipas `langas`.
- Diagonalė per langą = atidaroma dalis (X = abi atidaromos).
- Stoglangis: stačiakampis su X-diagonalėmis **LUBŲ PLANE** (NE sienos plane). Tipas `stoglangis`.
- Anotacija: `1200×1500` = 1200mm × 1500mm.

**LED nišos lubų plane (TIK iš LUBŲ PLANO):**
- **RAUDONA stačiakampė linija lubų plane** = LED juosta (LT industry konvencija, labai stabili).
- B&W brėžiniuose: ploni dvigubi stačiakampiai + žymėjimas "LED juosta" / "LED nišelė" / "el. nišelė".
- Gylis 80–120mm; aukštis 50–80mm.
- Tipas `nisa_LED`, `ilgis_m` = bendras nišų ilgis šioje patalpoje metrais, visų atkarpų suma
  (NE vienos atkarpos; NE mm) — susumuok ilgį visų atkarpų.

**Built-in spintos (baldų plane):**
- Užbrūkšniuotas / užpildytas stačiakampis prie sienos su žymėjimu "DRABUŽINĖ" / "SPINTA" /
  "RK" / "Baldai". Tipas `spinta_built_in`. Reikalingas tik tada, kai jis dengia SIENĄ ir todėl
  sumažina dažomą plotą — jei stovi atskirai ant grindų, NEĮSKAITYK.

**Kolonos ir atsikišimai:**
- `kolona` — atskiras stačiakampis / apskritimas erdvės viduryje, nejungiamas su siena.
- `atsikismas` — vidinis sienos atsikišimas (siena su atsikišimu į patalpą), ne durys / langas.

**`lubu_tipas` enum:**
- `gkp` — GK lubos su dvigubo karkaso žymėjimu lubų plane (default modern LT).
- `betonas` — atviras betonas (tambūras, garažas, tech).
- `pakabinamos` — matomas "pakabinamos lubos" žymėjimas (komercinės).
- `tempiamos` — tempiamos lubos (premium).

Jei lubų tipo nematai — grąžink `null`.

</symbol_recognition>

<bbox_pct>
`bbox_pct` PRIVALO būti TIK floor plan'o vietoje (kambarys iš viršaus su sienomis). Jei tas pats
kambario pavadinimas matosi keliose vietose (floor plan + elevation + mazgas + eksplikacija +
baldų plane) — pasirink TIK floor plan instance'ą. Jis atpažįstamas iš:
- Sienos nupieštos kaip dvi lygiagrečios linijos (storis 100-300 mm).
- Yra langų ir durų tarpai sienose.
- Yra dimension chain'ai aplink (matmenys mm).
- NĖRA tekstinių aprašymų ar baldų vidaus detalių.

Jei patalpa nematoma jokiame floor plan'e — grąžink `rasta: false, puslapio_nr: null, bbox_pct: null`.
`bbox_pct` koordinatės yra 0.0-1.0 fractions nuo puslapio kairio viršaus (top-left origin:
y=0 viršuje, y=1 apačioje). Apima TIK PATALPĄ (visas sienas), su ~5-10% papildomu plotu kad būtų
matoma dimension chains.
</bbox_pct>

<output_schema>
```typescript
type Output = {
  patalpos: Room[];
};
type Room = {
  nr: string;              // DUOTAS iš lentelės — pakartok lygiai
  rasta: boolean;          // ar šią patalpą radai FLOOR PLAN'e
  puslapio_nr: number | null;
  bbox_pct: {x: number, y: number, w: number, h: number} | null;
  lubu_tipas: "gkp" | "betonas" | "pakabinamos" | "tempiamos" | null;
  elementai: Element[];
};
type Element = {
  tipas: "langas" | "duris" | "pasleptos_duris" | "nisa_LED" | "stoglangis"
       | "spinta_built_in" | "kolona" | "atsikismas";
  kiekis: number;
  plotis_mm?: number;
  aukstis_mm?: number;
  ilgis_m?: number;        // TIK `nisa_LED` — bendras nišų ilgis šioje patalpoje metrais, visų atkarpų suma, NE vienos atkarpos
};
```

NIEKADA negrąžink markdown fences ar prozos. NIEKADA negrąžink `plotas_m2`, `perimetras_m`,
`lubu_aukstis_m`, `paskirtis`, `pastabos`, `confidence`, `warnings`, `santrauka`, `pozicijos`,
`puslapiai`, `durys_total`, `langai_total` ar `detected_symbols_summary` — jų kodas neprašo. Tik
`patalpos` lauką pateiktos struktūros.
</output_schema>
"""


NARROW_MAX_OUTPUT_TOKENS = 16000       # today's full prompt uses 64 000 — narrow asks for ~3 000
NARROW_VISION_TIMEOUT_S = 600.0


# ─── Entry probe + fall-open sentinels ────────────────────────────────────────
def _page_kinds(pdf_bytes: bytes) -> list[dict]:
    """Thin wrapper over `text/page_kind.page_kinds` — swallows every exception and returns `[]`,
    so a crashing kind classifier falls open to today's Pass-1 Vision rather than killing the
    extraction."""
    try:
        from text.page_kind import page_kinds
        return page_kinds(pdf_bytes) or []
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: page_kinds failed: %r", exc)
        return []


def _narrow_kinds(kinds: list[dict]) -> tuple[set[int], list[int], bool]:
    """`(kept_pages, dropped_pages, has_floor_plan)` — the narrow page set:
    floor_plan + ceiling_plan + furniture-plan-title + door_window_schedule.

    `tekstas` is the folded title the text layer gave; the furniture branch exists because
    page_kind's floor_plan regex already catches „BALDU PLANAS" / „BALDU ISDESTYM" but NOT a title
    that only says „BALDU IR IRANGOS PLANAS" (no clear PLANAS/ISDESTYM at the right position).
    """
    kept: set[int] = set()
    dropped: list[int] = []
    has_floor = False
    for k in kinds:
        tipas = str(k.get("tipas") or "").strip()
        tekstas = str(k.get("tekstas") or "")
        try:
            nr = int(k.get("nr"))
        except (TypeError, ValueError):
            continue
        if tipas == "floor_plan":
            kept.add(nr)
            has_floor = True
            continue
        if tipas == "ceiling_plan":
            kept.add(nr)
            continue
        if tipas == "door_window_schedule":
            kept.add(nr)
            continue
        if tekstas and _FURNITURE_TITLE_RX.search(tekstas):
            kept.add(nr)
            continue
        dropped.append(nr)
    return kept, dropped, has_floor


def _read_table_rooms(pdf_bytes: bytes, client) -> tuple[list[dict], dict]:
    """`(rooms, eks)` — the drawing's own room table.

    First `pdfplumber_eksplikacija.extract_eksplikacija_pdfplumber` (deterministic $0). When
    pdfplumber refuses (ambiguous columns, no header) and a client is given, fall back to the
    eksplikacija page's TEXT through `text.schema_llm.structure` (one text-schema model call,
    substring-guarded — a value whose source_text is not in the input is REFUSED; the model never
    sees the sheet). The two helpers are the ones `no_vision_route` built; this reuses the same
    public names rather than copying the bodies.
    """
    try:
        from .pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber
        eks = extract_eksplikacija_pdfplumber(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: pdfplumber eksplikacija failed: %r", exc)
        eks = {"patalpos": [], "schedule_tables": {"durys": [], "langai": []},
               "_meta": {"source": "pdfplumber_table"}}

    if not (eks.get("patalpos") or []):
        try:
            from .no_vision_route import eksplikacija_from_text_schema
            alt = eksplikacija_from_text_schema(pdf_bytes, client)
            if alt and alt.get("patalpos"):
                log.info("pass1_narrow: eksplikacija from text.schema_llm (%s rooms, p%s)",
                         len(alt["patalpos"]), alt.get("eksplikacija_source_page"))
                # tally the schema_llm call so the per-user spend cap sees it
                try:
                    from . import run_usage as _run_usage
                    _run_usage.note((alt.get("_meta") or {}))
                except Exception as exc:  # noqa: BLE001
                    log.debug("pass1_narrow: eksplikacija run_usage.note failed: %r", exc)
                prev_meta = eks.get("_meta") or {}
                eks = {**alt}
                eks["_meta"] = {**(alt.get("_meta") or {}), "pdfplumber_refused": {
                    k: prev_meta.get(k) for k in ("ambiguous_rows", "eksplikacija_pages_found",
                                                   "tables_examined", "wide_acceptance")}}
        except Exception as exc:  # noqa: BLE001
            log.warning("pass1_narrow: text-schema eksplikacija fallback failed: %r", exc)

    try:
        from .no_vision_route import rooms_from_table
        rooms = rooms_from_table(eks)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: rooms_from_table failed: %r", exc)
        rooms = []
    return rooms, eks


# ─── Narrow prompt builder ────────────────────────────────────────────────────
def build_narrow_user_content(pages: list[dict], table_rooms: list[dict]) -> list[dict]:
    """User content for the narrow Pass-1: images, cache break on the last image, THEN the room
    list and the final instruction. Images sit in the stable prefix so voting rounds (if the
    `*_VOTES=3` lever is on) can share the prompt cache the same way today's full prompt does.
    """
    n = len(pages)
    content: list[dict] = []
    for p in pages:
        content.append({"type": "text",
                        "text": f"Page {p['page_index']} of {n}:"})
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg",
                                   "data": p["image_b64"]}})
    if content and content[-1].get("type") == "image":
        content[-1]["cache_control"] = {"type": "ephemeral"}

    # The TABLE's own identifiers — the model must copy nr back exactly. plotas_m2 is given so
    # the model knows the room's size without being asked to re-read it; it also lets the model
    # discriminate between two rooms with the same name but different plotai.
    rows = [{"nr": r.get("nr"), "pavadinimas": r.get("pavadinimas"),
             "plotas_m2": r.get("plotas_m2")} for r in table_rooms if isinstance(r, dict)]
    content.append({
        "type": "text",
        "text": (
            "Patalpų sąrašas iš brėžinio paties lentelės — tai faktai, jų neperskaityk ir "
            "nekurk naujų. Grąžink po VIENĄ patalpos įrašą kiekvienai iš šių eilučių "
            "(net ir toms, kurių FLOOR PLAN'e nerandi — joms grąžink `rasta: false`).\n\n"
            f"```json\n{json.dumps(rows, ensure_ascii=False)}\n```\n\n"
            "Kiekvienai patalpai perskaityk: `puslapio_nr`, `bbox_pct`, `lubu_tipas`, "
            "`elementai[]` (langai, durys, paslėptos durys, LED nišos, stoglangiai, kolonos, "
            "atsikišimai, built-in spintos). "
            "Grąžink VIENĄ JSON objektą pagal pateiktą schemą."
        ),
    })
    return content


# ─── Single-round narrow call ─────────────────────────────────────────────────
def _run_narrow_once(client, system, user_content, *, model: str) -> dict:
    """One narrow Pass-1 call (≤2 retries). Returns `parsed` or an error dict.

    Mirrors `_run_pass1_once`'s shape but without the native-PDF path (narrow mode currently
    sends images only — the native-PDF path is unaffected by narrow mode's smaller prompt and
    adds a second axis to the gate measurement for no clear win). Pricing lands in `_meta` the
    same way, so the per-user cap sees the narrow call.
    """
    import anthropic
    from .vision_call import _repair_json
    from . import run_usage as _run_usage

    last_err: Exception | None = None
    truncated_metas: list[dict] = []

    def _with_truncated(meta: dict) -> dict:
        if truncated_metas:
            for _k in ("input_tokens", "output_tokens",
                       "cache_read_tokens", "cache_write_tokens"):
                meta[_k] = int(meta.get(_k) or 0) + sum(
                    int(tm.get(_k) or 0) for tm in truncated_metas)
            meta["truncated_attempts"] = [
                {_k: tm.get(_k) for _k in ("input_tokens", "output_tokens",
                                            "cache_read_tokens", "cache_write_tokens",
                                            "stop_reason", "attempt")}
                for tm in truncated_metas]
        return meta

    max_attempts = 3
    attempt = 0
    while attempt < max_attempts:
        try:
            with client.with_options(timeout=NARROW_VISION_TIMEOUT_S).messages.stream(
                model=model,
                max_tokens=NARROW_MAX_OUTPUT_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_content}],
                output_config={"effort": "high"},
            ) as stream:
                resp = stream.get_final_message()

            usage = getattr(resp, "usage", None)
            meta = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0),
                "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0),
                "stop_reason": resp.stop_reason,
                "attempt": attempt + 1,
                "pages_sent": None,                 # the caller fills these in
                "model": model,
                "pass": "narrow",
            }
            _run_usage.note(meta)

            if resp.stop_reason == "refusal":
                return {"status": "error", "_error": "model_refused",
                        "_stop_reason": "refusal", "_meta": _with_truncated(meta)}
            if resp.stop_reason == "max_tokens":
                if not truncated_metas:
                    truncated_metas.append(meta)
                    log.warning("pass1_narrow: answer cut off at max_tokens=%s "
                                "(output_tokens=%s) — one more try",
                                NARROW_MAX_OUTPUT_TOKENS, meta.get("output_tokens"))
                    continue
                return {"status": "error", "_error": "output_truncated",
                        "_stop_reason": "max_tokens", "_meta": _with_truncated(meta)}

            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(_repair_json(text))
                    parsed["_repaired"] = True
                except json.JSONDecodeError as je:
                    return {"status": "error", "_error": "json_decode_failure",
                            "_raw_text": text[:4000], "_je": str(je),
                            "_meta": _with_truncated(meta)}

            parsed["_meta"] = _with_truncated(meta)
            parsed["status"] = "ok"
            return parsed
        except Exception as exc:
            last_err = exc
            log.warning("pass1_narrow: attempt %s failed: %r", attempt + 1, exc)
            attempt += 1
            if attempt >= max_attempts:
                out = {"status": "error", "_error": f"narrow_call_failed: {exc}"}
                if truncated_metas:
                    out["_meta"] = _with_truncated({"model": model, "pass": "narrow"})
                return out
            time.sleep(1.5 ** (attempt - 1))

    out = {"status": "error", "_error": str(last_err or "Unknown error")}
    if truncated_metas:
        out["_meta"] = _with_truncated({"model": model, "pass": "narrow"})
    return out


def _run_narrow_voted(client, system, user_content, votes, *, model: str, emit) -> dict:
    """`votes` rounds of narrow Pass-1 + median voting. Byte-identical prompts across rounds →
    cache-friendly (the images sit in the stable prefix). Degrades gracefully: 0 good runs →
    error; 1 good run → that run."""
    from .vision.extraction_voter import vote_extraction

    runs: list[dict] = []
    per_round_meta: list[dict] = []
    for i in range(votes):
        emit({"event": "voting_round_started", "round": i + 1, "of": votes, "model": model,
              "pass": "narrow"})
        res = _run_narrow_once(client, system, user_content, model=model)
        per_round_meta.append(res.get("_meta") or {})
        if res.get("status") == "ok":
            runs.append(res)
            emit({"event": "voting_round_completed", "round": i + 1, "of": votes,
                  "rooms": len(res.get("patalpos") or [])})
        else:
            emit({"event": "voting_round_failed", "round": i + 1, "error": res.get("_error")})

    if not runs:
        return {"status": "error", "_error": "all_narrow_rounds_failed",
                "_meta": {"model": model, "pass": "narrow",
                          "per_round": per_round_meta}}
    if len(runs) == 1:
        runs[0].setdefault("_meta", {})["narrow_votes_effective"] = 1
        runs[0]["_meta"]["narrow_per_round"] = per_round_meta
        return runs[0]

    voted = vote_extraction(runs)
    # Keep the first run's `_meta` (tokens, model) as the base; add narrow-specific markers and
    # fold the other rounds' token counts in.
    base_meta = dict(runs[0].get("_meta") or {})
    for extra in per_round_meta[1:]:
        for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
            base_meta[k] = int(base_meta.get(k) or 0) + int(extra.get(k) or 0)
    base_meta["narrow_votes_effective"] = len(runs)
    base_meta["narrow_per_round"] = per_round_meta
    voted["_meta"] = base_meta
    voted["status"] = "ok"
    return voted


# ─── Merge: write model fields onto table rooms ───────────────────────────────
_ELEMENT_TIPAI = {"langas", "duris", "pasleptos_duris", "nisa_LED", "stoglangis",
                  "spinta_built_in", "kolona", "atsikismas"}
_LUBU_TIPAI = {"gkp", "betonas", "pakabinamos", "tempiamos"}


def _clean_element(e: Any) -> dict | None:
    if not isinstance(e, dict):
        return None
    tipas = str(e.get("tipas") or "").strip()
    if tipas not in _ELEMENT_TIPAI:
        return None
    try:
        kiekis = int(e.get("kiekis") or 0)
    except (TypeError, ValueError):
        kiekis = 0
    if kiekis <= 0:
        return None
    out: dict = {"tipas": tipas, "kiekis": kiekis}
    for key in ("plotis_mm", "aukstis_mm", "ilgis_m"):
        v = e.get(key)
        if v is None:
            continue
        try:
            out[key] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _clean_bbox(bb: Any) -> dict | None:
    if not isinstance(bb, dict):
        return None
    try:
        return {k: float(bb.get(k)) for k in ("x", "y", "w", "h")}
    except (TypeError, ValueError):
        return None


def _mark_room_not_found(parsed, room, nr):
    '''Mark a table room as not found on the floor plan.

    Shared by the rasta-false path and the omitted-room path (rooms the model
    did not mention at all).
    '''
    room['_pass1_narrow_rasta'] = False
    pavadinimas = room.get('pavadinimas') or nr
    room['_kilme'] = (
        'Patalpa „' + pavadinimas + '“ (' + nr + ') '
        'neatpažinta brėžinio aukšto plane — '
        'patikrinkite brėžinio puslapį su šios patalpos vieta, '
        'kad atpažintų langus, duris ir nišas.'
    )
    parsed.setdefault('warnings', []).append({
        'level': 'WARN',
        'code': 'pass1_narrow_room_not_on_plan',
        'patalpa_nr': nr,
        'message': (
            'Patalpos „' + pavadinimas + '“ (' + nr + ') '
            'brėžinio aukšto plane rasti nepavyko — langai, durys ir '
            'lubų nišos liko neperskaityti. Patikrinkite patalpą Patikros žingsnyje.'
        ),
    })

def merge_narrow(parsed: dict, model_result: dict, table_rooms: list[dict]) -> int:
    """Build `parsed["patalpos"]` from table rooms and apply the model's narrow answer per nr.

    Returns the number of rooms the model MARKED as found on the plan (`rasta: true`). Rooms
    the model marked `rasta: false`, and rooms the model did not mention at all, keep their table
    row and carry an LT sentence in `_kilme` and a WARN so the user is told what to check.
    """
    parsed["patalpos"] = list(table_rooms)
    by_nr = {str(r.get("nr") or "").strip(): r for r in parsed["patalpos"]}

    found = 0
    model_rooms = (model_result or {}).get("patalpos") or []
    for m in model_rooms:
        if not isinstance(m, dict):
            continue
        nr = str(m.get("nr") or "").strip()
        if not nr or nr not in by_nr:
            continue
        room = by_nr[nr]
        rasta = bool(m.get('rasta'))
        if not rasta:
            _mark_room_not_found(parsed, room, nr)
            continue
        room['_pass1_narrow_rasta'] = True
        found += 1
        # The model's own placement on the floor plan — reused by Patikra (click-to-pan) and by
        # the geometry lane as a hint when the drawn outline needs a bbox anchor.
        try:
            pn = int(m.get("puslapio_nr"))
            room["puslapio_nr"] = pn
        except (TypeError, ValueError):
            pass
        bbox = _clean_bbox(m.get("bbox_pct"))
        if bbox is not None:
            room["bbox_pct"] = bbox
        lubu = str(m.get("lubu_tipas") or "").strip()
        if lubu in _LUBU_TIPAI:
            room["lubu_tipas"] = lubu
        elems = [e for e in (_clean_element(e) for e in (m.get("elementai") or [])) if e]
        if elems:
            room["elementai"] = elems

    # Rooms the model did not mention at all are treated the same as rasta: false.
    for nr, room in by_nr.items():
        if "_pass1_narrow_rasta" not in room:
            _mark_room_not_found(parsed, room, nr)

    return found


# ─── The full extract (mirror of extract_interior_no_vision + narrow Vision) ──
def extract_interior_narrow(
    pdf_bytes: bytes,
    rules_override: dict | None = None,
    progress_cb: Callable[[dict], None] | None = None,
) -> dict | NarrowFallOpen:
    """Narrow-mode entry. Returns a parsed dict on success, or `NarrowFallOpen` if either gate
    fails (`extract_interior` then runs today's full Pass-1 and stamps the reason).
    """
    import anthropic

    t0 = time.time()

    def _emit(ev: dict) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(ev)
        except Exception as exc:  # noqa: BLE001
            log.debug("pass1_narrow: progress_cb raised: %r", exc)

    # Step 1 — page kinds. No `floor_plan` kind ⇒ fall open.
    kinds = _page_kinds(pdf_bytes)
    if not kinds:
        return NarrowFallOpen("no_floor_plan_kind",
                              {"status": "fell_open", "reason": "no_floor_plan_kind",
                               "sentence": "Lapų rūšių tekste nerasta — paliekamas pilnas vaizdo skaitymas"})
    narrow_pages, dropped_pages, has_floor = _narrow_kinds(kinds)
    if not has_floor:
        return NarrowFallOpen("no_floor_plan_kind",
                              {"status": "fell_open", "reason": "no_floor_plan_kind",
                               "sentence": "Aukšto plano brėžinio puslapio neradom — paliekamas pilnas vaizdo skaitymas",
                               "pages_dropped_by_kind": dropped_pages})

    # Step 2 — the room table. No rows ⇒ fall open.
    try:
        client = anthropic.Anthropic(max_retries=1)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: anthropic client not available: %r", exc)
        client = None

    table_rooms, eks = _read_table_rooms(pdf_bytes, client)
    if not table_rooms:
        return NarrowFallOpen("no_room_list_in_text",
                              {"status": "fell_open", "reason": "no_room_list_in_text",
                               "sentence": "Patalpų eksplikacijos lentelė nerasta — paliekamas pilnas vaizdo skaitymas"})

    # From here on, narrow is committed. Everything below mirrors the Vision route's tail except
    # for the Pass-1 call itself (narrower prompt + schema + no zoom).
    from models_config import model_for
    from .prompt import SYSTEM_TEXT as _FULL_SYSTEM_TEXT  # noqa: F401 — proves the import path
    from .vision_call import (
        pdf_to_b64_images,
        apply_apdailos,
        apply_door_types,
        _recompute_per_room_via_python,
        _build_pozicijos_from_rooms,
        _recompute_santrauka,
        _emit_v8_compat_fields,
        _append_extra_call,
        _apply_schedule_match,
        DPI,
    )
    from .page_filter import select_pass1_pages
    from . import run_usage as _run_usage
    from . import scope as _scope
    from . import row_provenance as _rp

    sentence = ("Patalpų sąrašas iš brėžinio lentelės; vaizdo modelis skaito tik langus, duris, "
                "nišas ir lubas")
    _emit({"event": "route_selected", "route": "vision_narrow", "sentence": sentence})

    # Step 3 — render + page selection (vendor / photo exclusions on top of the narrow kinds).
    _emit({"event": "rendering_pdf"})
    try:
        pages = pdf_to_b64_images(pdf_bytes)
    except Exception as exc:
        log.warning("pass1_narrow: pdf render failed: %r", exc)
        _emit({"event": "error", "message": "Nepavyko perskaityti PDF failo."})
        return {"status": "error", "_error": f"pdf_render_failed: {exc}"}
    if not pages:
        _emit({"event": "error", "message": "PDF has no renderable pages"})
        return {"status": "error", "_error": "PDF has no renderable pages"}

    n_pdf_pages = len(pages)

    page_selection_meta: dict | None = None
    try:
        selection = select_pass1_pages(pdf_bytes, pages)
        page_selection_meta = selection.meta()
        vendor_photo_skipped = set(selection.skipped)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: page selection failed: %r", exc)
        vendor_photo_skipped = set()

    pages_sent = [p for p in pages
                  if p["page_index"] in narrow_pages and p["page_index"] not in vendor_photo_skipped]
    if not pages_sent:
        # Narrow pages ∩ (not vendor/photo) is empty — fall open rather than send nothing.
        return NarrowFallOpen("no_narrow_pages_after_filter",
                              {"status": "fell_open", "reason": "no_narrow_pages_after_filter",
                               "sentence": "Siauram vaizdo skaitymui tinkamų brėžinio puslapių neliko — "
                                           "paliekamas pilnas vaizdo skaitymas",
                               "pages_dropped_by_kind": dropped_pages})

    # Step 4 — build the parsed shell with table rooms (areas never move from here).
    parsed: dict = {
        "status": "ok",
        "patalpos": [],
        "puslapiai": [],
        "warnings": [],
        "pozicijos": [],
        "_meta": {
            "vision_pass": "narrow",
            "route": "vision_narrow",
            "route_sakinys": sentence,
            "n_pdf_pages": n_pdf_pages,
        },
    }
    if page_selection_meta:
        parsed["_meta"]["page_selection"] = page_selection_meta

    _emit({"event": "started", "page_count": len(pages_sent), "voting": narrow_votes() > 1,
           "route": "vision_narrow"})
    _emit({"event": "pass1_started", "page_count": len(pages_sent), "voting": narrow_votes() > 1,
           "pass": "narrow"})

    # Step 5 — the narrow Vision call.
    system = [{"type": "text", "text": NARROW_SYSTEM_TEXT,
               "cache_control": {"type": "ephemeral"}}]
    user_content = build_narrow_user_content(pages_sent, table_rooms)
    model = model_for("vision_pass1")
    t_pass1 = time.time()
    votes = narrow_votes()
    if votes > 1:
        model_result = _run_narrow_voted(client, system, user_content, votes,
                                         model=model, emit=_emit)
    else:
        model_result = _run_narrow_once(client, system, user_content, model=model)
    pass1_elapsed = round(time.time() - t_pass1, 2)

    if model_result.get("status") == "error":
        _emit({"event": "error", "message": str(model_result.get("_error"))})
        # The call was billed in full — fold tokens into the meta so pricing counts them, then
        # fail out just like the Vision route does.
        _append_extra_call(parsed, model_result.get("_meta"), reader="pass1_narrow")
        parsed["status"] = "error"
        parsed["_error"] = model_result.get("_error") or "narrow_call_failed"
        return parsed

    # Step 6 — merge table rooms + model answer.
    pages_sent_list = [p["page_index"] for p in pages_sent]
    narrow_meta = model_result.get("_meta") or {}
    narrow_meta["pages_sent"] = pages_sent_list
    model_result["_meta"] = narrow_meta
    _append_extra_call(parsed, narrow_meta, reader="pass1_narrow")

    found = merge_narrow(parsed, model_result, table_rooms)

    rooms = parsed["patalpos"]
    parsed["_eksplikacija"] = eks
    parsed["eksplikacija_source_page"] = eks.get("eksplikacija_source_page")
    parsed["bendras_plotas_m2"] = round(
        sum(float(r.get("plotas_m2") or 0) for r in rooms if isinstance(r, dict)), 2)

    # The TABLE is the room list — stop every later identity reconciler from running.
    parsed["_meta"]["kambariu_tapatybe"] = {
        "saltinis": "lentele",
        "lenteles_eilutes": len(rooms),
        "sutapo": found,
        "tik_lenteleje": len(rooms) - found,
        "atmesta": [],
        "perkeisti_numeriai": {},
    }
    parsed["_meta"]["eksplikacija_merged_rooms"] = len(rooms)
    parsed["_meta"]["eksplikacija_total_rows"] = len(rooms)

    # Ceiling anchor from the table's own total / rows sum (same logic no_vision_route uses — the
    # table IS the room list; the eksplikacija guard never runs on this route).
    _eks_meta = eks.get("_meta") or {}
    if _eks_meta.get("total_area_m2"):
        parsed["_ceiling_anchor"] = {
            "total_area_m2": _eks_meta["total_area_m2"],
            "label": _eks_meta.get("total_row_label") or "Iš viso",
            "page": _eks_meta.get("total_row_page"),
        }
    else:
        rows_sum = round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2)
        if rows_sum > 0:
            parsed["_ceiling_anchor"] = {
                "total_area_m2": rows_sum, "label": "patalpų plotų suma",
                "page": _eks_meta.get("source_page") or eks.get("eksplikacija_source_page"),
            }

    _emit({"event": "pass1_completed", "rooms_count": len(rooms),
           "pass": "narrow",
           "patalpos": [{"nr": r.get("nr"), "pavadinimas": r.get("pavadinimas"),
                         "paskirtis": r.get("paskirtis"), "plotas_m2": r.get("plotas_m2"),
                         "puslapio_nr": r.get("puslapio_nr")} for r in rooms]})

    # Step 7 — Pass-1 narrow meta (stamped on `_meta.pass1_narrow` so the gate reader can tell
    # today's full run from a narrow run at a glance).
    pass1_narrow_meta = {
        "status": "narrow",
        "rooms_from_table": len(rooms),
        "rooms_marked_rasta": found,
        "pages_sent": pages_sent_list,
        "pages_dropped_by_kind": dropped_pages,
        "votes": votes,
        "votes_effective": int(narrow_meta.get("narrow_votes_effective") or 1),
        "output_tokens": int(narrow_meta.get("output_tokens") or 0),
        "input_tokens": int(narrow_meta.get("input_tokens") or 0),
        "cache_read_tokens": int(narrow_meta.get("cache_read_tokens") or 0),
        "cache_write_tokens": int(narrow_meta.get("cache_write_tokens") or 0),
        "elapsed_s": pass1_elapsed,
    }
    parsed["_meta"]["pass1_narrow"] = pass1_narrow_meta

    # Step 8 — schedule-table anchoring for window / door dimensions (same shape the Vision
    # route runs). Narrow mode's model also emits elementai with mm sizes; the schedule tables
    # from `extract_eksplikacija_pdfplumber` carry the exact dimensions, so matching tightens
    # them exactly like the full route does.
    try:
        sched = (eks.get("schedule_tables") or {})
        sched_langai = sched.get("langai") or []
        sched_durys = sched.get("durys") or []
        DIM_TOL_MM = 50

        def _match(elem_w, elem_h, candidates):
            if not elem_w or not elem_h:
                return None
            best, best_dist = None, DIM_TOL_MM + 1
            for s in candidates:
                sw, sh = s.get("plotis_mm"), s.get("aukstis_mm")
                if not sw or not sh:
                    continue
                d = abs(sw - elem_w) + abs(sh - elem_h)
                if d < best_dist:
                    best, best_dist = s, d
            return best if best_dist <= DIM_TOL_MM * 2 else None

        anchored = 0
        for room in rooms:
            for elem in (room.get("elementai") or []):
                tipas = elem.get("tipas")
                ew, eh = elem.get("plotis_mm"), elem.get("aukstis_mm")
                if tipas in ("langas", "stoglangis"):
                    matched = _match(ew, eh, sched_langai)
                    if matched:
                        _apply_schedule_match(elem, matched)
                        anchored += 1
                elif tipas in ("duris", "pasleptos_duris"):
                    matched = _match(ew, eh, sched_durys)
                    if matched:
                        _apply_schedule_match(elem, matched)
                        anchored += 1
        parsed["_meta"]["schedule_anchored_elements"] = anchored
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: schedule anchor merge failed: %r", exc)

    # Step 9 — zoom is SKIPPED (areas are table facts).
    n_rooms = len(rooms)
    _emit({"event": "zoom_started", "total": 0, "skipped": True,
           "note": "patalpų plotai iš brėžinio lentelės",
           "skipped_via_eksplikacija": n_rooms})
    _emit({"event": "zoom_completed", "attempted": 0, "applied": 0,
           "skipped_via_eksplikacija": n_rooms, "elapsed_s": 0.0, "skipped": True})
    parsed["_meta"]["zoom_attempted"] = 0
    parsed["_meta"]["zoom_applied"] = 0
    parsed["_meta"]["zoom_elapsed_s"] = 0.0
    parsed["_meta"]["zoom_skipped_via_eksplikacija"] = n_rooms

    # Step 10 — the drawing's €0 lanes (page kinds applied, text scan + anchors, dimension pairs,
    # raster outlines, heights, vector geometry, legend counts). Shared with the Vision route.
    from .drawing_lanes import run_drawing_lanes
    try:
        run_drawing_lanes(parsed, pdf_bytes, emit=_emit)
    except Exception as exc:  # noqa: BLE001
        log.exception("pass1_narrow: drawing lanes failed: %r", exc)
        parsed.setdefault("warnings", []).append({
            "level": "WARN",
            "message": ("Brėžinio skaitymo takeliai nenurodyti — kiekiai gali būti netikslūs. "
                        "Patikrinkite patalpas Patikros žingsnyje."),
        })

    # Step 11 — wall finishes (apply_apdailos: text layer / OCR, a schema_llm text call allowed).
    try:
        _emit({"event": "apdailos_started"})
        apdailos_result = apply_apdailos(parsed, pdf_bytes, client=client)
        _append_extra_call(parsed, apdailos_result.get("_meta"), reader="apdailos")
        _emit({"event": "apdailos_completed" if apdailos_result.get("status") == "ok" else "apdailos_skipped",
               "page": apdailos_result.get("page"), "status": apdailos_result.get("status"),
               "rooms_updated": (parsed.get("_meta") or {}).get("apdailos_rooms_updated"),
               "reason": apdailos_result.get("_error")})
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: apdailos failed: %r", exc)
        _emit({"event": "apdailos_error", "message": str(exc)})

    # Step 12 — door types from the drawing's text (no model).
    try:
        _emit({"event": "door_types_started"})
        dt = apply_door_types(parsed, pdf_bytes)
        if dt.get("status") == "ok":
            _dtt = parsed.get("_door_types") or {}
            _emit({"event": "door_types_completed", "frameless": _dtt.get("count"),
                   "confidence": _dtt.get("confidence"),
                   "reader": dt.get("beapvadines_count"), "tagged": 0})
        else:
            _emit({"event": "door_types_skipped", "reason": dt.get("_error")})
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: door types failed: %r", exc)
        _emit({"event": "door_types_error", "message": str(exc)})

    # Step 13 — ceiling heights from the drawing's text (shared helper).
    try:
        n_h = _rp.fill_heights_from_read(parsed.get("patalpos") or [], parsed)
        if n_h:
            parsed["_meta"]["aukstis_is_brezinio"] = n_h
            _emit({"event": "heights_from_drawing", "rooms_changed": n_h})
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: height fill failed: %r", exc)

    # Step 14 — tile mentions, symbol legend, door schedule, vector symbols (all deterministic $0).
    try:
        from .plyteliu_specifikacija import extract_plyteliu_specifikacija, RELEVANT_PAGE_TYPES
        relevant = [p["nr"] for p in (parsed.get("puslapiai") or [])
                    if isinstance(p, dict) and p.get("tipas") in RELEVANT_PAGE_TYPES]
        plyt = extract_plyteliu_specifikacija(pdf_bytes, relevant_pages=relevant or None)
        parsed["_plyteliu_specs"] = plyt.get("tile_specs", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: plyteliu_specifikacija failed: %r", exc)
    try:
        from .symbol_legend import scan_symbol_legend
        parsed["_symbol_legend"] = scan_symbol_legend(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: symbol legend scan failed: %r", exc)
    try:
        from .door_schedule import scan_door_schedule
        parsed["_duru_ziniarastis"] = scan_door_schedule(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: door schedule scan failed: %r", exc)
    try:
        from .vector_symbols import scan_vector_symbols
        parsed["_vector_symbols"] = scan_vector_symbols(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: vector symbol scan failed: %r", exc)

    # Step 15 — the per-room Python math (`reconcile_openings_with_walls` runs inside it) and
    # the sąmata rows.
    _emit({"event": "post_processing"})
    try:
        parsed = _recompute_per_room_via_python(parsed, rules_override)
        _emit({"event": "python_math_completed", "rooms_computed": len(parsed.get("patalpos") or [])})
    except Exception as exc:  # noqa: BLE001
        log.exception("pass1_narrow: per-room recompute failed: %r", exc)
        parsed.setdefault("warnings", []).append({
            "level": "WARN",
            "message": ("Patalpų kiekių apskaičiuoti nepavyko — kiekiai gali būti neišsamūs. "
                        "Patikrinkite patalpų kiekius Patikros žingsnyje."),
        })

    try:
        if rules_override is not None:
            parsed["_overrides"] = rules_override
        _apimtis = _scope.normalize_apimtis(_scope.with_profile_defaults(
            (rules_override or {}).get("apimtis"), rules_override))
        _scope.mark_rooms(parsed.get("patalpos") or [], _apimtis)
        if _apimtis:
            parsed["_apimtis"] = _apimtis
            _scope.apply_ceiling_choice(parsed.get("patalpos") or [], _apimtis)
        parsed = _build_pozicijos_from_rooms(parsed)
        if _apimtis:
            parsed["pozicijos"] = _scope.filter_rows_by_families(parsed.get("pozicijos"), _apimtis)
    except Exception as exc:  # noqa: BLE001
        log.exception("pass1_narrow: pozicijos build failed: %r", exc)
        parsed["pozicijos"] = []
        parsed.setdefault("warnings", []).append({
            "level": "ERROR", "source": "pozicijos_build_failure",
            "message": ("Sąmatos eilučių sudaryti nepavyko — sąmata tuščia. "
                        "Eilutes įrašykite rankomis sąmatoje arba brėžinį "
                        "perskaitykite iš naujo per mygtuką „Nustatymai“."),
        })

    try:
        parsed = _recompute_santrauka(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: santrauka recompute failed: %r", exc)

    # Step 16 — sanity tail (lt_rules, cross-page, sanity_checks, consistency, lt_sanity, v8).
    try:
        from .lt_rules import apply_lt_sanity
        parsed = apply_lt_sanity(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: lt_sanity failed: %r", exc)
    try:
        from .cross_page_validator import as_pipeline_warnings, validate_consistency
        cross = validate_consistency(parsed)
        if cross:
            parsed.setdefault("warnings", []).extend(as_pipeline_warnings(cross))
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: cross_page_validator failed: %r", exc)
    try:
        from .sanity_checks import run_all_checks
        sw = run_all_checks(parsed)
        if sw:
            parsed.setdefault("warnings", []).extend(sw)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: sanity_checks failed: %r", exc)
    try:
        from .consistency_checker import run_all_checks as _ck_run
        parsed["_consistency_checks"] = _ck_run(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: consistency_checker failed: %r", exc)
    try:
        from .sanity_mirror import build_lt_sanity
        parsed["lt_sanity"] = build_lt_sanity(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: lt_sanity mirror failed: %r", exc)
    try:
        parsed = _emit_v8_compat_fields(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("pass1_narrow: v8 compat emit failed: %r", exc)

    if rules_override is not None:
        parsed["_overrides"] = rules_override

    elapsed = round(time.time() - t0, 1)
    parsed["_meta"]["elapsed_s"] = elapsed
    parsed["_elapsed_s"] = elapsed
    parsed["status"] = "ok"
    return parsed
