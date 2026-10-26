"""Every _confidence_reason a contractor can see must guide, never confess.

2026-08-31, founder catch on the live review queue: a row read "Formulė
kalibruota pagal 1 rangovo samatą (Kliento) — … tikslumas nepatvirtintas
(reikia daugiau etalonų)". Three failures in one string: it LEAKS another
client's project name to every future user, it quotes our benchmark
methodology (sample counts, error pairs) as if the number were copied from
someone else's job, and it speaks pipeline jargon no contractor can act on.
The calibration facts belong in code comments; the visible string answers
"what is this based on, what do I check".

This test bans the whole class from every reason-producing surface.
"""
from __future__ import annotations

import re

import pytest

from extractor.confidence import CLASS_RULES, _OVERBILLING_RULES, apply_confidence

# Methodology confession / dev-speak lives in the runtime guard (one vocabulary
# source); customer identifiers are NEVER written into the repo — they come from
# the gitignored `backend/.confidential-terms` / SAMATU_CONFIDENTIAL_TERMS and
# are folded in here when present (extractor/user_text.confidential_pattern).
from extractor.user_text import JARGON, confidential_pattern  # noqa: E402

_CONF = confidential_pattern()
BANNED = re.compile(
    JARGON.pattern + (f"|{_CONF.pattern}" if _CONF else ""), re.IGNORECASE)


@pytest.mark.parametrize("needle,conf,reason",
                         CLASS_RULES + _OVERBILLING_RULES,
                         ids=[r[0] for r in CLASS_RULES + _OVERBILLING_RULES])
def test_static_rule_reasons_are_clean(needle, conf, reason):
    m = BANNED.search(reason)
    assert not m, f"banned token {m.group(0)!r} in reason for {needle!r}: {reason}"


def test_dynamic_reasons_are_clean():
    """The f-string reasons (apdailos-low, voting disagreement, no-partitions,
    unread dims) are only observable through apply_confidence — drive every
    branch and scan what it writes."""
    parsed = {
        "patalpos": [
            {"nr": "01", "_apdailos_confidence": "low", "n_partition_walls": 0,
             "elementai": [{"tipas": "langas", "plotis_m": None, "aukstis_m": None}]},
        ],
        "_voting": {"low_confidence_fields": ["01.plotas_m2"]},
        "pozicijos": [
            {"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 100},
            {"aprasymas": "Dažymo kampų montavimas", "kiekis": 200},
            {"aprasymas": "Angokraščių glaistymas-dažymas", "kiekis": 50},
            {"aprasymas": "Parketo / laminato klojimas", "kiekis": 80},
        ],
    }
    out = apply_confidence(parsed)
    for p in out["pozicijos"]:
        r = p.get("_confidence_reason") or ""
        m = BANNED.search(r)
        assert not m, f"banned token {m.group(0)!r} on {p['aprasymas']!r}: {r}"
    # The branches actually fired — this test must not pass by vacuity.
    joined = " | ".join(p.get("_confidence_reason") or "" for p in out["pozicijos"])
    assert "AI skaitymai nesutarė" in joined
    assert "PER MAŽA" in joined


def test_material_row_reasons_are_clean():
    """The Medžiagos section (2026-09-02) adds one reason of its own — the note
    a material row carries when its parent work line had none — and inherits
    the parent's otherwise. Scan the new string, and the rows a real build
    produces, through the same net."""
    from extractor.vision_call import (
        _MEDZIAGOS_REASON, SK_MEDZIAGOS, _build_pozicijos_from_rooms,
    )
    m = BANNED.search(_MEDZIAGOS_REASON)
    assert not m, f"banned token {m.group(0)!r} in the material reason"

    out = _build_pozicijos_from_rooms({
        "patalpos": [
            {"nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
             "glaistas_kg": 120.0, "dazai_l": 12.0, "gruntas_l": 8.0,
             "walls_paintable_m2": 45.0, "ceiling_paintable_m2": 20.0,
             "dazymo_plotas_m2": 65.0, "kampu_metrai": 30.0,
             "grindjuosciu_m": 16.0, "elementai": []},
        ],
        "santrauka": {},
    })
    mats = [p for p in out["pozicijos"] if p["skyrius"] == SK_MEDZIAGOS]
    assert mats, "the build produced no material rows to scan"
    for p in mats:
        r = p.get("_confidence_reason") or ""
        hit = BANNED.search(r)
        assert not hit, f"banned token {hit.group(0)!r} on {p['aprasymas']!r}: {r}"


def test_contribution_ledger_strings_are_clean():
    """The ledger (2026-09-02) adds a whole new class of user-visible prose:
    why each room is IN a number, why each one is OUT, and what every roll-up
    step did. Same net — a contractor reads these the way he reads a reason."""
    from extractor.vision_call import _build_pozicijos_from_rooms

    out = _build_pozicijos_from_rooms({
        "patalpos": [
            {"nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
             "walls_paintable_m2": 45.0, "ceiling_paintable_m2": 20.0,
             "dazymo_plotas_m2": 65.0, "kampu_metrai": 30.0,
             "kampai_inner_m": 10.8, "kampai_opening_reveals_m": 1.2,
             "kampai_pusiniai_m": 0.0, "kampai_perimetras_m": 18.0,
             "grindjuosciu_m": 16.0, "_grindjuosciu_baze_m": 14.55,
             "elementai": []},
            {"nr": "102", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.0, "perimetras_m": 10.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
             "walls_paintable_m2": 0.0, "ceiling_paintable_m2": 6.0,
             "plyteles_grindys_m2": 6.0, "kampu_metrai": 0.0,
             "grindjuosciu_m": 0.0, "elementai": []},
        ],
        "santrauka": {},
    })
    seen = 0
    for p in out["pozicijos"]:
        strings = (
            [c["included_because"] for c in (p.get("contributions") or [])]
            + [e["excluded_because"] for e in (p.get("excluded") or [])]
            + [s["label"] for s in (p.get("roll_up") or [])]
            + [s.get("note") or "" for s in (p.get("roll_up") or [])]
            + [k for c in (p.get("contributions") or [])
               for k in (c.get("terms") or {})]
        )
        seen += len(strings)
        for s in strings:
            m = BANNED.search(s)
            assert not m, f"banned token {m.group(0)!r} on {p['aprasymas']!r}: {s}"
    assert seen > 10, "the ledger produced almost no prose — did it stop emitting?"


def test_room_check_sheet_sentences_are_clean():
    """The room check sheet (2026-09-04) is now the most-read prose we ship:
    six source sentences per room plus a formula line per contributed
    quantity, and the contractor reads them one after another while deciding
    whether to trust the number beside them. Drive the builder over every
    corpus fixture and put the whole harvest through both nets — this test's
    BANNED regex AND the runtime guard, which additionally knows the
    (gitignored) customer identifiers."""
    import json
    from pathlib import Path

    from extractor import user_text
    from extractor.room_facts import build_room_facts
    from extractor.vision_call import (
        _build_pozicijos_from_rooms, _emit_v8_compat_fields,
        _recompute_per_room_via_python,
    )

    root = Path(__file__).resolve().parents[1]
    fixtures = sorted((root.parent / "ground_truth").glob("*/ai_extract.json"))
    assert fixtures, "no corpus fixture to scan — this test would pass vacuously"

    seen = 0
    for fixture in fixtures:
        src = json.loads(fixture.read_text(encoding="utf-8"))
        parsed = {k: v for k, v in src.items()
                  if k not in ("darbu_sarasas", "pozicijos")}
        parsed["pozicijos"] = []
        parsed = _recompute_per_room_via_python(
            parsed, parsed.get("_overrides") or {})
        built = _emit_v8_compat_fields(_build_pozicijos_from_rooms(parsed))
        project = {**parsed, "darbu_sarasas": built["darbu_sarasas"]}

        for room in project.get("patalpos") or []:
            payload = build_room_facts(project, room.get("nr"))
            assert payload is not None
            strings = []
            for f in payload["facts"]:
                strings.append(f["sentence"])
                if isinstance(f.get("value"), str):
                    strings.append(f["value"])
            for q in payload["quantities"]:
                strings += [s for s in (q.get("formula"),
                                        q.get("included_because")) if s]
            strings += [e["reason"] for e in payload["excluded"] if e.get("reason")]
            seen += len(strings)
            for s in strings:
                m = BANNED.search(s)
                assert not m, (f"banned token {m.group(0)!r} on "
                               f"{fixture.parent.name} room "
                               f"{room.get('nr')}: {s}")
                assert not user_text.is_banned(s), (
                    f"runtime guard rejected a check-sheet string on "
                    f"{fixture.parent.name} room {room.get('nr')}: {s}")
    assert seen > 100, "the check sheet produced almost no prose — did it stop?"


def test_door_reconciliation_reasons_are_clean():
    """Drive every branch of reconcile_frameless and scan the reasons it
    actually returns — banning identifiers in source was the wrong net
    (`archetipas` is a parameter name, not a user string)."""
    from extractor.door_type_reader import reconcile_frameless
    outs = [
        reconcile_frameless(2, 0, "beapvadines", 7, "premium"),
        reconcile_frameless(2, 0, "beapvadines", 7, None),
        reconcile_frameless(2, 5, None, 7, None),
        reconcile_frameless(5, 2, None, 7, None),
        reconcile_frameless(3, 3, None, 7, None),
        reconcile_frameless(0, 0, None, 7, None),
    ]
    for o in outs:
        r = o.get("reason") or ""
        m = BANNED.search(r)
        assert not m, f"banned token {m.group(0)!r} in door reason: {r}"
    assert any("specifikacij" in (o.get("reason") or "") for o in outs), \
        "the guidance strings must actually be exercised"


# ═════════════════════════════════════════════════════════════════════════════
# Patikrinimai — the rows the Sąmata step lists (2026-10-06)
# ═════════════════════════════════════════════════════════════════════════════
# Contractor walkthrough on localhost, „Patikrinimai → Verta patikrinti":
#   „[01]Tambūras (nr=01): Sienos neįtrauktos į dažomą plotą – standartinė
#    prielaida paskirčiai 'tamburas'; projekto apdailos duomenų nerasta. Jei
#    sienos dažomos, pažymėkite Prielaidų skydelyje."
#   „… Virtuvės plytelių juosta 0.60 m aukščio palei 3.0 m stalviršio …"
# The room's number twice (the list prints it in front, from `patalpa_nr`), a
# purpose CODE in Python quotes, a settings panel by a name the screen no
# longer shows (its button says „Nustatymai"), numbers with a decimal POINT in a
# Lithuanian sentence. The net below drives every builder that writes such a
# row — plus the ledger's exclusion reasons, which name the same panel — and
# rejects the whole class. A source-level net covers the builders that live
# inside the extraction run and cannot be driven alone.

import ast  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

from extractor.universal_rules import PASKIRTIS_LT, ROOM_TYPE_RULES  # noqa: E402

_LT_LETTERS = "A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž"
# What the engine writes for a purpose, a ceiling or a floor — never shown raw.
_CODES = sorted({*ROOM_TYPE_RULES, *PASKIRTIS_LT, "gkp", "pakabinamos", "tempiamos",
                 "itempiamos", "betonas", "medis", "plyteles", "minksta", "be_dangos"},
                key=len, reverse=True)
_QUOTED_CODE = re.compile(r"[\"'«„“]\s*(?:%s)\s*[\"'»“”]" % "|".join(map(re.escape, _CODES)))
_ASCII_QUOTED = re.compile(r"'[^'\n]+'|(?<![\w\"])\"[^\"\n]+\"")
_APOSTROPHE_WORD = re.compile(rf"[A-Za-z]'[{_LT_LETTERS}]")
_QUOTED_SPAN = re.compile(r"„[^“”]*[“”]")          # his drawing's own words, as written
_DOTTED = re.compile(r"(?<![\w.])\d+\.\d+(?!\.?\d)")  # 0.60 — not STR 2.04.01
# The drawing's own numbering is no decimal, the same way his quoted text is
# not: a page, sheet or section number („psl. 2.3", „lapas 4.1", „4.1–5.1
# punktas") and a code with letters in front („D-2.1", „M-3.2"). The reading
# model's warnings cite them and extractor/model_warnings.py keeps them as
# written (2026-10-06); a number with a unit after it is a quantity all the same.
_NO_UNIT = r"(?!\d|\.\d|\s?(?:m²|m2|m³|mm|cm|kg|m\b|l\b|%))"
_DRAWING_NUMBERING = re.compile(
    rf"(?<!\w)(?:psl\.?|lap\w*|brėž\w*\.?|pav\.?|nr\.?|p\.|punkt\w*|skyr\w*)\s*"
    rf"\d+(?:\.\d+)?(?:\s*[–—-]\s*\d+(?:\.\d+)?)?{_NO_UNIT}"
    r"|(?<![\w.,])\d+(?:\.\d+)?(?:\s*[–—-]\s*\d+(?:\.\d+)?)?\s*(?:punkt\w*|skyr\w*|lap\w*|psl\b|p\.)"
    r"|(?<![\w.])[^\W\d_]+-\d+(?:\.\d+)+", re.IGNORECASE)
_OLD_PANEL = re.compile(r"Prielaidų skydel|Prielaidose|[Pp]rielaidų skyri|„Prielaidos")
_INFORMAL = re.compile(r"\b(?:Patikrink|Pridėk|Įvesk|Pakeisk|Pažymėk|Pakartok)\b", re.IGNORECASE)
_AI = re.compile(rf"(?<![{_LT_LETTERS}])AI(?![{_LT_LETTERS}])")
_DEV = re.compile(r"\b(?:bbox|prompt\w*|floor plan\w*|elevation|re-?extract\w*|extraction\w*|"
                  r"wall_elevation|Python|recompute|pozicij\w*)\b|`", re.IGNORECASE)
_SNAKE = re.compile(r"(?<![\w./-])[a-z]+(?:_[a-z0-9]+)+(?!\w)")   # santechnika_potinkinis


def plain_lt_problems(text: str, allow=()) -> list[str]:
    """Everything that makes a Patikrinimai row read like a debug log. `allow`
    = the project's own identifiers (room numbers, names) — blanked out first,
    because a room called „1.2" is his numbering, not a decimal."""
    if not isinstance(text, str) or not text:
        return []
    for a in sorted((str(x) for x in allow if x), key=len, reverse=True):
        text = text.replace(a, "…")
    found = []
    if "(nr=" in text:
        found.append("„(nr=“ — the list already prints the room's number in front")
    for pat, why in ((_QUOTED_CODE, "a purpose/ceiling code in quotes — show its label"),
                     (_ASCII_QUOTED, "ASCII quotes — Lithuanian text quotes „…“"),
                     (_APOSTROPHE_WORD, "an English apostrophe word"),
                     (_OLD_PANEL, "the settings panel by a name the screen no longer shows (it is „Nustatymai“)"),
                     (_INFORMAL, "informal imperative — the app says „Patikrinkite“"),
                     (_AI, "„AI“ — say what was read from the drawing"),
                     (_DEV, "developer words"),
                     (_SNAKE, "a setting's code name — name the control his screen shows"),
                     (BANNED, "methodology jargon / a confidential term")):
        m = pat.search(text)
        if m:
            found.append(f"{why}: {m.group(0)!r}")
    m = _DOTTED.search(_DRAWING_NUMBERING.sub("…", _QUOTED_SPAN.sub("„…“", text)))
    if m:
        found.append(f"a decimal point in a number: {m.group(0)!r} — use lt_num()")
    return found


def _assert_plain(rows, allow=()):
    """`rows` = [(where, text)]; every text must read plain."""
    bad = [f"{where}: {problems} — {text}" for where, text in rows
           for problems in [plain_lt_problems(text, allow)] if problems]
    assert not bad, "Patikrinimai text reads like a debug log:\n" + "\n".join(bad)


def _warning_texts(warnings, tag):
    out = []
    for w in warnings or []:
        if not isinstance(w, dict):
            continue
        for key in ("message", "message_lt", "hint", "expected", "suggestion"):
            if isinstance(w.get(key), str) and w[key]:
                out.append((f"{tag}.{key}", w[key]))
    return out


def test_the_net_catches_the_walkthrough_rows():
    """The two strings the founder read must trip the net — else it protects
    nothing."""
    first = ("Tambūras (nr=01): Sienos neįtrauktos į dažomą plotą – standartinė prielaida "
             "paskirčiai 'tamburas'; projekto apdailos duomenų nerasta. Jei sienos dažomos, "
             "pažymėkite Prielaidų skydelyje.")
    second = ("Virtuvė/valgomasis (nr=04): Virtuvės plytelių juosta 0.60 m aukščio palei 3.0 m "
              "stalviršio — prielaida (brėžinys stalviršio ilgio neduoda). Pakeiskite Prielaidų "
              "skydelyje.")
    one = " ".join(plain_lt_problems(first))
    assert "(nr=" in one and "code in quotes" in one and "„Nustatymai“" in one
    two = " ".join(plain_lt_problems(second))
    assert "decimal point" in two and "„Nustatymai“" in two
    # …and the forms we write instead pass
    assert plain_lt_problems("Tambūras: Plotas 0,9 m² per mažas paskirčiai „Tambūras“ "
                             "(STR norma 1,5–10 m²). Pagal STR 2.04.01 — patikrinkite per "
                             "mygtuką „Nustatymai“; pjūvio žymeklis „+2.800“.") == []


def test_purpose_labels_are_the_ones_on_his_screen():
    """`PASKIRTIS_LT` mirrors the frontend's own labels — the room sheet select
    where he changes a purpose, and the room card for the classes that select
    does not offer — so a row says the same word he picks it by."""
    lt = json.loads((Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n"
                     / "lt.json").read_text(encoding="utf-8"))
    sheet = {k[len("paskirtis_"):]: v for k, v in lt["project"]["roomSheet"].items()
             if k.startswith("paskirtis_")}
    card = lt["project"]["roomCard"]["paskirtis"]
    fold = {"tambūras": "tamburas", "sandėliukas": "sandeliukas", "laiptinė": "laiptine"}
    for code, label in PASKIRTIS_LT.items():
        key = fold.get(code, code)
        want = sheet.get(key) or card.get(key) or card.get(code)
        assert want == label, f"{code}: backend {label!r}, screen {want!r}"
    # every class the engine has a rule for has a label
    assert set(ROOM_TYPE_RULES) <= set(PASKIRTIS_LT)


def _rule_rooms():
    """Rooms that trip every per-room branch of lt_rules and every finish note
    of universal_rules. Numbers carry letters („T1") so a number repeated in
    its own message cannot hide behind an area or a height."""
    from extractor.universal_rules import calc_room_quantities

    specs = [
        # too small for its purpose, low ceiling, perimeter too short; walls
        # and ceiling left out by the purpose standard
        {"nr": "T1", "pavadinimas": "Tambūras", "paskirtis": "tamburas",
         "plotas_m2": 0.9, "perimetras_m": 2.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.0, "lubu_aukstis_saltinis": "plano_uzrasas"},
        # too big, ceiling out of range and above 3 m, perimeter too long
        {"nr": "G2", "pavadinimas": "Garažas", "paskirtis": "garazas",
         "plotas_m2": 80.0, "perimetras_m": 100.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 4.8, "lubu_aukstis_saltinis": "plano_uzrasas"},
        # below the STR minimum for a bedroom
        {"nr": "M3", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji",
         "plotas_m2": 12.0, "perimetras_m": 14.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.4, "lubu_aukstis_saltinis": "plano_uzrasas"},
        # the kitchen splashback along an assumed counter
        {"nr": "K4", "pavadinimas": "Virtuvė/valgomasis", "paskirtis": "virtuve",
         "plotas_m2": 12.0, "perimetras_m": 14.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas"},
        # a wet room on the purpose default band, above 3 m
        {"nr": "V5", "pavadinimas": "Vonia", "paskirtis": "vonia",
         "plotas_m2": 6.0, "perimetras_m": 10.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 3.4, "lubu_aukstis_saltinis": "plano_uzrasas"},
        # the pipeline's bathroom default (no wall elevation pages)
        {"nr": "S6", "pavadinimas": "San. mazgas", "paskirtis": "san",
         "plotas_m2": 4.0, "perimetras_m": 8.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
         "_bathroom_paint_above_tile_m": 2.0},
        # the elevation measured the walls and found no tile
        {"nr": "L7", "pavadinimas": "Skalbykla", "paskirtis": "skalbykla",
         "plotas_m2": 5.0, "perimetras_m": 9.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
         "_tile_elevation_evidence": {"walls_measured": 2, "tile_zones_seen": 0}},
        # the finish table paints a garage the standard leaves raw
        {"nr": "G8", "pavadinimas": "Garažas", "paskirtis": "garazas",
         "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "plano_uzrasas",
         "sienu_apdailos_breakdown": {"dazymas_share": 1.0}},
        # a sauna: wood-lined ceiling, left out
        {"nr": "P9", "pavadinimas": "Pirtis", "paskirtis": "pirtis",
         "plotas_m2": 6.0, "perimetras_m": 10.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.4, "lubu_aukstis_saltinis": "plano_uzrasas"},
        # v4 2026-10-26: the ceiling-off disclosure fires only when he explicitly says the walls are
        # not painted (walls_paint_factor_override = 0): the raw-slab gate stays shut without a user
        # choice.
        {"nr": "G11", "pavadinimas": "Garažas", "paskirtis": "garazas",
         "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "plano_uzrasas",
         "lubu_tipas": "betonas", "walls_paint_factor_override": 0.0},
    ]
    rooms = []
    for spec in specs:
        r = {**spec, "elementai": []}
        rooms.append({**r, **calc_room_quantities(r)})
    # a wet room with no tile evidence at all (his rules: no band)
    wet = {"nr": "V10", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 5.0,
           "perimetras_m": 9.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "elementai": []}
    rules = {"vonia": {**ROOM_TYPE_RULES["vonia"], "tile_walls_to_m": 0}}
    rooms.append({**wet, **calc_room_quantities(wet, rules=rules)})
    rooms[0]["_height_source"] = "positioned_marker"
    rooms[1]["_height_marker_conflict"] = {"marker_m": 2.8, "kept_m": 5.7}
    return rooms


def test_rule_engine_rows_read_plain():
    from extractor.lt_rules import apply_lt_sanity

    rooms = _rule_rooms()
    rows = []
    for r in rooms:
        for note in (r.get("_wall_finish_assumptions") or []) + (r.get("_ceiling_finish_assumptions") or []):
            rows.append((f"room {r['nr']} note", note))
    warnings = apply_lt_sanity({"patalpos": rooms})["_lt_warnings"]
    rows += _warning_texts(warnings, "lt_rules")
    # the project-level branches each need their own project
    dup = [{"nr": f"D{i}", "pavadinimas": "Koridorius", "paskirtis": "koridorius",
            "plotas_m2": 6.0, "perimetras_m": 10.0, "perimetras_saltinis": "plano_matmenys"} for i in (1, 2)]
    for tag, parsed in (
        ("few rooms + duplicate", {"patalpos": dup}),
        ("many rooms", {"patalpos": [{"nr": f"N{i}", "pavadinimas": f"Kambarys {i}",
                                      "plotas_m2": 30.0} for i in range(31)]}),
        ("all heights from markers", {"patalpos": [{**r, "_height_source": "positioned_marker"}
                                                   for r in rooms[:3]
                                                   if not r.get("_height_marker_conflict")]}),
        ("markers + a split-level room", {"patalpos": [{**r, "_height_source": "positioned_marker"}
                                                       for r in rooms[:3]]}),
    ):
        rows += _warning_texts(apply_lt_sanity(parsed)["_lt_warnings"], tag)
    _assert_plain(rows)

    joined = " | ".join(t for _, t in rows)
    for fired in ("per mažas paskirčiai „Tambūras“", "per didelis paskirčiai „Garažas“",
                  "žemesnis, nei STR leidžia", "neįprastas (norma", "Perimetras 2,0 m per mažas",
                  "per didelis 80,0 m² plotui", "Išklotinės šiai patalpai nėra",
                  "Sienos dažomos pagal projekto apdailos duomenis", "Lubos neįtrauktos",
                  "lubos dengiamos medžiu", "Atatvaro plytelių juosta skaičiuota 0,60 m",
                  "3,0 m ilgio stalviršį", "Plytelių aukštis brėžinyje nerastas",
                  "Drėgnos patalpos sienų plytelių", "Išklotinėse šios patalpos sienose",
                  "Plytelių juosta (iki", "Virš 3 m kiekis skaičiuotas", "altitudė 2,80 m",
                  "gali būti didesnis", "nesiliečiančios", "neįprastai didelis", "Rasta tik 2",
                  "Patalpų rasta: 31", "gali būti ta pati patalpa", "Visų patalpų",
                  "„Nustatymai“"):
        assert fired in joined, f"branch did not fire: {fired!r}"

    # a room-level row names the room once — its number is in front of it
    for w in warnings:
        nr = str(w.get("patalpa_nr") or "")
        if nr:
            assert nr not in w["message"], w["message"]


def test_extraction_rows_read_plain():
    """The rows the extraction run itself writes, through the builders that can
    be driven alone, and the ledger's reasons for leaving a room out."""
    from extractor import vision_call as vc

    rows = []
    for name, table in (("walls", vc._WALLS_OUT_LT), ("floor", vc._GRIND_OUT_LT),
                        ("ceiling", vc._CEILING_OUT_LT)):
        rows += [(f"ledger.{name}.{k}", v) for k, v in table.items()]
    for k, (msg, hint) in vc._CONSISTENCY_LT.items():
        rows += [(f"consistency.{k}", msg), (f"consistency.{k}.hint", hint)]

    # (the perimeter-bound warning went with Pass-1's perimeters — v4 3b; the blank rows' sentences are here)
    from extractor import row_provenance as rp
    rows += [(f"row_provenance.{k}", getattr(rp, k)) for k in
             ("LED_NO_LEGEND_LT", "DUCTS_LT", "DUCTS_INSULATION_LT", "DUCTS_FIXING_LT", "RUBBISH_LT")]
    rows += [("row_provenance.protection", rp.protection_lt(120.5))]

    for partial in (False, True):
        parsed: dict = {}
        vc._warn_apdailos_degraded(parsed, "no JSON in response", partial=partial)
        rows += _warning_texts(parsed["warnings"], f"apdailos(partial={partial})")

    boxed = {"patalpos": [{"pavadinimas": f"R{i}", "bbox_pct": {"x": 0.4, "y": 0.4, "w": 0.02, "h": 0.02}}
                          for i in range(10)]}
    rows += _warning_texts(vc._validate_room_bboxes(boxed)["warnings"], "bbox")

    failing = {"patalpos": [{"nr": "K4", "pavadinimas": "Virtuvė", "paskirtis": "virtuve",
                             "plotas_m2": 26.0, "perimetras_m": 20.8, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "plano_uzrasas",
                             "lubu_tipas": ["gkp", "tempiamos"], "elementai": []}]}
    calc = [x for x in vc._recompute_per_room_via_python(failing, None).get("warnings") or []
            if isinstance(x, dict) and x.get("code") == "room_calc_failed"]
    assert calc and "K4" not in calc[0]["message"]
    rows += _warning_texts(calc, "room_calc_failed")

    twins = {"_wall_elevations": [{"room_name": "Vonia", "wall_id": "A", "wall_total_width_mm": 1500,
                                   "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 1500}]}],
             "patalpos": [{"nr": "V1", "pavadinimas": "Vonia"}, {"nr": "V2", "pavadinimas": "Vonia"}]}
    vc._apply_wall_elevation_tile_override(twins)
    assert twins.get("warnings")        # the list that is kept (2026-10-06), not _lt_warnings
    rows += _warning_texts(twins["warnings"], "elevation twins")
    _assert_plain(rows)


def test_cross_check_rows_read_plain():
    from extractor.cross_page_validator import validate_consistency

    def room(nr, name, pask, **kw):
        return {"nr": nr, "pavadinimas": name, "paskirtis": pask, "elementai": [], **kw}

    parsed = {
        "patalpos": [
            room("101", "Svetainė", "gyvenamoji", plotas_m2=40.0, perimetras_m=60.0, perimetras_saltinis="plano_matmenys",
                 lubu_aukstis_m=2.1, lubu_aukstis_saltinis="plano_uzrasas", ceiling_paintable_m2=30.0, lubu_tipas="gkp",
                 dazymo_plotas_m2=400.0, dazai_l=200.0, grindjuosciu_m=80.0, puslapio_nr=3,
                 aukstas=2, elementai=[{"tipas": "duris", "kiekis": 2}, {"tipas": "langas", "kiekis": 3}]),
            room("201", "Vonia", "vonia", plotas_m2=6.0, perimetras_m=7.0, perimetras_saltinis="plano_matmenys", lubu_aukstis_m=5.0, lubu_aukstis_saltinis="plano_uzrasas", aukstas=2),
            room("202", "WC", "wc", plotas_m2=2.0, perimetras_m=6.0, perimetras_saltinis="plano_matmenys", lubu_aukstis_m=2.7, lubu_aukstis_saltinis="plano_uzrasas", aukstas=2),
            room("301", "Sandėliukas", "sandeliukas", plotas_m2=5.0, perimetras_m=9.0, perimetras_saltinis="plano_matmenys",
                 lubu_aukstis_m=2.7, lubu_aukstis_saltinis="plano_uzrasas", aukstas=3),
        ],
        "schedule_tables": {"durys": [{"kiekis": 5}], "langai": [{"kiekis": 7}]},
        "_eksplikacija": {"patalpos": [{"nr": "101", "plotas_m2": 60.0, "aukstas": 2},
                                       {"nr": "201", "plotas_m2": 3.0, "aukstas": 2}]},
    }
    no_floors = {"patalpos": [room("1-01", "Holas", "holas", plotas_m2=10.0),
                              room("2-01", "Holas", "holas", plotas_m2=10.0)]}
    out = validate_consistency(parsed) + validate_consistency(no_floors)
    rows = _warning_texts(out, "cross_page")
    _assert_plain(rows)
    joined = " | ".join(t for _, t in rows)
    for fired in ("forma neįprasta", "kompaktiška", "per mažas — įprastai", "neįprastai didelis",
                  "lubų plotas", "Durų skaičius", "Langų skaičius", "Bendras patalpų plotas",
                  "Kelių aukštų projektas", "hidroizoliacija", "sienų plytelių nėra",
                  "dažų sąnauda", "Dažomas plotas", "Grindjuosčių", "Pažymėta, kad patalpa yra"):
        assert fired in joined, f"rule did not fire: {fired!r}"


def test_quantity_logic_rows_read_plain(monkeypatch):
    from extractor import sanity_checks as sc
    from extractor.plan_area_annotations import lane_warnings
    from extractor.scale_validator import validate_scale

    rooms = [
        {"nr": "1", "pavadinimas": "Svetainė", "plotas_m2": 20.0, "perimetras_m": 9.0, "perimetras_saltinis": "plano_matmenys",
         "walls_paintable_m2": 120.0, "ceiling_paintable_m2": 12.0, "grindjuosciu_m": 40.0,
         "dazai_l": 1.0, "gkp_lubu_standart_m2": 30.0,
         "elementai": [{"type": "langas", "reveal_length_m": 0}, {"tipas": "duris"}]},
        {"nr": "2", "pavadinimas": "Kambarys", "plotas_m2": 15.0, "perimetras_m": 16.0, "perimetras_saltinis": "plano_matmenys",
         "walls_paintable_m2": 40.0, "ceiling_paintable_m2": 15.0,
         "elementai": [{"type": "langas", "reveal_length_m": 12.0}]},
    ]
    vr = {"patalpos": rooms, "pozicijos": [{"aprasymas": "GKP lapai luboms", "vnt": "vnt", "kiekis": 40}]}
    rows = _warning_texts(sc.run_all_checks(vr), "sanity_checks")
    rows += _warning_texts(sc.run_all_checks({"patalpos": rooms[:1]}), "sanity_checks(zero reveals)")

    def boom(*_a, **_k):
        raise KeyError("plotas_m2")
    monkeypatch.setattr(sc, "_ALL_CHECKS", [boom])
    crashed = sc.run_all_checks(vr)
    assert crashed and "boom" not in crashed[0]["message"]
    rows += _warning_texts(crashed, "sanity_checks(crash)")

    rows += [("scale", w) for w in validate_scale(
        scale_factor=50.0, rendered_dpi=200,
        rooms=[{"pavadinimas": "Svetainė", "width_m": 3.0, "height_m": 4.0, "diagonal_px": 394}])]

    plan_rooms = [{"nr": "06", "pavadinimas": "Kambarys", "plotas_m2": 7.01},
                  {"nr": "07", "pavadinimas": "Kambarys 2", "plotas_m2": 5.64,
                   "_area_unconfirmed_reason": "duplicate_of:06"},
                  {"nr": "08", "pavadinimas": "Sandėliukas", "plotas_m2": 3.1,
                   "_area_unconfirmed_reason": "label_differs",
                   "_plotas_uzrasas_kitas": {"page": 2, "value_m2": 4.25}},
                  {"nr": "09", "pavadinimas": "Rūbinė", "plotas_m2": 2.2}]
    lane = {"status": "applied", "geometry": "shared_frame", "unconfirmed": ["07", "08", "09"],
            "unclaimed": [{"page": 2, "value_m2": 6.9}, {"page": 2, "value_m2": 4.1, "patalpoje": "06"}]}
    rows += _warning_texts(lane_warnings(lane, plan_rooms), "plan labels")
    assert len(rows) > 12
    _assert_plain(rows)


def test_every_corpus_project_lists_plain_rows():
    """The whole list a corpus project shows, rebuilt by today's code: the
    per-room engine's notes, the STR rules, the §6 logic checks, the cross-page
    checks, everything the row builder writes — through the same mirror the
    Patikrinimai list reads. Stored warnings from older runs are dropped first:
    only what the code says TODAY is judged."""
    from extractor.cross_page_validator import validate_consistency
    from extractor.lt_rules import apply_lt_sanity
    from extractor.sanity_checks import run_all_checks
    from extractor.sanity_mirror import build_lt_sanity
    from extractor.vision_call import _build_pozicijos_from_rooms, _recompute_per_room_via_python

    root = Path(__file__).resolve().parents[2]
    fixtures = sorted((root / "ground_truth").glob("*/ai_extract.json"))
    assert fixtures, "no corpus fixture to scan — this test would pass vacuously"
    seen = 0
    for fixture in fixtures:
        src = json.loads(fixture.read_text(encoding="utf-8"))
        parsed = {k: v for k, v in src.items()
                  if k not in ("darbu_sarasas", "pozicijos", "warnings", "_lt_warnings", "lt_sanity")}
        parsed["pozicijos"] = []
        parsed = _recompute_per_room_via_python(parsed, parsed.get("_overrides") or {})
        parsed = _build_pozicijos_from_rooms(parsed)
        parsed = apply_lt_sanity(parsed)
        parsed["warnings"] = (parsed.get("warnings") or []) + run_all_checks(parsed) + [
            {"level": w["level"].upper(), "message": w.get("message_lt") or w.get("message", "")}
            for w in validate_consistency(parsed)]
        shown = build_lt_sanity(parsed)["warnings"]
        ids = [v for r in parsed.get("patalpos") or [] for v in (r.get("nr"), r.get("pavadinimas")) if v]
        rows = [(f"{fixture.parent.name} {t}", x) for t, x in _warning_texts(shown, "row")]
        rows += [(f"{fixture.parent.name} ledger", e["excluded_because"])
                 for p in parsed.get("pozicijos") or [] for e in (p.get("excluded") or [])
                 if e.get("excluded_because")]
        seen += len(rows)
        _assert_plain(rows, allow=ids)
    assert seen > 40, "the corpus produced almost no rows — did the builders stop?"


# The builders inside the extraction run that cannot be driven alone (the
# section-marker height row, the specification count row, the failure rows) —
# and every module that writes one. Scanned as source: the literal fragments
# below can only be the old wording.
_ROW_BUILDERS = (
    "extractor/lt_rules.py", "extractor/universal_rules.py", "extractor/vision_call.py",
    "extractor/cross_page_validator.py", "extractor/sanity_checks.py",
    "extractor/scale_validator.py", "extractor/plan_area_annotations.py",
    "extractor/room_facts.py", "extractor/project_questions.py", "extractor/sanity_mirror.py",
    "extractor/row_provenance.py",
    "api/recompute_quantities.py", "api/revalidate.py", "main.py",
)
_OLD_FRAGMENTS = re.compile(r"\(nr=|Prielaidų skydel|Prielaidose|[Pp]rielaidų skyri|"
                            r"paskirčiai '|skiltyje „Prielaidos")


def test_no_row_builder_writes_the_old_fragments():
    backend = Path(__file__).resolve().parents[1]
    hits = []
    for rel in _ROW_BUILDERS:
        tree = ast.parse((backend / rel).read_text(encoding="utf-8"))
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and n.body and isinstance(n.body[0], ast.Expr)
                      and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings):
                m = _OLD_FRAGMENTS.search(node.value)
                if m:
                    hits.append(f"{rel}:{node.lineno} {m.group(0)!r}: {node.value[:90]!r}")
    assert not hits, "old Patikrinimai wording in a row builder:\n" + "\n".join(hits)


# ═════════════════════════════════════════════════════════════════════════════
# The reading model's own warnings and the LED estimate rows (2026-10-06)
# ═════════════════════════════════════════════════════════════════════════════
# The model's warnings reach the same list as it wrote them — „… priimta
# 101=3.40 ir 102=3.40." on a production run of objektas_a. Their numbers are
# now written his way (extractor/model_warnings.py, at extraction); the rest of
# their wording is the prompt's, and changing the prompt needs a paid eval. So
# the whole net is asked of the sentences that were plain apart from their
# numbers, and the number class of every model-written sentence in the corpus.

from extractor.model_warnings import plain_numbers, room_identifiers  # noqa: E402

_PROD_ROOMS = [{"nr": "101", "pavadinimas": "Tambūras", "paskirtis": "tamburas"},
               {"nr": "102", "pavadinimas": "Svetainė, virtuvė", "paskirtis": "gyvenamoji"}]


def _model_written(warnings) -> list[str]:
    """The model's own entries in a stored extract: level + message (+ room),
    nothing the pipeline adds (its code / source / severity)."""
    out = []
    for w in warnings or []:
        if isinstance(w, str):
            out.append(w)
        elif isinstance(w, dict) and not set(w) - {"level", "message", "patalpa_nr"}:
            if isinstance(w.get("message"), str) and w["message"]:
                out.append(w["message"])
    return out


def _classes(problems: list[str]) -> set[str]:
    return {p.split(":")[0] for p in problems}


def test_the_net_lets_the_drawings_own_numbering_through():
    for text in ("Žr. psl. 2.3 ir lapas 4.1.", "Apdaila — 4.1–5.1 punktas.", "Durys D-2.1, mazgas M-3.2."):
        assert plain_lt_problems(text) == [], text
    # …while a number with a unit is a quantity wherever it stands
    for text in ("Lape 2.5 m ilgio niša.", "Durų plotis 0.90 m.", "Psl. 2.5 m² plotas."):
        assert "decimal point" in " ".join(plain_lt_problems(text)), text


def test_the_production_warning_reads_plain_once_its_numbers_are_his():
    raw = ("Trijų +3400 žymeklių priskyrimas tarp 101 ir 102 nėra visiškai vienareikšmis; "
           "priimta 101=3.40 ir 102=3.40.")
    assert "decimal point" in " ".join(plain_lt_problems(raw))
    out = plain_numbers(raw, room_identifiers(_PROD_ROOMS), _PROD_ROOMS)
    assert out.endswith("priimta 101 — 3,40 m ir 102 — 3,40 m.")
    assert plain_lt_problems(out, allow=room_identifiers(_PROD_ROOMS)) == []


def test_every_model_written_warning_in_the_corpus_has_his_numbers():
    root = Path(__file__).resolve().parents[2]
    fixtures = sorted((root / "ground_truth").glob("*/ai_extract.json"))
    assert fixtures, "no corpus fixture to scan — this test would pass vacuously"
    changed, clean = 0, 0
    for fixture in fixtures:
        src = json.loads(fixture.read_text(encoding="utf-8"))
        rooms = [r for r in src.get("patalpos") or [] if isinstance(r, dict)]
        ids = room_identifiers(rooms)
        for raw in _model_written(src.get("warnings")):
            out = plain_numbers(raw, ids, rooms)
            before, after = plain_lt_problems(raw, allow=ids), plain_lt_problems(out, allow=ids)
            where = f"{fixture.parent.name}: {out}"
            assert not [p for p in after if p.startswith("a decimal point")], where
            assert _classes(after) <= _classes(before), f"the rewrite added a problem — {where}"
            changed += out != raw
            clean += not after and bool(before)
    assert changed >= 6, f"only {changed} corpus sentences rewritten — is the corpus still the one measured?"
    assert clean >= 4, "no sentence went from flagged to plain — the net and the rewrite disagree"


