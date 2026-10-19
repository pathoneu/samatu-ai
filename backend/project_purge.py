"""Remove the files a deleted project leaves behind (audit 2026-09-29).

DELETE /api/projects/{id} used to drop only the database row. The drawing
stayed in object storage and every store keyed by the project id kept its
files, so a project later created under the same id read them back, and the
privacy page's promise that deleting removes the files was not true.

Runs only AFTER the owner-scoped database delete succeeded. Every step is
best-effort and safe to repeat: a failure is logged, the remaining steps still
run, and nothing here can bring the project back.

`delete_project_and_files` is THE project delete — the row, then this purge.
DELETE /api/projects/{id} and the account deletion both call it (2026-10-05:
they used to repeat the same two calls, each promising to stay in step with
the other).

Purged: the stored PDF and its later editions (api/pdf_revisions), the in-memory PDF byte caches (CV tools and evidence
crops), the CV page renders of that PDF, annotations, calibrations, the symbol
legend, the evidence crops on disk, the F2/F3 line override and any re-read
the server holds for the project on its extraction job row (2026-10-03: it
otherwise stayed for the 3-day hold), and (v3 M8, 2026-10-18) the
symbol-training crops of the project. Account deletion additionally runs
`purge_account_files`: the per-owner architect legends.
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


def _purge_revisions(project_id: str, backend) -> None:
    """The later editions of the drawing (api/pdf_revisions), each under its own key."""
    from api import pdf_revisions
    for key, _size in list(backend.list_keys(pdf_revisions.revision_prefix(project_id))):
        backend.delete(key)
    pdf_revisions._forget(project_id)


def purge_project_files(project_id: str) -> list[str]:
    """Delete everything stored under `project_id` besides its projects row
    (which the caller already deleted).

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
    step("pdf_revisions", lambda: _purge_revisions(project_id, backend))
    from api import evidence
    step("evidence_memory", lambda: evidence.forget_project(project_id))
    # A parameterised UPDATE, so any id is safe here (no path is built).
    import db
    step("held_rereads", lambda: db.drop_held_extraction_results(project_id))

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
    # v3 M8 (2026-10-18): the symbol-training crops of this project — its own
    # folder, plus legacy root-level crops whose log line names it.
    from extractor import training_data
    step("symbol_training", lambda: training_data.purge_project(project_id))
    return failed


def purge_account_files(user_id: str) -> list[str]:
    """Files keyed by the ACCOUNT, not by a project: the per-owner architect
    legends (`<legends>/architect/<user id>/`, W2-A's layout in api/legends.py,
    read here through its ARCHITECT_DIR so the two never drift). Runs after the
    account deletion committed; best-effort, safe to repeat. Returns the steps
    that failed."""
    failed: list[str] = []
    if not user_id:
        return failed
    try:
        from api import legends
        root = Path(getattr(legends, "ARCHITECT_DIR", Path(legends.LEGENDS_DIR) / "architect"))
        # The folder name is the one the legend routes write under
        # (`_owner_key`: path-unsafe characters → "_"), never the raw id.
        owner_key = getattr(legends, "_owner_key", None)
        folder = owner_key({"id": user_id}) if callable(owner_key) else user_id
        if not _plain_id(folder):
            return failed
        _rmtree_inside(root, root / folder)
    except Exception as exc:  # noqa: BLE001
        log.warning("account purge: architect legends failed for %s: %r", user_id, exc)
        failed.append("architect_legends")
    return failed


def delete_project_and_files(project_id: str, user_id: str | None = None) -> bool:
    """Delete one project: its row, then — only when that removed a row — the
    best-effort purge of its drawing and every id-keyed store.

    `user_id` scopes the row delete to that owner; None deletes whoever owns
    it (an admin's DELETE /api/projects/{id}). An empty id is refused rather
    than read as None, which would widen an owner's delete to every project.
    Returns whether a row was deleted. A purge failure is logged and never
    brings the project back."""
    import db
    if user_id is not None and (not isinstance(user_id, str) or not user_id):
        raise ValueError("an owner-scoped project delete needs a non-empty user_id")
    if not db.delete_project(project_id, user_id=user_id):
        return False
    try:
        purge_project_files(project_id)
    except Exception as exc:  # noqa: BLE001 — the row is gone; files are best-effort
        log.warning("project purge failed for %s: %r", project_id, exc)
    return True
