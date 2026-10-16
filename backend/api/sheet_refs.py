"""Sheet references in a drawing's text layer — pure matching, no I/O (Togal-v2 W7, research §1).

A sheet set refers to itself: „žr. lapą A-03", „žiūrėti iškl.", „Rozečių pririšimus tikslinti
išklotinėse", an elevation tag „g2" on the finishes plan that is drawn on the sheet named
„Išklotinės g1-g7", „PJŪVIS A-A" on a plan whose section is its own sheet. Togal turns those into
links. This module finds them in the lines of ONE page and resolves each to another page of the
same PDF; `api/sheet_links.py` feeds it the text layer (pypdfium2) and the sheet names.

What a sheet is known by (`build_sheet_index`):
  * its name — the classification's `pavadinimas` (an AI reading of the title block) or the name the
    user gave it (`sheet_overrides`), whichever the rail shows;
  * its number — the code the name starts with („IN.1A.-B.01 …" → IN.1A.-B.01 and B.01) and the
    code printed in its own title block („B.01", „LVN-03"), read from the text layer;
  * its type — the classification's `tipas` or the user's;
  * the tags its name declares („Išklotinės b1-b3, c1-c4" → b1 b2 b3 c1 … c4).

Rules, strongest first; a span is claimed once (`find_callouts`):
  1. explicit — a „see" word, then a sheet word and a number: „žr. lapą 3", „žr. br. LVN-03".
  2. number — a token equal to another sheet's number („B.08").
  3. tag — a token equal to a tag another sheet's name declares („g2"), case kept.
  4. label — „PJŪVIS A-A", „MAZGAS B", „DETALĖ STD-04" or a bare „A-A" where another sheet's NAME
     carries the same label (the section drawn as its own sheet).
  5. type — a word that names a kind of sheet in a referring form („iškl.", „išklotinėse",
     „lubų planą", „detalizaciją") → the sheets of that type. Several sheets → the first, the rest in
     `other_pages`, confidence `low`.
  6. name — another sheet's full name (two words or more) written on this page.

Never a link to the page itself: a sheet's own title block names it.

Confidence says how the target was found, for the hover text: `high` — a written reference with a
number that matches exactly; `medium` — one sheet answers; `low` — several sheets could be meant.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Sequence

# Title block: the lower-right corner of the sheet (page_classifier._ANTSPAUDAS_BBOX, same corner).
TITLE_BLOCK = (0.40, 0.70, 1.00, 1.00)

_FOLD = str.maketrans("ąčęėįšųūž", "aceeisuuz")


def fold(text: str) -> str:
    """Case- and diacritic-free form for comparing Lithuanian words („IŠKLOTINĖS" == „isklotines")."""
    return unicodedata.normalize("NFC", text or "").casefold().translate(_FOLD)


# A sheet number: letters, then a . or - and digits („B.01", „A-03", „LVN-03", „SA-02",
# „IN.1A.-B.01"). A bare „3" is a page and „A3" a paper size, not a number.
_CODE = r"[A-ZĄČĘĖĮŠŲŪŽ]{1,4}(?:[.\-]{1,2}[0-9A-ZĄČĘĖĮŠŲŪŽ]{1,4})*[.\-]\d{1,3}"
_CODE_RE = re.compile(rf"^{_CODE}$")
# A name that starts with its number: „IN.1A.-B.01 1A. BALDŲ PLANAS M 1:50".
_LEADING_CODE_RE = re.compile(rf"^\s*({_CODE})\s+(.+)$")
_SCALE_RE = re.compile(r"\bM\s*1\s*:\s*\d+\b", re.I)


def split_code(name: str) -> tuple[str | None, str]:
    """(number, title) of a sheet name. The number is the leading code, when the name has one."""
    m = _LEADING_CODE_RE.match(name or "")
    if m and re.search(r"\d", m.group(1)) and re.search(r"[A-Za-zĄ-ž]", m.group(1)):
        return m.group(1), m.group(2).strip()
    return None, (name or "").strip()


def code_aliases(code: str | None) -> set[str]:
    """The ways a number is written: the whole code and its last segment („IN.1A.-B.01" → also
    „B.01"). Folded. A segment without a letter or a digit is not a number on its own."""
    if not code:
        return set()
    out = {fold(code)}
    tail = re.split(r"[.\-]{0,2}-", code)[-1]
    if tail and re.search(r"\d", tail) and re.search(r"[A-Za-zĄ-ž]", tail) and len(tail) >= 3:
        out.add(fold(tail))
    return out


# „b1-b3, c1-c4", „a1-a9", „d1-d4" — the tags an elevation sheet's name declares.
_TAG_RANGE_RE = re.compile(r"\b([a-zA-Z])(\d{1,2})\s*[-–]\s*\1(\d{1,2})\b")
_TAG_RE = re.compile(r"^[a-zA-Z]\d{1,2}$")


def declared_tags(name: str) -> set[str]:
    out: set[str] = set()
    for letter, a, b in _TAG_RANGE_RE.findall(name or ""):
        lo, hi = sorted((int(a), int(b)))
        if hi - lo > 40:
            continue
        out.update(f"{letter}{i}" for i in range(lo, hi + 1))
    return out


def _title_words(title: str) -> str:
    """The words of a sheet name that identify it: no number, no scale, no punctuation."""
    t = _SCALE_RE.sub(" ", title or "")
    t = re.sub(r"[^\wĄ-ž]+", " ", fold(t))
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Sheet:
    page: int
    name: str
    tipas: str = "unknown"
    numbers: set[str] = field(default_factory=set)   # folded
    tags: set[str] = field(default_factory=set)      # case kept
    words: str = ""                                  # folded title words, for rules 4 and 6


def build_sheet_index(sheets: Iterable[dict], title_codes: dict[int, Sequence[str]] | None = None) -> list[Sheet]:
    """sheets: [{page, name, tipas}] (the rail's view: overrides already applied).
    title_codes: {page: [codes read from that page's title block]}."""
    out: list[Sheet] = []
    for s in sheets:
        try:
            page = int(s.get("page"))
        except (TypeError, ValueError):
            continue
        name = str(s.get("name") or "").strip()
        code, title = split_code(name)
        numbers = code_aliases(code)
        for c in (title_codes or {}).get(page, ()):
            numbers |= code_aliases(c)
        out.append(Sheet(page=page, name=name, tipas=str(s.get("tipas") or "unknown"),
                         numbers=numbers, tags=declared_tags(name), words=_title_words(title)))
    # A code printed on several sheets is the DOCUMENT's number („SA.B-02" on every elevation of
    # one bundle), not a sheet's — it identifies none of them.
    seen: dict[str, int] = {}
    for s in out:
        for n in s.numbers:
            seen[n] = seen.get(n, 0) + 1
    for s in out:
        s.numbers = {n for n in s.numbers if seen[n] == 1}
    return out


# ── the text of a page ─────────────────────────────────────────────────────────

Box = tuple[float, float, float, float]   # x0, top, x1, bottom — top-origin points


def line_text(chars: Sequence[dict]) -> tuple[str, list[Box | None]]:
    """One text line from its characters (sorted left to right): the string and, per character, its
    box. A space is inserted where two characters stand further apart than 0.3 em (min 1 pt) — the
    same word rule as plan_area_annotations._words — and has no box."""
    text: list[str] = []
    boxes: list[Box | None] = []
    prev_x1: float | None = None
    for c in chars:
        t = str(c.get("text") or "")
        if not t:
            continue
        size = float(c.get("size") or 0)
        x0, x1 = float(c["x0"]), float(c["x1"])
        if prev_x1 is not None and not t.isspace() and x0 - prev_x1 > max(1.0, 0.3 * size) \
                and text and not text[-1].isspace():
            text.append(" ")
            boxes.append(None)
        for ch in t:
            text.append(ch)
            boxes.append(None if ch.isspace() else (x0, float(c["top"]), x1, float(c["bottom"])))
        prev_x1 = x1
    return unicodedata.normalize("NFC", "".join(text)), boxes


def span_box(boxes: Sequence[Box | None], i0: int, i1: int) -> Box | None:
    got = [b for b in boxes[i0:i1] if b is not None]
    if not got:
        return None
    return (min(b[0] for b in got), min(b[1] for b in got), max(b[2] for b in got), max(b[3] for b in got))


def title_block_codes(lines: Sequence[tuple[str, Sequence[Box | None]]], width: float, height: float) -> list[str]:
    """Sheet-number-like tokens printed in the title block corner, nearest the corner first."""
    x0, y0, _, _ = TITLE_BLOCK
    found: list[tuple[float, str]] = []
    for text, boxes in lines:
        for m in re.finditer(r"\S+", text):
            tok = m.group(0).strip(",;:()")
            if not _CODE_RE.match(tok):
                continue
            b = span_box(boxes, m.start(), m.end())
            if not b or b[0] < x0 * width or b[1] < y0 * height:
                continue
            found.append(((width - b[2]) + (height - b[3]), tok))
    return [tok for _, tok in sorted(found)]


# ── matching ──────────────────────────────────────────────────────────────────

# „see" words: žr., žiūr., žiūrėti, žiūrėkite, pagal, tikslinti, nurodyta, parodyta, detalizuota.
_SEE = r"(?:žr\.?|žiūr(?:ėti|ėkite|ėk|\.)?|pagal|tikslinti|nurodyt[ai]|parodyt[ai]|detalizuot[ai])"
_SHEET_WORD = r"(?:lap(?:ą|e|o|as|uose|us|ai)|br\.|brėž(?:inį|inyje|inys|iniuose|inius|\.)?)"
_EXPLICIT_RE = re.compile(
    rf"{_SEE}\s*{_SHEET_WORD}\s*(?:nr\.?\s*)?(?P<code>{_CODE}|\d{{1,3}})(?![\w.])",
    re.I,
)
_LABEL_RE = re.compile(
    r"(?P<kind>pjūvi[sos]|pjūvį|mazg(?:as|o|ą)|detal(?:ė|ės|ę)|pav\.?)\s+(?P<id>[A-Z0-9]{1,4}(?:[.\-][A-Z0-9]{1,4})?)(?![\w])",
    re.I,
)
_SECTION_MARK_RE = re.compile(r"(?<![\w.\-])(?P<id>([A-Z0-9])-\2)(?![\w.\-])")
_LABEL_KIND = ("pjuv", "mazg", "detal", "pav")


def _plain(folded: str) -> str:
    """Punctuation → spaces, length kept (so a match's span is a span of the line)."""
    return re.sub(r"[^\w]", " ", folded)

# Rule 5: (folded pattern of the referring word, which sheets it means). A pattern must be a
# referring FORM — „išklotinėse", „iškl.", „lubų planą" — never the nominative a title uses.
_TYPE_WORDS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\biskl(?:\.|otinese|otines|otinej|otiniu|otinyje|otine)(?![a-z])"), {"tipas": {"wall_elevation"}}),
    (re.compile(r"\blubu plan(?:a|e|uose)\b"), {"tipas": {"ceiling_plan"}}),
    (re.compile(r"\bgrindu (?:dangu )?plan(?:a|e|uose)\b"), {"words": "grindu"}),
    (re.compile(r"\bpertvaru plan(?:a|e|uose)\b"), {"words": "pertvaru"}),
    (re.compile(r"\bbaldu plan(?:a|e|uose)\b"), {"words": "baldu"}),
    (re.compile(r"\b(?:apsvietimo|elektros) plan(?:a|e|uose)\b"), {"tipas": {"electrical"}}),
    (re.compile(r"\bsantechnikos plan(?:a|e|uose)\b"), {"tipas": {"plumbing"}}),
    (re.compile(r"\beksplikacij(?:a|oje|os)\b"), {"tipas": {"eksplikacija"}}),
    (re.compile(r"\bdetalizacij(?:a|oje|ose|as)\b"), {"words": "detal"}),
    (re.compile(r"\b(?:langu|duru)(?: ir (?:langu|duru))? (?:specifikacij|ziniarast)\w*"),
     {"tipas": {"door_window_schedule"}, "words": "lang"}),
    (re.compile(r"\bspecifikacij(?:oje|ose|a|as)\b"),
     {"tipas": {"specification", "finish_schedule", "door_window_schedule"}}),
]
# Rule 5 needs a „see" word close before it, except for forms that only a reference uses.
_SEE_FOLDED_RE = re.compile(r"\b(?:zr\.?|ziur\w*|pagal|tikslinti|nurodyt\w*|parodyt\w*|detalizuot\w*)\s*$")
_LOCATIVE_ONLY = re.compile(r"(?:ese|uose|oje|yje|ose)$|^iskl\.$")


@dataclass
class Callout:
    line: int
    start: int
    end: int
    text: str
    target_page: int
    confidence: str
    kind: str
    other_pages: list[int] = field(default_factory=list)


def _by_number(index: Sequence[Sheet], token: str) -> list[Sheet]:
    t = fold(token.strip(".,;:()"))
    return [s for s in index if t in s.numbers]


def _overlaps(taken: list[tuple[int, int, int]], line: int, a: int, b: int) -> bool:
    return any(li == line and a < tb and ta < b for li, ta, tb in taken)


def _type_targets(index: Sequence[Sheet], want: dict, page: int) -> list[Sheet]:
    tipas = want.get("tipas") or set()
    words = want.get("words")
    out = []
    for s in index:
        if s.page == page:
            continue
        if (tipas and s.tipas in tipas) or (words and words in s.words):
            out.append(s)
    return out


def find_callouts(page: int, lines: Sequence[tuple[str, Sequence[Box | None]]],
                  index: Sequence[Sheet], page_count: int | None = None) -> list[Callout]:
    """Every reference on `page` to another sheet in `index`. `lines` are (text, boxes) pairs
    from `line_text`; spans are character ranges into a line's text."""
    others = [s for s in index if s.page != page]
    me = next((s for s in index if s.page == page), None)
    if not others:
        return []
    out: list[Callout] = []
    taken: list[tuple[int, int, int]] = []

    def add(li: int, a: int, b: int, text: str, targets: list[Sheet], confidence: str, kind: str) -> None:
        targets = [t for t in targets if t.page != page]
        if not targets or _overlaps(taken, li, a, b):
            return
        targets = sorted(targets, key=lambda s: s.page)
        if len(targets) > 1 and confidence != "low":
            confidence = "low"
        out.append(Callout(li, a, b, text[a:b].strip(), targets[0].page, confidence, kind,
                           [t.page for t in targets[1:]]))
        taken.append((li, a, b))

    for li, (text, _boxes) in enumerate(lines):
        # 1. explicit: „žr. lapą 3", „žr. br. LVN-03"
        for m in _EXPLICIT_RE.finditer(text):
            code = m.group("code")
            targets = _by_number(others, code)
            confidence = "high"
            if not targets and code.isdigit():
                n = int(code)
                targets = [s for s in others if any(re.search(rf"(?<!\d)0*{n}$", x) for x in s.numbers)]
                if not targets and (page_count is None or 1 <= n <= page_count):
                    targets = [s for s in others if s.page == n]
                    confidence = "medium"
            add(li, m.start(), m.end(), text, targets, confidence, "nuoroda")

    for li, (text, _boxes) in enumerate(lines):
        for m in re.finditer(r"[^\s,;:()/]+", text):
            tok = m.group(0)
            core = tok.rstrip(".")
            a, b = m.start(), m.start() + len(core)
            # 2. number
            if _CODE_RE.match(core) and re.search(r"[A-Za-zĄ-ž]", core):
                hits = _by_number(others, core)
                if hits:
                    add(li, a, b, text, hits, "medium", "numeris")
                    continue
            # 3. tag declared by another sheet's name (case kept: „A1" is a paper size, „a1" a tag)
            if _TAG_RE.match(core):
                hits = [s for s in others if core in s.tags]
                if hits and not (me and core in me.tags):
                    add(li, a, b, text, hits, "medium", "zyma")

    for li, (text, _boxes) in enumerate(lines):
        # 4. labels: „PJŪVIS A-A", „MAZGAS B", „DETALĖ STD-04", a bare „A-A"
        for m in _LABEL_RE.finditer(text):
            stem = next((k for k in _LABEL_KIND if fold(m.group("kind")).startswith(k)), None)
            if stem is None:
                continue
            pat = re.compile(rf"\b{stem}\w*\s+{re.escape(fold(m.group('id')))}\b")
            hits = [s for s in others if pat.search(re.sub(r"[^\w\-]", " ", fold(s.name)))]
            add(li, m.start(), m.end(), text, hits, "medium", "detale")
        for m in _SECTION_MARK_RE.finditer(text):
            ident = fold(m.group("id"))
            hits = [s for s in others if re.search(rf"(?<![\w-]){re.escape(ident)}(?![\w-])", fold(s.name))]
            add(li, m.start(), m.end(), text, hits, "medium", "pjuvis")

    for li, (text, _boxes) in enumerate(lines):
        folded = fold(text)   # same length as text: the fold maps one character to one
        if len(folded) != len(text):
            continue
        # 5. a kind of sheet named in a referring form
        for pat, want in _TYPE_WORDS:
            for m in pat.finditer(folded):
                word = m.group(0).split()[-1]
                before = folded[max(0, m.start() - 30):m.start()]
                see = _SEE_FOLDED_RE.search(before)
                if not see and not _LOCATIVE_ONLY.search(word):
                    continue
                if me is not None and want.get("tipas") and me.tipas in want["tipas"] and not want.get("words"):
                    continue      # an elevation sheet speaking of „išklotinės" means itself
                a = max(0, m.start() - 30) + see.start() if see else m.start()
                add(li, a, m.end(), text, _type_targets(index, want, page), "medium", "tipas")
        # 6. another sheet's full name (punctuation and spacing may differ)
        plain = _plain(folded)
        for s in others:
            if len(s.words) < 10 or " " not in s.words:
                continue
            m = re.search(r"(?<!\w)" + r"\s+".join(map(re.escape, s.words.split())) + r"(?!\w)", plain)
            if m:
                add(li, m.start(), m.end(), text, [s], "medium", "pavadinimas")

    out.sort(key=lambda c: (c.line, c.start))
    return out
