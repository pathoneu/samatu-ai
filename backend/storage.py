"""Durable object storage for user-uploaded PDFs (2026-06-21 durability track).

The source drawing used to live ONLY in the uploader's browser (IndexedDB,
frontend/src/lib/pdfStore.js), so a cache-clear / device-switch / share link lost
it — the #1 "browser tool vs cloud product" gap from the commercial audit. This
persists the bytes server-side; the browser cache becomes an optimization, not the
only copy.

Two interchangeable backends, chosen by environment:
  - R2Storage      — Cloudflare R2 (S3-compatible, via boto3) when all R2_* env
                     vars are set. Zero egress, scales with success.
  - LocalDiskStorage — a directory under backend/data/pdf_store. Used in dev + the
                     test suite; needs no credentials, so everything below is fully
                     testable without R2.

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

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


class R2Storage(_Backend):
    def __init__(self, account_id: str, access_key: str, secret_key: str, bucket: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
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

    def put(self, key: str, data: bytes, content_type: str = "application/pdf") -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def _is_missing(self, exc: Exception) -> bool:
        from botocore.exceptions import ClientError
        if isinstance(exc, ClientError):
            code = str(exc.response.get("Error", {}).get("Code", ""))
            return code in ("NoSuchKey", "404", "NotFound")
        return False

    def get(self, key: str) -> bytes | None:
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:  # noqa: BLE001
            if self._is_missing(exc):
                return None
            raise StorageError(f"R2 get failed for {key}") from exc

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception:  # noqa: BLE001 — best effort
            pass


_lock = threading.Lock()
_instance: _Backend | None = None


_R2_VARS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")


def selected_backend_name() -> str:
    """'r2' | 'local' — what get_storage() would pick (cheap, no side effects).
    Surfaced by /api/admin/v2/system-health so a misconfigured prod is visible."""
    return "r2" if all(os.environ.get(v) for v in _R2_VARS) else "local"


def get_storage() -> _Backend:
    """Process-wide storage backend. R2 when configured, else local disk.

    2026-07-27 audit (finding 7): the fallback to local disk was SILENT — a prod
    deploy missing one R2_* var kept "working" while every uploaded PDF went to
    ephemeral container disk. It now says which backend it picked, and shouts
    (ERROR) when production lands on local disk."""
    global _instance
    with _lock:
        if _instance is not None:
            return _instance
        acct = os.environ.get("R2_ACCOUNT_ID")
        ak = os.environ.get("R2_ACCESS_KEY_ID")
        sk = os.environ.get("R2_SECRET_ACCESS_KEY")
        bucket = os.environ.get("R2_BUCKET")
        if acct and ak and sk and bucket:
            _instance = R2Storage(acct, ak, sk, bucket)
            log.info("storage backend: R2 (bucket=%s)", bucket)
        else:
            root = os.environ.get("LOCAL_STORAGE_DIR") or str(
                data_path("pdf_store", pathlib.Path(__file__).parent / "data" / "pdf_store")
            )
            _instance = LocalDiskStorage(root)
            missing = [v for v in _R2_VARS if not os.environ.get(v)]
            msg = "storage backend: LOCAL DISK at %s — R2 disabled, missing: %s"
            if os.environ.get("ENV") == "production":
                log.error(msg + " | PRODUCTION uploads are NOT durable", root, missing)
            else:
                log.warning(msg, root, missing)
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
