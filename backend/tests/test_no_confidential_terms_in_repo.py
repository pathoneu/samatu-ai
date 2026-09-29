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
`git grep` are the ones spelled differently. Using a stand-in term to show the
three shapes (never a real one — that is the whole point):

  * case-insensitive               — `ĄŽUOLAS`, `Ąžuolas`, `ąžuolas` all match
                                     the one entry. `grep -i` does NOT do this
                                     for multi-byte Lithuanian letters, which
                                     is how an uppercase spelling survived the
                                     mechanical cleanup that preceded this test.
  * diacritics-insensitive         — an entry written in plain ascii still
                                     catches the diacritic spelling
                                     (`azuol` finds `ąžuol`)
  * homoglyph/transliteration-safe — 16 occurrences of one project name were
                                     found spelled with Cyrillic letters inside
                                     otherwise-Latin words: visually identical,
                                     and invisible to every plain grep anyone
                                     had run for that name.

Scope is `git ls-files`, so a file is checked only once it is TRACKED. A new
file you have not staged yet is invisible to this test — stage it, then re-run.
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
# false positives (two tracked test PDFs do exactly that). PDFs are still
# checked — by their TEXT LAYER, in the second test below.
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


def tracked_pdfs() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO_ROOT / n for n in out.split("\0")
            if n.lower().endswith(".pdf") and (REPO_ROOT / n).is_file()]


def test_no_confidential_terms_in_tracked_pdf_text():
    """The text layer and metadata of every tracked PDF (audit 2026-09-29).

    Skipping `.pdf` above let a tracked sample drawing carry an identifier in
    its title block on 16 of 17 sheets while this guard stayed green. The
    extracted text has none of the compressed-stream noise, so it is matched
    like any text file. The failure names the denylist ENTRY NUMBER, not the
    term, so the term never lands in a test log.
    """
    terms = load_terms()
    if not terms:
        pytest.skip("No confidentiality denylist available — see the test above.")
    import pypdfium2 as pdfium

    offences: list[str] = []
    for path in tracked_pdfs():
        rel = path.relative_to(REPO_ROOT)
        doc = pdfium.PdfDocument(str(path))
        try:
            texts = [("metadata", " ".join(
                str(v) for v in (doc.get_metadata_dict() or {}).values()))]
            for i in range(len(doc)):
                page = doc[i]
                texts.append((f"page {i + 1}", page.get_textpage().get_text_range()))
            for where, text in texts:
                folded = fold(text)
                for n, term in enumerate(terms, 1):
                    if term in folded:
                        offences.append(f"{rel} ({where}): denylist entry #{n}")
        finally:
            doc.close()

    assert not offences, (
        f"{len(offences)} confidential-identifier occurrence(s) in the text of "
        f"tracked PDFs. Replace the file with a synthetic one (see "
        f"backend/tests/synthetic_plan_pdf.py), untrack it and gitignore it:\n  "
        + "\n  ".join(offences)
    )
