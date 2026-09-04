"""Repo-wide confidentiality guard.

Everything a contractor hands over is confidential, and this repository is
public. Customer and project identifiers must therefore appear in NO tracked
file — not in code, comments, docstrings, tests, test ids, fixture or
directory names, slugs, eval output, docs, scripts or commit messages.

The denylist itself is the one thing that cannot live here: writing the terms
into a tracked test would be the leak it is meant to prevent. So the terms come
from outside git —

    backend/.confidential-terms   one term per line, `#` comments allowed
                                  (gitignored — never commit it), or
    SAMATU_CONFIDENTIAL_TERMS     newline- or comma-separated, for CI

— and when neither is present the test SKIPS. A skip is the honest outcome on a
checkout that has no list to check against; it is not a pass. Run it on a
machine that has the file (every dev machine does) before trusting a clean tree.

Matching is deliberately generous, because the leaks that survive a naive
`git grep` are the ones spelled differently:

  * case-insensitive               — `BERZAS`, `Berzas`, `berzas`
  * diacritics-insensitive         — a term written without Lithuanian
                                     diacritics still catches the diacritic
                                     spelling (`berz` finds `berž`)
  * homoglyph/transliteration-safe — 16 occurrences of the project name were
                                     found spelled with Cyrillic р and ж inside
                                     otherwise-Latin words, which every plain
                                     grep for the name walked straight past.
"""

from __future__ import annotations

import os
import subprocess
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TERMS_FILE = REPO_ROOT / "backend" / ".confidential-terms"
TERMS_ENV = "SAMATU_CONFIDENTIAL_TERMS"

# Binaries and rendered assets. Their bytes cannot be scrubbed without changing
# behaviour, and compressed streams throw off random letter runs that read as
# false positives (two tracked test PDFs do exactly that).
SKIP_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg",
    ".pdf", ".xlsx", ".xls", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".db", ".sqlite", ".sqlite3",
)

# Cyrillic letters → their Latin transliteration. Not a full transliteration
# table: just enough that a word typed with Cyrillic letters mixed into Latin
# ones folds to the same ascii skeleton as the honest spelling.
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "z", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "c", "ш": "s", "щ": "s", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "u", "я": "a",
}
_CYRILLIC_TABLE = str.maketrans(
    {**_CYRILLIC, **{k.upper(): v.upper() for k, v in _CYRILLIC.items()}}
)


def fold(text: str) -> str:
    """Lowercase, transliterate Cyrillic, strip diacritics.

    NFKD decomposition splits `ž` into `z` + a combining caron, and dropping
    every combining mark then covers all of ąčęėįšųūž in one step.
    """
    text = text.translate(_CYRILLIC_TABLE).lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def load_terms() -> list[str]:
    """Denylist from the environment, else the gitignored file, else empty."""
    raw = os.environ.get(TERMS_ENV)
    if raw is None and TERMS_FILE.is_file():
        raw = TERMS_FILE.read_text(encoding="utf-8")
    if not raw:
        return []
    terms: list[str] = []
    for chunk in raw.replace(",", "\n").split("\n"):
        term = chunk.strip()
        if not term or term.startswith("#"):
            continue
        folded = fold(term)
        if folded and folded not in terms:
            terms.append(folded)
    return terms


def tracked_text_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    files = []
    for name in out.split("\0"):
        if not name or name.lower().endswith(SKIP_SUFFIXES):
            continue
        path = REPO_ROOT / name
        # git tracks the name; the working tree may not have the file (sparse
        # checkout, a symlink to somewhere unreadable). Nothing to scan then.
        if path.is_file():
            files.append(path)
    return files


def test_no_confidential_terms_in_tracked_files():
    terms = load_terms()
    if not terms:
        pytest.skip(
            f"No confidentiality denylist available, so nothing was checked. "
            f"Provide {TERMS_FILE.relative_to(REPO_ROOT)} (one term per line, "
            f"gitignored) or set {TERMS_ENV}, then re-run — a skip here is NOT "
            f"evidence that the tree is clean."
        )

    offences: list[str] = []
    for path in tracked_text_files():
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue          # binary or unreadable — not a text leak
        if "\0" in content:
            continue          # binary that happens to decode
        if not any(term in fold(content) for term in terms):
            continue          # fast path: whole file is clean
        rel = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(content.split("\n"), 1):
            folded = fold(line)
            for term in terms:
                if term in folded:
                    offences.append(f"{rel}:{lineno}: matches {term!r}")

    assert not offences, (
        f"{len(offences)} confidential-identifier occurrence(s) in tracked "
        f"files. Customer and project identifiers must appear nowhere in this "
        f"repository — replace each with its codename (Objektas A/B/C/…), and "
        f"rename any file or directory whose PATH carries one:\n  "
        + "\n  ".join(offences)
    )
