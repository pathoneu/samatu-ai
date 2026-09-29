"""Remove the files a deleted project leaves behind (audit 2026-09-29).

DELETE /api/projects/{id} used to drop only the database row. The drawing
stayed in object storage and every store keyed by the project id kept its
files, so a project later created under the same id read them back, and the
privacy page's promise that deleting removes the files was not true.

Runs only AFTER the owner-scoped database delete succeeded. Every step is
best-effort and safe to repeat: a failure is logged, the remaining steps still
run, and nothing here can bring the project back.

Purged: the stored PDF, the in-memory PDF byte caches (CV tools and evidence
crops), the CV page renders of that PDF, annotations, calibrations, the symbol
legend, the evidence crops on disk and the F2/F3 line override. Not purged (see the audit report): symbol-training
crops (append-only corpus keyed by class, the id is only in its log) and the
per-architect legend aggregate (keyed by architect, not by project).
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger("samatu.purge")


def _plain_id(project_id: str) -> bool:
    """The rule the id-keyed file stores already enforce on write
    (annotations, calibrations, evidence cache): anything else never had a
    file there, and must never be joined into a path here."""
    return bool(project_id) and all(c.isalnum() or c in "-_" for c in project_id)


def _unlink_inside(root: Path, path: Path) -> None:
    if path.resolve().is_relative_to(Path(root).resolve()):
        path.unlink(missing_ok=True)


def _rmtree_inside(root: Path, path: Path) -> None:
    root_r, path_r = Path(root).resolve(), path.resolve()
    if path_r != root_r and path_r.is_relative_to(root_r) and path_r.is_dir():
        shutil.rmtree(path_r)


def _purge_cv_renders(project_id: str, pdf_bytes: bytes | None, backend) -> None:
    """CV page renders are keyed by the PDF's content hash, so the bytes are
    needed to name them. Skip the storage read when nothing is rendered."""
    from extractor import cv_render_cache as cv
    from storage import pdf_key
    cache_dir = Path(cv.CACHE_DIR)
    if not cache_dir.is_dir() or next(cache_dir.glob("*.png"), None) is None:
        return
    if pdf_bytes is None:
        pdf_bytes = backend.get(pdf_key(project_id))
    if not pdf_bytes:
        return
    digest = cv.cache_key(pdf_bytes, 0, 0).split("_p", 1)[0]
    for p in cache_dir.glob(f"{digest}_p*_dpi*.png"):
        p.unlink(missing_ok=True)


def purge_project_files(project_id: str) -> list[str]:
    """Delete everything stored under `project_id` outside the database.

    Returns the names of the steps that failed (empty list = all clean).
    """
    import page_raster_cache
    from storage import get_storage, pdf_key

    failed: list[str] = []

    def step(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — one store must not stop the rest
            log.warning("project purge: %s failed for %s: %r", name, project_id, exc)
            failed.append(name)

    cached = page_raster_cache.drop_pdf(project_id)
    backend = get_storage()
    # Before the PDF itself: the renders are named by the PDF's bytes.
    step("cv_cache", lambda: _purge_cv_renders(project_id, cached, backend))
    step("pdf", lambda: backend.delete(pdf_key(project_id)))
    from api import evidence
    step("evidence_memory", lambda: evidence.forget_project(project_id))

    if not _plain_id(project_id):
        return failed
    from api import annotations, calibrate, exports_v2, legends
    step("annotations", lambda: _unlink_inside(
        annotations.DATA_ROOT, annotations.DATA_ROOT / f"{project_id}.json"))
    step("calibrations", lambda: _unlink_inside(
        calibrate.CALIB_ROOT, calibrate.CALIB_ROOT / f"{project_id}.json"))
    step("legends", lambda: _unlink_inside(
        legends.LEGENDS_DIR, legends.LEGENDS_DIR / f"{project_id}.json"))
    step("evidence_cache", lambda: _rmtree_inside(
        evidence.CACHE_ROOT, evidence.CACHE_ROOT / project_id))
    step("exports", lambda: _rmtree_inside(
        exports_v2.PROJECTS_DIR, exports_v2.PROJECTS_DIR / project_id))
    return failed
