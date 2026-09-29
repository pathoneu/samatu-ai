"""Ownership policy over EVERY project route (audit 2026-09-29, testing-eval-5).

Each project-scoped handler repeats its own owner filter, and deleting four of
them left the whole suite green. This module does not list routes by hand: it
walks the live route table (``main.app.routes`` plus every included router), so
a ``{project_id}`` route added next month is checked with no edit here.

For every such route and every HTTP method it accepts:
  * signed out            -> 401;
  * signed in as user B   -> 404 on user A's project (never 2xx, never 5xx),
    no trace of A's data in the body, and the answer is the SAME as B gets for
    a project id that does not exist (so the API never tells B that A's
    project exists, and a route that skipped the gate and failed later, for
    another reason, is caught);
  * user A's project row, corrections and extractions are unchanged.

Real accounts through /api/auth/register + /api/auth/login with auth switched
ON for this module. No Anthropic call can happen: the model client is replaced
by one that fails loudly.
"""
from __future__ import annotations

import re
import uuid

import anthropic
import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

import main  # noqa: E402  (must precede `import auth` so load_dotenv runs first)
from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"
_CANARY = "SAVININKO-A-KANARELE"

# Routes with {project_id} that are public on purpose, as (METHOD, path).
# Empty today: the only public read (/api/share/{token}) is keyed by a share
# token, not a project id. Anything added here needs a comment saying why.
_PUBLIC_BY_DESIGN: set[tuple[str, str]] = set()

# Routes where an existing test pins 401/403 for another user instead of 404,
# as {(METHOD, path): {codes}}. Everything else must answer 404.
_PINNED_FOREIGN_CODES: dict[tuple[str, str], set[int]] = {
    # PUT is an upsert on a client-made id: a free id creates the caller's own
    # project, someone else's id is refused. Pinned by
    # test_sweep_2026_07_28_save_path.py::test_f8_ownership_still_wins_over_conflict.
    ("PUT", "/api/projects/{project_id}"): {403},
}

# Dummy values for path parameters other than project_id.
_DUMMY_PATH_VALUES = {"room_nr": "1"}

_TINY_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


# ── route discovery ─────────────────────────────────────────────────────────

def _walk(routes, prefix=""):
    """Yield (path, methods) for every HTTP route, descending into included
    routers (FastAPI >= 0.13x keeps them as `_IncludedRouter` nodes) and mounts."""
    for r in routes:
        if hasattr(r, "effective_candidates"):
            yield from _walk(r.effective_candidates(), prefix)
            yield from _walk(r.effective_low_priority_routes(), prefix)
        elif isinstance(r, Mount):
            yield from _walk(r.routes, prefix + r.path)
        elif getattr(r, "path", None) is not None and getattr(r, "methods", None):
            yield prefix + r.path, set(r.methods)


def _project_routes():
    out = set()
    for path, methods in _walk(app.routes):
        if "{project_id}" not in path:
            continue
        for m in methods - {"HEAD", "OPTIONS"}:
            if (m, path) not in _PUBLIC_BY_DESIGN:
                out.add((m, path))
    return sorted(out, key=lambda mp: (mp[1], mp[0]))


_ROUTES = _project_routes()


def test_discovery_sees_main_and_router_routes():
    """Guard the walker itself: if FastAPI changes how included routers are
    stored and discovery silently finds nothing, this fails instead of the
    policy test passing on an empty list."""
    paths = {p for _, p in _ROUTES}
    assert "/api/projects/{project_id}" in paths                 # main.py
    assert "/api/projects/{project_id}/annotations" in paths     # api/ router
    assert "/api/projects/{project_id}/rooms/{room_nr}/facts" in paths
    assert len(_ROUTES) >= 30, _ROUTES


# ── minimal request built from the route's own OpenAPI schema ───────────────

_FILE = object()  # marker: this field is an uploaded file


def _sample(schema, defs, key, pid):
    if "$ref" in schema:
        return _sample(defs[schema["$ref"].rsplit("/", 1)[-1]], defs, key, pid)
    for combo in ("anyOf", "oneOf"):
        if combo in schema:
            opts = [o for o in schema[combo] if o.get("type") != "null"] or schema[combo]
            return _sample(opts[0], defs, key, pid)
    if "allOf" in schema:
        return _sample(schema["allOf"][0], defs, key, pid)
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" and "properties" not in schema:
        return {"name": "patikra"}  # open dict: non-empty, so "empty body" is not the answer
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        return {k: _sample(props[k], defs, k, pid)
                for k in schema.get("required", []) if k in props}
    if t == "array":
        n = max(schema.get("minItems", 0), 1 if key else 0)
        return [_sample(schema.get("items", {}), defs, key, pid) for _ in range(n)]
    if t == "integer":
        v = max(int(schema.get("minimum", 1)), 1)
        return min(v, int(schema.get("maximum", v)))
    if t == "number":
        lo = schema.get("minimum", 0.0)
        return (lo + schema.get("maximum", lo + 1.0)) / 2
    if t == "boolean":
        return False
    if t == "string":
        if schema.get("format") == "binary" or "contentMediaType" in schema:
            return _FILE
        return pid if key == "project_id" else "1"
    return None


def _request_kwargs(method, path, pid):
    """A harmless minimal request that passes the route's own validation, so
    the gate — not a 422 — is what answers."""
    spec = app.openapi()
    op = spec["paths"].get(path, {}).get(method.lower())
    if op is None:  # include_in_schema=False: no schema to go on
        return {}
    defs = spec.get("components", {}).get("schemas", {})
    kw = {}
    params = {p["name"]: _sample(p.get("schema", {}), defs, p["name"], pid)
              for p in op.get("parameters", [])
              if p.get("in") == "query" and p.get("required")}
    if params:
        kw["params"] = params
    body = op.get("requestBody")
    if body:
        ctype, media = next(iter(body["content"].items()))
        value = _sample(media.get("schema", {}), defs, "", pid)
        if ctype == "application/json":
            kw["json"] = value if value is not None else {}
        else:  # multipart / urlencoded form
            data, files = {}, []
            for k, v in (value or {}).items():
                for item in (v if isinstance(v, list) else [v]):
                    if item is _FILE:
                        files.append((k, ("plan.pdf", _TINY_PDF, "application/pdf")))
                    else:
                        data[k] = str(item)
            kw["data"] = data
            if files:
                kw["files"] = files
    return kw


def _url(path, pid):
    url = path.replace("{project_id}", pid)
    return re.sub(r"\{(\w+)(?::\w+)?\}",
                  lambda m: _DUMMY_PATH_VALUES.get(m.group(1), "1"), url)


def _call(client, method, path, pid):
    return client.request(method, _url(path, pid), **_request_kwargs(method, path, pid))


# ── accounts + seeded project ───────────────────────────────────────────────

class _NoModelCalls:
    def __init__(self, *a, **kw):
        pass

    def __getattr__(self, name):
        raise AssertionError("ownership policy test reached the Anthropic client")


@pytest.fixture(scope="module")
def clients(tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(db, "_DB_PATH", tmp_path_factory.mktemp("ownpol") / "own.db")
        mp.setattr(auth, "AUTH_DISABLED", False)
        mp.setenv("SAMATU_ADMIN_EMAIL", "nobody@invalid.lt")  # neither user is admin
        mp.setattr(main, "client", _NoModelCalls())
        mp.setattr(anthropic, "Anthropic", _NoModelCalls)  # lazily built clients too
        db.init_schema()
        db._migrate_schema()
        main._RATE_BUCKET.clear()
        out = {}
        for who in ("a", "b"):
            c = TestClient(app)
            email = f"{who}-owner-policy@x.lt"
            r = c.post("/api/auth/register", json={"email": email, "password": _PW})
            assert r.status_code == 200, r.text
            assert r.json()["is_first_admin"] is False
            r = c.post("/api/auth/login", json={"email": email, "password": _PW})
            assert r.status_code == 200, r.text
            out[who] = (c, db.get_user_by_email(email))
        yield out


def _snapshot(pid):
    with db._conn() as c:
        row = c.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        corr = c.execute("SELECT COUNT(*) FROM corrections WHERE project_id = ?",
                         (pid,)).fetchone()[0]
        extr = c.execute("SELECT COUNT(*) FROM extractions WHERE project_id = ?",
                         (pid,)).fetchone()[0]
    return (dict(row) if row else None), corr, extr


def _normalized(resp, pid):
    return resp.status_code, resp.text.replace(pid, "<ID>")


@pytest.fixture()
def seeded(clients):
    main._RATE_BUCKET.clear()
    _, user_a = clients["a"]
    tag = uuid.uuid4().hex[:12]
    pid, ghost = f"own-a-{tag}", f"own-z-{tag}"   # same length: bodies compare 1:1
    db.upsert_project(pid, {
        "name": _CANARY, "tipas": "interjeras",
        "patalpos": [{"nr": "1", "pavadinimas": "Kambarys", "plotas_m2": 12.0,
                      "perimetras_m": 14.0, "lubu_aukstis_m": 2.7}],
        "darbu_sarasas": [{"aprasymas": _CANARY, "kiekis": 1, "kaina": 5}],
    }, user_id=user_a["id"])
    db.log_correction(pid, "patalpos[0].plotas_m2", 11.0, 12.0, room_nr="1")
    return pid, ghost


# ── the policy ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", _ROUTES, ids=[f"{m} {p}" for m, p in _ROUTES])
def test_foreign_and_anonymous_callers_are_turned_away(clients, seeded, method, path):
    pid, ghost = seeded
    client_b, _ = clients["b"]
    before = _snapshot(pid)
    route = f"{method} {path}"

    anon = _call(TestClient(app), method, path, pid)
    assert anon.status_code == 401, f"{route}: signed out got {anon.status_code} {anon.text[:200]}"

    foreign = _call(client_b, method, path, pid)
    allowed = _PINNED_FOREIGN_CODES.get((method, path), {404})
    assert foreign.status_code in allowed, (
        f"{route}: another user got {foreign.status_code} on someone else's project "
        f"(expected {sorted(allowed)}): {foreign.text[:300]}")
    assert _CANARY not in foreign.text, f"{route}: another user's data in the body"

    # Same answer as for a project that does not exist. Pinned routes answer
    # differently on purpose; elsewhere compare whenever the free id 404s.
    missing = _call(client_b, method, path, ghost)
    if missing.status_code == 404 and (method, path) not in _PINNED_FOREIGN_CODES:
        assert _normalized(foreign, pid) == _normalized(missing, ghost), (
            f"{route}: answer on someone else's project differs from a missing one "
            f"— the route went past the owner check: {foreign.text[:200]!r} vs "
            f"{missing.text[:200]!r}")

    assert _snapshot(pid) == before, f"{route}: user A's project changed"
