"""POST /api/intake/combine — several drawings (PDFs, PNG / JPG / TIFF pictures) into ONE PDF for a new project
(Pathon v3 W5-D, D14; extractor/intake.py).

The New Project page calls it when more than one file, or a picture, is chosen, and then goes on exactly as with
one PDF — the preflight, the reading and the viewer all get the one combined file. €0, saves nothing. Answers
the PDF itself; which file each page came from rides in the `X-Pathon-Lapai` header as percent-encoded JSON
({"lapai": [{page, failas, failo_lapas, lapu_faile}], "pavadinimai": {page: name}}) so the sheets can be named after
their files. Login required, rate-limited like the other PDF handlers; the combined PDF passes the same upload
checks a single PDF does (size, page count, page dimensions).
"""
from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

import auth as _auth
from extractor.intake import IntakeError, MAX_FILES, combine, sheet_names

log = logging.getLogger("samatu.intake")

router = APIRouter(prefix="/api/intake", tags=["intake"])


@router.post("/combine")
async def api_intake_combine(request: Request, files: list[UploadFile] = File(...)):
    _auth.require_user(request)
    from main import MAX_PDF_SIZE_BYTES, _check_rate_limit, _client_key, _validate_pdf_upload
    _check_rate_limit(_client_key(request), "intake")
    if not files:
        raise HTTPException(status_code=400, detail="Nepateikta jokio failo.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Vienu kartu galima įkelti iki {MAX_FILES} failų.")
    got: list[tuple[str, bytes]] = []
    total = 0
    for f in files:
        name = f.filename or "failas"
        if ".." in name or name.startswith("/"):
            raise HTTPException(status_code=400, detail="Neleistinas failo pavadinimas.")
        data = await f.read()
        total += len(data)
        if total > MAX_PDF_SIZE_BYTES:
            raise HTTPException(status_code=413, detail=f"Failai kartu per dideli. Maksimumas {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB.")
        got.append((name, data))
    try:
        res = await asyncio.to_thread(combine, got)          # PDFium + Pillow: blocking work
    except IntakeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:  # noqa: BLE001
        log.exception("intake combine failed")
        raise HTTPException(status_code=500, detail="Failų sujungti nepavyko — bandykite įkelti juos po vieną.")
    _validate_pdf_upload(res["pdf"], "sujungta.pdf")
    meta = {"lapai": res["lapai"], "pavadinimai": sheet_names(res["lapai"])}
    return Response(content=res["pdf"], media_type="application/pdf",
                    headers={"X-Pathon-Lapai": quote(json.dumps(meta, ensure_ascii=False)),
                             "Access-Control-Expose-Headers": "X-Pathon-Lapai"})
