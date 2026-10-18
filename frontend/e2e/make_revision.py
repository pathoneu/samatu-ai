"""A synthetic "later edition" of a drawing for the founder-guide smoke suite (step 9).

    python make_revision.py <source.pdf> <out.pdf>

Sheet 1 is shifted 25 pt right and 15 pt up, gets one added bar and loses the lines under a small white
patch; every other sheet is copied as it is (the guide's „Palyginti leidimus" was verified on togal-v2 W10
with the shift and the bar; the patch adds removed lines, which alignment by walls cannot absorb).
The output stays in the suite's gitignored results folder: it is the project's own drawing, never
committed and never sent anywhere but the local backend.

Needs pikepdf (backend/requirements-dev.lock, installed in the repo venv).
"""
import sys

import pikepdf


def main(src: str, dst: str) -> None:
    with pikepdf.open(src) as pdf:
        page = pdf.pages[0]
        page.contents_coalesce()
        prefix = pdf.make_stream(b"q 1 0 0 1 25 15 cm\n")
        # after the shifted content, in the unshifted page frame: one added bar ("nauja") and a white
        # patch over part of the plan, so some of its lines are gone in this edition ("išbraukta")
        suffix = pdf.make_stream(b"\nQ\nq 0 0 0 rg 120 200 260 6 re f Q\nq 1 1 1 rg 300 450 60 40 re f Q\n")
        page.obj.Contents = pikepdf.Array([prefix, page.obj.Contents, suffix])
        pdf.save(dst)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: make_revision.py <source.pdf> <out.pdf>")
    main(sys.argv[1], sys.argv[2])
