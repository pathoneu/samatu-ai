"""Durable object storage for user-uploaded PDFs (2026-06-21 durability track).

The source drawing used to live ONLY in the uploader's browser (IndexedDB,
frontend/src/lib/pdfStore.js), so a cache-clear / device-switch / share link lost
it — the #1 "browser tool vs cloud product" gap from the commercial audit. This
persists the bytes server-side; the browser cache becomes an optimization, not the
only copy.

Two interchangeable backends, chosen by environment (see `r2_decision`):
  - R2Storage      — Cloudflare R2 (S3-compatible, via boto3) when the four R2_*
                     vars are set AND this process is allowed to use them
                     (ENV=production, or an explicit STORAGE_BACKEND=r2). Zero
                     egress, scales with success.
  - LocalDiskStorage — a directory under backend/data/pdf_store. The default for
                     dev + the test suite EVEN WHEN R2 credentials are present;
                     needs no credentials, so everything below is fully testable
                     without R2.

Keys are namespaced, e.g. "projects/<project_id>.pdf".
"""
from __future__ import annotations

import logging
import os
import pathlib
import threading

log = logging.getLogger("samatu.storage")


class StorageError(Exception):
    """Raised on a hard storage failure (callers may degrade gracefully)."""


def data_path(subdir: str, legacy: pathlib.Path | str) -> pathlib.Path:
    """Root a server-writable data directory.

    2026-07-27 audit (finding 6): annotations / calibrations / F2-F3 project
    lines / the local PDF store all wrote INSIDE the container image, so on
    Render every one of them died with the container. They now share ONE knob —
    set SAMATU_DATA_DIR to the persistent disk mount and all four follow.

    Unset (dev, tests, CI) → the legacy in-repo path, byte-for-byte unchanged.
    """
    base = os.environ.get("SAMATU_DATA_DIR")
    return (pathlib.Path(base) / subdir) if base else pathlib.Path(legacy)


class _Backend:
    def put(self, key: str, data: bytes, content_type: str = "application/pdf") -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def stat(self, key: str) -> dict | None:
        """Cheap metadata WITHOUT downloading the object.

        Returns {"size": int, "mtime": float|None, "etag": str|None} or None when
        the key is missing. Used to build an HTTP ETag so a conditional GET can
        answer 304 without reading (or, on R2, paying egress for) the bytes.
        Backends that can't answer cheaply may return None — callers must treat
        that as "no cheap validator available", not as "missing".
        """
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return type(self).__name__


def _safe_key(key: str) -> str:
    """Block path traversal for the local backend; harmless for R2."""
    return key.replace("..", "_").lstrip("/")


class LocalDiskStorage(_Backend):
    def __init__(self, root: str):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> pathlib.Path:
        p = self.root / _safe_key(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/pdf") -> None:
        # atomic-ish write (tmp + replace) so a partial write never serves a half file
        p = self._path(key)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)

    def get(self, key: str) -> bytes | None:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def stat(self, key: str) -> dict | None:
        p = self._path(key)
        try:
            st = p.stat()
        except OSError:
            return None
        return {"size": st.st_size, "mtime": st.st_mtime, "etag": None}

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


class R2Storage(_Backend):
    def __init__(self, account_id: str, access_key: str, secret_key: str, bucket: str,
                 key_prefix: str = ""):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        # R2_KEY_PREFIX (2026-09-16): a second deployment (the Railway `dev`
        # environment) can share the production bucket under its own prefix,
        # e.g. "dev/", instead of mixing its test objects into `projects/`.
        # Empty for production — keys stay exactly as they were.
        prefix = key_prefix.strip().strip("/")
        self.key_prefix = prefix + "/" if prefix else ""
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def _k(self, key: str) -> str:
        return self.key_prefix + key

    def put(self, key: str, data: bytes, content_type: str = "application/pdf") -> None:
        self._client.put_object(Bucket=self.bucket, Key=self._k(key), Body=data, ContentType=content_type)

    def _is_missing(self, exc: Exception) -> bool:
        from botocore.exceptions import ClientError
        if isinstance(exc, ClientError):
            code = str(exc.response.get("Error", {}).get("Code", ""))
            return code in ("NoSuchKey", "404", "NotFound")
        return False

    def get(self, key: str) -> bytes | None:
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=self._k(key))
            return resp["Body"].read()
        except Exception as exc:  # noqa: BLE001
            if self._is_missing(exc):
                return None
            raise StorageError(f"R2 get failed for {key}") from exc

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._k(key))
            return True
        except Exception:  # noqa: BLE001
            return False

    def stat(self, key: str) -> dict | None:
        try:
            resp = self._client.head_object(Bucket=self.bucket, Key=self._k(key))
        except Exception:  # noqa: BLE001 — missing key or transient R2 error
            return None
        lm = resp.get("LastModified")
        return {
            "size": int(resp.get("ContentLength") or 0),
            "mtime": lm.timestamp() if lm is not None else None,
            # R2/S3 already computed a content hash — reuse it verbatim.
            "etag": str(resp.get("ETag") or "").strip('"') or None,
        }

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=self._k(key))
        except Exception:  # noqa: BLE001 — best effort
            pass


_lock = threading.Lock()
_instance: _Backend | None = None


_R2_VARS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")


def _hosted_production() -> str:
    """Which signal says this process is a production deploy — "" when none.

    The same production test main.py / auth.py apply (`ENV` or `ENVIRONMENT`,
    `prod` or `production`), plus the hosts' own markers: Railway sets
    RAILWAY_ENVIRONMENT / RAILWAY_ENVIRONMENT_NAME to the environment's name,
    Render sets RENDER=true.
    2026-09-15 review: the rule read `ENV == "production"` exactly, which the
    Railway deploy does not necessarily set, so the next push could have sent
    every production PDF to the container's disk."""
    for var in ("ENV", "ENVIRONMENT"):
        if (os.environ.get(var) or "").strip().lower() in ("prod", "production"):
            return f"{var}=production"
    # Railway injects both (the older RAILWAY_ENVIRONMENT and the current
    # RAILWAY_ENVIRONMENT_NAME); checked live on the samatu-api service 2026-09-16.
    for var in ("RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME"):
        if (os.environ.get(var) or "").strip().lower() == "production":
            return f"{var}=production"
    if (os.environ.get("RENDER") or "").strip().lower() == "true":
        return "RENDER=true"
    return ""


def r2_decision() -> tuple[bool, str]:
    """(use_r2, why) — the whole backend-selection rule, pure over os.environ.

    2026-09-04. Credentials alone used to be the rule: any machine with the four
    R2_* vars wrote to the PRODUCTION bucket. `backend/.env` carries them, so a
    dev server and the whole test suite did exactly that — 35 test-seed objects
    landed in the live `projects/` prefix on 09-02 and 09-04, mixed in with real
    customers' drawings. Presence of a credential is not consent to use it.

    R2 is now used only when something SAYS this process is allowed to write to
    the real bucket:
      · ENV=production            — a deploy, and
      · STORAGE_BACKEND=r2        — an explicit opt-in (a staging box, or a
                                    developer deliberately testing R2)
    and `STORAGE_BACKEND=local` opts out even in production — the ERROR below
    still fires there, so opting prod out cannot be done quietly.
    """
    explicit = (os.environ.get("STORAGE_BACKEND") or "").strip().lower()
    if explicit == "local":
        return False, "STORAGE_BACKEND=local"
    missing = [v for v in _R2_VARS if not os.environ.get(v)]
    if missing:
        return False, f"R2 not configured, missing: {', '.join(missing)}"
    if explicit == "r2":
        return True, "STORAGE_BACKEND=r2"
    prod = _hosted_production()
    if prod:
        return True, prod
    return False, ("R2 credentials present but unused — neither ENV=production "
                   "(nor ENVIRONMENT / RAILWAY_ENVIRONMENT / RENDER) nor "
                   "STORAGE_BACKEND=r2, so this process must not write to "
                   "the production bucket")


def selected_backend_name() -> str:
    """'r2' | 'local' — what get_storage() would pick (cheap, no side effects).
    Surfaced by /api/admin/v2/system-health so a misconfigured prod is visible."""
    return "r2" if r2_decision()[0] else "local"


def get_storage() -> _Backend:
    """Process-wide storage backend. R2 when `r2_decision()` allows it, else
    local disk.

    2026-07-27 audit (finding 7): the fallback to local disk was SILENT — a prod
    deploy missing one R2_* var kept "working" while every uploaded PDF went to
    ephemeral container disk. It says which backend it picked, and shouts
    (ERROR) when production lands on local disk.

    2026-09-04: which backend and WHY, on one line, every time — because the
    dangerous case is not a missing credential, it is a present one being used
    by a machine that should not have been writing to the live bucket."""
    global _instance
    with _lock:
        if _instance is not None:
            return _instance
        use_r2, why = r2_decision()
        if use_r2:
            _instance = R2Storage(
                os.environ["R2_ACCOUNT_ID"], os.environ["R2_ACCESS_KEY_ID"],
                os.environ["R2_SECRET_ACCESS_KEY"], os.environ["R2_BUCKET"],
                **({"key_prefix": _prefix} if (_prefix := os.environ.get("R2_KEY_PREFIX", "").strip()) else {}))
            log.info("storage backend: R2 (bucket=%s) — %s",
                     os.environ["R2_BUCKET"], why)
        else:
            root = os.environ.get("LOCAL_STORAGE_DIR") or str(
                data_path("pdf_store", pathlib.Path(__file__).parent / "data" / "pdf_store")
            )
            _instance = LocalDiskStorage(root)
            msg = "storage backend: LOCAL DISK at %s — %s"
            if _hosted_production():
                # Unchanged and deliberate: prod on local disk is data loss
                # waiting to happen, whatever the reason.
                log.error(msg + " | PRODUCTION uploads are NOT durable", root, why)
            elif all(os.environ.get(v) for v in _R2_VARS):
                # Credentials present, deliberately not used — routine, so INFO.
                log.info(msg, root, why)
            else:
                # A partial/absent R2 config is a real misconfiguration on any
                # machine that meant to have one: keep it at WARNING.
                log.warning(msg, root, why)
        return _instance


def reset_storage_for_test() -> None:
    """Drop the cached backend so a test can re-select with a fresh env/dir."""
    global _instance
    with _lock:
        _instance = None


def pdf_key(project_id: str) -> str:
    return f"projects/{project_id}.pdf"


def invoice_key(invoice_id: str) -> str:
    """Object-storage key for an emitted PVM sąskaita-faktūra PDF (W3 Task 14).
    Same backend selection as pdf_key (R2 in prod, local disk in dev/tests)."""
    return f"invoices/{invoice_id}.pdf"
