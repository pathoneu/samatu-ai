"""The reading model's own warnings, in the numbers his screen writes (2026-10-06).

Pass 1 returns `warnings` the model wrote itself, and they reach „Verta
patikrinti" as written — on a production run: „Trijų +3400 žymeklių
priskyrimas tarp 101 ir 102 nėra visiškai vienareikšmis; priimta 101=3.40 ir
102=3.40." A decimal point and a formula in a Lithuanian sentence. The prompt
is not touched (that needs a paid eval); this is ONE deterministic pass over the
model-written texts only (`extract_interior` captures them right after Pass 1
and runs this before the checks and the list read them):

  · a decimal point between digits → a decimal comma („2.82 m" → „2,82 m");
  · a room number = a ceiling height in metres („101=3.40") → „101 — 3,40 m".

Left exactly as written: quoted drawing text („+3400“, "…", '…'), codes and
dates with two or more dots (STR 2.04.01, 2025.04.02), page / sheet / section
numbers (psl. 2.3, lapas 2.1, 4.1–5.1 punktas), codes with letters in front
(D-2.1, M-3.2, A1.2), the project's own room numbers (1.01) and a list of
rooms after „patalpose" / „kambariuose" — unless a unit follows the number,
which makes it a quantity.

Meaning never changes: every number keeps its digits, and the two steps that
read these texts by machine — the LED room-list gate
(niche_inference.enumerated_led_rooms) and the height salvage
(height_markers.salvage_heights_from_warnings) — must read the same thing
before and after, or the text is left as the model wrote it.

The English words the reading prompt teaches the model come back inside its
Lithuanian sentences too („… (dimension chain nepilnai įskaitomas)", „…,
confidence žema" — the 2026-10-07 walkthrough). `plain_words` is a small
glossary for the ones the stored readings actually carry; it runs first, under
the same rules (see the block above it).
"""
from __future__ import annotations

import re
from typing import Iterable

_LT_LETTERS = "A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž"
_NUM = r"\d+(?:\.\d+)?"
_RANGE = rf"{_NUM}(?:\s*[–—-]\s*{_NUM})?"

# Spans never touched.
_QUOTED = re.compile(r"„[^“”\"\n]*[“”\"]|“[^”\n]*”|«[^»\n]*»|\"[^\"\n]*\"|(?<!\w)'[^'\n]*'(?!\w)")
_MULTI_DOT = re.compile(r"(?<![\d.])\d+(?:\.\d+){2,}(?!\d)")              # 2.04.01, 2025.04.02
_YEAR_MONTH = re.compile(r"(?<![\w.,])(?:19|20)\d{2}\.(?:0[1-9]|1[0-2])(?![\d]|[.,]\d)")  # 2025.04
_LETTER_CODE = re.compile(rf"(?<![\w.])[{_LT_LETTERS}]+-?\d+(?:\.\d+)+")  # D-2.1, M-3.2, A1.2
_REF_BEFORE = re.compile(
    rf"(?<!\w)(?:psl\.?|lap\w*|brėž\w*\.?|pav\.?|nr\.?|p\.|punkt\w*|skyr\w*)\s*"
    rf"{_RANGE}(?:\s*,\s*{_RANGE})*", re.IGNORECASE)                       # psl. 2.3, lapas 2.1
_REF_AFTER = re.compile(
    rf"(?<![\w.,]){_RANGE}\s*(?:punkt\w*|skyr\w*|lap\w*|psl\b|p\.)", re.IGNORECASE)  # 4.1–5.1 punktas
_ROOM_LIST = re.compile(
    rf"(?<!\w)(?:patalp\w*|kambar\w*)\s+(?:nr\.?\s*)?{_NUM}(?:\s*(?:,|ir|bei)\s*{_NUM})*",
    re.IGNORECASE)                                                         # kambariuose 1.01, 1.03
_DOTTED_NUMBER = re.compile(r"\d+\.\d+")
# A unit right after a number makes it a quantity, whatever stands in front.
_UNIT_AFTER = re.compile(r"\s?(?:m²|m2|m³|m3|mm|cm|kg|vnt|val|m(?![\w²³])|l(?!\w)|h(?!\w)|%|°)")

# The two rewrites.
_DECIMAL = re.compile(r"(?:(?<![\w.,])|(?<=\d[x×]))(\d+)\.(\d+)(?![\d]|\.\d)")
_ROOM_HEIGHT_TAIL = r"\s*=\s*(\d)[.,](\d{1,3})(?![\d]|[.,]\d)(?:\s*m(?![\w²³]))?"
MIN_HEIGHT_M, MAX_HEIGHT_M = 1.5, 9.99


def _spans(pattern: re.Pattern, text: str) -> list[tuple[int, int]]:
    return [m.span() for m in pattern.finditer(text)]


def _numbers_kept_in(span_pattern: re.Pattern, text: str) -> list[tuple[int, int]]:
    """The dotted numbers inside `span_pattern`'s matches that are NOT followed
    by a unit — the ones the span protects."""
    out = []
    for m in span_pattern.finditer(text):
        for n in _DOTTED_NUMBER.finditer(text, m.start(), m.end()):
            if not _UNIT_AFTER.match(text, n.end()):
                out.append(n.span())
    return out


def _hard_spans(text: str) -> list[tuple[int, int]]:
    return (_spans(_QUOTED, text) + _spans(_MULTI_DOT, text) + _spans(_LETTER_CODE, text)
            + _numbers_kept_in(_YEAR_MONTH, text)
            + _numbers_kept_in(_REF_BEFORE, text) + _numbers_kept_in(_REF_AFTER, text))


def _room_spans(text: str, room_ids: Iterable[str]) -> list[tuple[int, int]]:
    """His room numbers (and names) that carry a dot, wherever they stand alone
    and no unit follows them, plus the numbers listed after „patalpose" /
    „kambariuose"."""
    out = _numbers_kept_in(_ROOM_LIST, text)
    for rid in room_ids:
        if not _DOTTED_NUMBER.search(rid):
            continue
        for m in re.finditer(rf"(?<![\w.,]){re.escape(rid)}(?![\w]|[.,]\d)", text):
            if not _UNIT_AFTER.match(text, m.end()):
                out.append(m.span())
    return out


def _inside(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(s < end and start < e for s, e in spans)


def _room_height_pattern(room_ids: Iterable[str]) -> re.Pattern | None:
    """„<room number>=<metres>" for THIS project's room numbers only — a number
    the project has no room for („300=3.00", centimetres = metres) is not one."""
    ids = sorted({str(r).strip() for r in room_ids if str(r or "").strip()}, key=len, reverse=True)
    if not ids:
        return None
    head = "|".join(re.escape(r) for r in ids)
    return re.compile(rf"(?<![\w.,])({head}){_ROOM_HEIGHT_TAIL}")


def _rewrite(text: str, room_ids: list[str], with_room_heights: bool) -> str:
    pattern = _room_height_pattern(room_ids) if with_room_heights else None
    if pattern is not None:
        hard = _hard_spans(text)

        def _height(m: re.Match) -> str:
            value = float(f"{m.group(2)}.{m.group(3)}")
            if _inside(hard, m.start(), m.end()) or not (MIN_HEIGHT_M <= value <= MAX_HEIGHT_M):
                return m.group(0)
            return f"{m.group(1)} — {m.group(2)},{m.group(3)} m"

        text = pattern.sub(_height, text)
    keep = _hard_spans(text) + _room_spans(text, room_ids)

    def _comma(m: re.Match) -> str:
        if _inside(keep, m.start(), m.end()):
            return m.group(0)
        return f"{m.group(1)},{m.group(2)}"

    return _DECIMAL.sub(_comma, text)


def _digits(text: str) -> list[str]:
    """Every number's digits in order, separators read alike — what may not change."""
    return [t.replace(",", ".") for t in re.findall(r"\d+(?:[.,]\d+)*", text)]


def _same_for_the_readers(before: str, after: str, rooms: list[dict]) -> bool:
    """Do the steps that read these texts by machine read the same thing?"""
    if _digits(before) != _digits(after):
        return False
    from .niche_inference import enumerated_led_rooms
    if enumerated_led_rooms([before]) != enumerated_led_rooms([after]):
        return False
    if rooms:
        from .height_markers import salvage_heights_from_warnings
        if salvage_heights_from_warnings([before], rooms) != salvage_heights_from_warnings([after], rooms):
            return False
    return True


def room_identifiers(rooms: Iterable[dict] | None) -> list[str]:
    """The project's own room numbers and names — never read as decimals."""
    out: list[str] = []
    for r in rooms or []:
        if not isinstance(r, dict):
            continue
        for key in ("nr", "pavadinimas"):
            v = str(r.get(key) or "").strip()
            if v and v not in out:
                out.append(v)
    return out


def plain_numbers(text: str, room_ids: Iterable[str] = (), rooms: list[dict] | None = None) -> str:
    """One model-written text with decimal commas and „101 — 3,40 m" — or the
    text as written, when the rewrite would change what a reader of it sees."""
    if not isinstance(text, str) or not text or not re.search(r"\d[.,=]|=\s*\d", text):
        return text
    ids = [str(r) for r in room_ids if str(r or "").strip()]
    rooms = [r for r in (rooms or []) if isinstance(r, dict)]
    for with_room_heights in (True, False):
        out = _rewrite(text, ids, with_room_heights)
        if out == text or _same_for_the_readers(text, out, rooms):
            return out
    return text


# ── The English words the reader leaks into a Lithuanian sentence ───────────
# The reading prompt is half English (`dimension chain`, `confidence: "low"`,
# `default 2.82`, `count'as`, `inline_label`) and the model writes those words
# back into its Lithuanian warnings. Measured on the stored readings
# (ground_truth/*/ai_extract.json and the local projects, 2026-10-07): the
# dimension chain, the confidence level, a default / fallback height, a symbol
# count and „inline žymų". A glossary for exactly those, nothing cleverer:
#   · only in a Lithuanian sentence (it has a Lithuanian letter);
#   · whole words — a code (snake_case, `…`), the drawing's quoted text and
#     the project's own room names are never touched;
#   · an ending the glossary does not know („chain'uką") stays as written;
#   · case follows the English word („Confidence" → „Patikimumas").
_LT_ONLY = re.compile(r"[ąčęėįšųūžĄČĘĖĮŠŲŪŽ]")
_NOT_IN_WORD = r"(?<![\w'’`])"
_WORD_END = r"(?![\w'’`])"
_BACKTICKED = re.compile(r"`[^`\n]*`")

_CHAIN_FORMS = {   # the ending the model hung on „chain" → the Lithuanian noun
    "": "grandinė", "as": "grandinė", "s": "grandinės", "ai": "grandinės",
    "o": "grandinės", "ų": "grandinių", "ą": "grandinę", "us": "grandines",
    "e": "grandinėje", "uose": "grandinėse", "u": "grandine", "ais": "grandinėmis",
    "ams": "grandinėms",
}
# The model declined the chain as a masculine noun („dimension chain …
# nematomas"); „grandinė" is feminine, so a participle that agreed with it —
# right after it, or after one adverb — follows it.
_CHAIN = re.compile(
    rf"{_NOT_IN_WORD}(dimension)\s+chain(s?)(?:['’]([^\W\d_]+))?{_WORD_END}"
    r"(?:(\s+(?:(?:ne)?(?:pilnai|aiškiai|dalinai|visiškai|tiksliai|visai)\s+)?)"
    rf"([^\W\d_]+?(?:om|am|ėm|yt|ėt|ot))(as|i){_WORD_END})?",
    re.IGNORECASE)
_CHAIN_HALF = re.compile(rf"{_NOT_IN_WORD}(dimension)(?=\s+grandin)", re.IGNORECASE)

_LEVELS = {"low": "žemas", "žema": "žemas", "žemas": "žemas",
           "medium": "vidutinis", "vidutinė": "vidutinis", "vidutinis": "vidutinis",
           "high": "aukštas", "aukšta": "aukštas", "aukštas": "aukštas"}
_LEVEL = "|".join(sorted(_LEVELS, key=len, reverse=True))
_CONF_LEVEL_FIRST = re.compile(                       # „low confidence" → „žemas patikimumas"
    rf"{_NOT_IN_WORD}({_LEVEL})[\s-]+confidence{_WORD_END}", re.IGNORECASE)
_CONF_LEVEL_AFTER = re.compile(                       # „confidence žema" → „patikimumas žemas"
    rf"{_NOT_IN_WORD}(confidence)(\s*[:=–—-]\s*|\s+(?:yra\s+)?)({_LEVEL}){_WORD_END}",
    re.IGNORECASE)
_CONF_FORMS = {"": "patikimumas", "as": "patikimumas", "o": "patikimumo",
               "ą": "patikimumą", "u": "patikimumu", "e": "patikimume"}
_CONF = re.compile(rf"{_NOT_IN_WORD}(confidence)(?:['’]([^\W\d_]+))?{_WORD_END}", re.IGNORECASE)

# „priimtas default 2.82m", „naudotas fallback 2.82 m" — before a value only:
# „numatytasis" agrees with the height it names, not with every noun.
_DEFAULT = re.compile(rf"{_NOT_IN_WORD}(default|fallback)(?=\s*[~≈]?\s*\d)", re.IGNORECASE)

_COUNT_FORMS = {"": "skaičius", "as": "skaičius", "o": "skaičiaus", "ą": "skaičių",
                "ai": "skaičiai", "ų": "skaičių", "ui": "skaičiui"}
_COUNT = re.compile(rf"{_NOT_IN_WORD}(count)(?:['’]([^\W\d_]+))?{_WORD_END}", re.IGNORECASE)

# „iš lubų plano inline žymų" — the plan's own labels; „inline" says nothing more.
_INLINE = re.compile(rf"{_NOT_IN_WORD}(inline)\s+((?:žym|užraš)[^\W\d_]*){_WORD_END}",
                     re.IGNORECASE)


def _cased(english: str, lithuanian: str) -> str:
    """`lithuanian` in the case the model wrote `english` in."""
    if len(english) > 1 and english.isupper():
        return lithuanian.upper()
    if english[:1].isupper():
        return lithuanian[:1].upper() + lithuanian[1:]
    return lithuanian


def _chain(m: re.Match) -> str | None:
    ending = (m.group(3) or "").lower()
    key = ending or ("s" if m.group(2) else "")
    noun = _CHAIN_FORMS.get(key)
    if noun is None:
        return None
    out = _cased(m.group(1), "matmenų") + " " + noun
    if m.group(5):
        participle, tail = m.group(5), m.group(6)
        if key in ("", "as") and tail.lower() == "as":
            tail = _cased(tail, "a")
        elif key in ("s", "ai") and tail.lower() == "i":
            tail = _cased(tail, "os")
        out += m.group(4) + participle + tail
    return out


def _conf(m: re.Match) -> str | None:
    noun = _CONF_FORMS.get((m.group(2) or "").lower())
    return None if noun is None else _cased(m.group(1), noun)


def _count(m: re.Match) -> str | None:
    noun = _COUNT_FORMS.get((m.group(2) or "").lower())
    return None if noun is None else _cased(m.group(1), noun)


_GLOSSARY = (
    (_CHAIN, _chain),
    (_CHAIN_HALF, lambda m: _cased(m.group(1), "matmenų")),
    (_CONF_LEVEL_FIRST, lambda m: _cased(m.group(1), _LEVELS[m.group(1).lower()]) + " patikimumas"),
    (_CONF_LEVEL_AFTER, lambda m: _cased(m.group(1), "patikimumas") + m.group(2)
                                  + _LEVELS[m.group(3).lower()]),
    (_CONF, _conf),
    (_DEFAULT, lambda m: _cased(m.group(1), "numatytasis")),
    (_COUNT, _count),
    (_INLINE, lambda m: _cased(m.group(1), m.group(2))),
)


def _name_spans(text: str, names: Iterable[str]) -> list[tuple[int, int]]:
    out = []
    for name in names:
        if name and not name.isdigit():
            out += _spans(re.compile(re.escape(name), re.IGNORECASE), text)
    return out


def _is_lithuanian(text: str, names: Iterable[str]) -> bool:
    """A Lithuanian letter in the sentence itself — not only in a quoted
    drawing text or a room's name („Room „Svetainė“ count unknown" is English)."""
    chars = list(text)
    for start, end in _spans(_QUOTED, text) + _name_spans(text, names):
        chars[start:end] = " " * (end - start)
    return bool(_LT_ONLY.search("".join(chars)))


def plain_words(text: str, rooms: list[dict] | None = None) -> str:
    """One model-written text with the leaked English words in Lithuanian — or
    the text as written, when a reader of it would read something else."""
    if not isinstance(text, str) or not text:
        return text
    rooms = [r for r in (rooms or []) if isinstance(r, dict)]
    names = [str(r.get("pavadinimas") or "").strip() for r in rooms]
    if not _is_lithuanian(text, names):
        return text
    out = text
    for pattern, english_to_lt in _GLOSSARY:
        keep = _spans(_QUOTED, out) + _spans(_BACKTICKED, out) + _name_spans(out, names)

        def _sub(m: re.Match) -> str:
            if _inside(keep, m.start(), m.end()):
                return m.group(0)
            new = english_to_lt(m)
            return m.group(0) if new is None else new

        out = pattern.sub(_sub, out)
    if out != text and not _same_for_the_readers(text, out, rooms):
        return text
    return out


def normalise_model_warnings(parsed: dict, model_entries: list) -> int:
    """Rewrite, in place, the entries of `parsed["warnings"]` that are the
    model's own (`model_entries`: the Pass-1 list as it came back — the same
    dict / str objects, so a note the pipeline appended later is never touched).
    Returns how many texts changed."""
    ws = parsed.get("warnings") if isinstance(parsed, dict) else None
    if not isinstance(ws, list) or not model_entries:
        return 0
    rooms = [r for r in parsed.get("patalpos") or [] if isinstance(r, dict)]
    ids = room_identifiers(rooms)
    dicts = {id(e) for e in model_entries if isinstance(e, dict)}
    strings = {id(e) for e in model_entries if isinstance(e, str)}
    changed = 0
    for i, w in enumerate(ws):
        if isinstance(w, dict) and id(w) in dicts:
            msg = w.get("message")
            new = plain_numbers(plain_words(msg, rooms), ids, rooms)
            if new != msg:
                w["message"] = new
                changed += 1
        elif isinstance(w, str) and id(w) in strings:
            new = plain_numbers(plain_words(w, rooms), ids, rooms)
            if new != w:
                ws[i] = new
                changed += 1
    return changed
