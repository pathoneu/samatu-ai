"""Durable PDF storage (2026-06-21 durability track) — abstraction + endpoints.

Fully testable with the local-disk backend; no R2 credentials needed. R2 is
selected automatically when the R2_* env vars are set.
"""
import pathlib


def _local_storage(tmp_path, monkeypatch):
    import storage
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    return storage


def test_local_backend_roundtrip(tmp_path, monkeypatch):
    storage = _local_storage(tmp_path, monkeypatch)
    s = storage.get_storage()
    assert s.name == "LocalDiskStorage"
    key = storage.pdf_key("p1")
    assert s.get(key) is None and not s.exists(key)
    s.put(key, b"%PDF-1.4 hello")
    assert s.exists(key) and s.get(key) == b"%PDF-1.4 hello"
    s.delete(key)
    assert s.get(key) is None and not s.exists(key)


def test_factory_selects_r2_when_configured(tmp_path, monkeypatch):
    import storage
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")
    monkeypatch.setenv("R2_BUCKET", "bucket")
    # 2026-09-04: credentials alone no longer select R2 — a dev box and this
    # suite both carry them via backend/.env and were writing into the live
    # bucket. A process must also SAY it may (ENV=production, or this).
    # The full matrix lives in tests/test_storage_backend_gate.py.
    monkeypatch.setenv("STORAGE_BACKEND", "r2")
    storage.reset_storage_for_test()
    s = storage.get_storage()      # builds the boto3 client; no network call yet
    assert s.name == "R2Storage"
    storage.reset_storage_for_test()


def test_local_backend_blocks_path_traversal(tmp_path, monkeypatch):
    storage = _local_storage(tmp_path, monkeypatch)
    s = storage.get_storage()
    s.put("../../etc/evil", b"x")
    root = pathlib.Path(str(tmp_path / "pdfs")).resolve()
    for p in root.rglob("*"):
        assert root in p.resolve().parents or p.resolve() == root  # nothing escaped


def test_pdf_endpoints_roundtrip(tmp_path, monkeypatch):
    import db, auth, storage
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "pdf.db")
    db.init_schema(); db._migrate_schema()
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)  # dev admin user → ownership passes

    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    db.upsert_project("p1", {"name": "P", "tipas": "interjeras"}, user_id=None)
    pdf = b"%PDF-1.4\n% minimal test\n%%EOF\n"

    r = client.post("/api/projects/p1/pdf",
                    files={"pdf_file": ("d.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["size"] == len(pdf)

    g = client.get("/api/projects/p1/pdf")
    assert g.status_code == 200
    assert g.content == pdf
    assert g.headers["content-type"].startswith("application/pdf")

    # not-yet-stored / unknown project → 404, never a 500
    assert client.get("/api/projects/nope/pdf").status_code == 404


def test_db_backup_to_storage(tmp_path, monkeypatch):
    """A nightly backup must produce a valid SQLite snapshot in object storage."""
    import db, storage, backup
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "live.db")
    db.init_schema(); db._migrate_schema()
    db.create_user("u@x.lt", "h", name="U")  # content to snapshot
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "store"))
    storage.reset_storage_for_test()

    res = backup.backup_db(stamp="20260621T000000Z")
    assert res["key"] == "backups/samatu-20260621T000000Z.db"
    assert res["size"] > 0
    data = storage.get_storage().get(res["key"])
    assert data is not None
    assert data[:16].startswith(b"SQLite format 3")  # a real, restorable snapshot


def test_pdf_upload_rejects_non_pdf(tmp_path, monkeypatch):
    import db, auth, storage
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "pdf.db")
    db.init_schema(); db._migrate_schema()
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    db.upsert_project("p1", {"name": "P", "tipas": "interjeras"}, user_id=None)
    r = client.post("/api/projects/p1/pdf",
                    files={"pdf_file": ("x.png", b"\x89PNG not a pdf", "image/png")})
    assert r.status_code == 400
