"""GET /api/projects/{project_id}/pdf

Serves the project's source PDF for the viewer. Supports fixture mode
(``?fixture=berzas``) for demo/dev without auth or DB.

In production, the project's PDF bytes are stored in the database (or
behind auth-gated upload storage). Today the viewer needs ANY PDF to
load so the Annotator can render — the fixture path delivers exactly
that for the contractor-validated benchmark projects.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

REPO_ROOT = Path(__file__).resolve().parents[2]

# Map fixture slug → PDF on disk. Keep in sync with ground_truth/registry.yaml.
FIXTURE_PDFS = {
    "berzas":       REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf",
    "bacveviciaus": REPO_ROOT / "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 1/TP_Gytis ir Simona_2025naujausias.pdf",
    "ciurliu":      REPO_ROOT / "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 2/Techninio projekto planai_20250501 (a3)_2.pdf",
    "romainiai":    REPO_ROOT / "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 3/Deividas Norakitis INTERJERAS 4.1-5.1 punktas.pdf",
    "lazunu":       REPO_ROOT / "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 5/Apmatavimai-Layout4.pdf",
}


router = APIRouter(prefix="/api/projects", tags=["pdf"])


@router.get("/{project_id}/pdf")
def get_project_pdf(
    project_id: str,
    fixture: str | None = Query(default=None,
                                description="Demo fixture slug. Bypasses DB lookup."),
) -> FileResponse:
    """Stream the project's PDF. Fixture path takes precedence in dev mode.

    Returns 404 when:
      • fixture name unknown
      • fixture file missing on disk
      • (future) project ID not found in DB

    Browser sets Content-Disposition: inline so react-pdf can display it.
    """
    if fixture:
        path = FIXTURE_PDFS.get(fixture)
        if path is None:
            raise HTTPException(
                status_code=404,
                detail=f"unknown fixture {fixture!r}; "
                       f"known: {sorted(FIXTURE_PDFS.keys())}",
            )
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"fixture {fixture!r} PDF missing on disk: {path}",
            )
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=path.name,
            content_disposition_type="inline",
        )

    # TODO: when DB-backed projects ship, look up project_id → PDF bytes.
    raise HTTPException(
        status_code=404,
        detail=("DB-backed PDF lookup not implemented; "
                "supply ?fixture=<slug> to access fixture PDFs."),
    )
