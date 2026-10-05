"""The dependency locks and the builds that install them (2026-10-05).

Audit backend-architecture-debt-2 / data-ops-infra-7 / backend-security-20:
production (nixpacks, CPython 3.12) and the Dockerfile installed the UNPINNED
requirements.txt, while CI and the dev venv used the pinned lock — so what
shipped was resolved fresh on deploy day and had never run the suite.

The contract pinned here:
  * requirements.txt / requirements-dev.txt are the human-edited sources;
    requirements.lock (production) and requirements-dev.lock (CI, dev venv:
    `-r requirements.lock` + the test-only closure) hold exact pins only;
  * the production lock is closed — everything requirements.txt needs, on this
    interpreter, is pinned in it — and carries no test-only package;
  * the Dockerfile and nixpacks.toml install requirements.lock with --no-deps
    and run `pip check`; CI installs requirements-dev.lock the same way;
  * no production module imports a test-only package.
"""
from __future__ import annotations

import ast
import importlib.metadata as md
import re
import tomllib
from pathlib import Path

import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
RUNTIME_TXT = BACKEND / "requirements.txt"
DEV_TXT = BACKEND / "requirements-dev.txt"
RUNTIME_LOCK = BACKEND / "requirements.lock"
DEV_LOCK = BACKEND / "requirements-dev.lock"
TEST_ONLY_TOP = {"pytest", "pytest-asyncio", "pikepdf"}
_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.+!_-]+)")


def _lines(path: Path) -> list[str]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split(" #")[0].strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _own_pins(path: Path) -> dict[str, str]:
    """name → version of the pins written in this file (not its -r include)."""
    pins = {}
    for line in _lines(path):
        if line.startswith("-r "):
            continue
        m = _PIN.fullmatch(line)
        assert m, f"{path.name}: not an exact pin: {line!r}"
        name = canonicalize_name(m.group(1))
        assert name not in pins, f"{path.name}: {name} pinned twice"
        pins[name] = m.group(2)
    return pins


def _own_requirements(path: Path) -> list[Requirement]:
    return [Requirement(line) for line in _lines(path) if not line.startswith("-r ")]


def _closure(tops: list[Requirement]) -> set[str]:
    """Every distribution `tops` need on THIS interpreter, from the installed
    metadata, with markers and requested extras evaluated."""
    seen: dict[str, set[str]] = {}
    todo = [(canonicalize_name(r.name), set(r.extras)) for r in tops
            if r.marker is None or r.marker.evaluate({"extra": ""})]
    while todo:
        name, extras = todo.pop()
        known = seen.get(name)
        if known is not None and extras <= known:
            continue
        seen[name] = (known or set()) | extras
        for spec in md.distribution(name).requires or []:
            req = Requirement(spec)
            if req.marker is not None and not any(
                    req.marker.evaluate({"extra": e}) for e in (seen[name] or {""})):
                continue
            todo.append((canonicalize_name(req.name), set(req.extras)))
    return set(seen)


def test_the_locks_hold_exact_pins_and_the_dev_lock_builds_on_production():
    runtime, dev = _own_pins(RUNTIME_LOCK), _own_pins(DEV_LOCK)
    assert not [line for line in _lines(RUNTIME_LOCK) if line.startswith("-r ")]
    assert _lines(DEV_LOCK)[0] == "-r requirements.lock"
    assert not (set(runtime) & set(dev)), set(runtime) & set(dev)
    assert _lines(DEV_TXT)[0] == "-r requirements.txt"


def test_every_declared_dependency_is_pinned_where_it_belongs():
    runtime, dev = _own_pins(RUNTIME_LOCK), _own_pins(DEV_LOCK)
    for req in _own_requirements(RUNTIME_TXT):
        name = canonicalize_name(req.name)
        assert name in runtime, f"{name} (requirements.txt) is not in requirements.lock"
        assert req.specifier.contains(runtime[name], prereleases=True), (name, runtime[name])
    for req in _own_requirements(DEV_TXT):
        name = canonicalize_name(req.name)
        assert name in dev, f"{name} (requirements-dev.txt) is not in requirements-dev.lock"
        assert req.specifier.contains(dev[name], prereleases=True), (name, dev[name])


def test_test_only_packages_stay_out_of_production():
    runtime_txt = {canonicalize_name(r.name) for r in _own_requirements(RUNTIME_TXT)}
    assert not (TEST_ONLY_TOP & runtime_txt)
    assert not (TEST_ONLY_TOP & set(_own_pins(RUNTIME_LOCK)))
    assert TEST_ONLY_TOP <= set(_own_pins(DEV_LOCK))


def test_the_production_lock_is_closed_and_the_dev_lock_holds_only_test_needs():
    runtime_lock, dev_lock = set(_own_pins(RUNTIME_LOCK)), set(_own_pins(DEV_LOCK))
    needed = _closure(_own_requirements(RUNTIME_TXT))
    assert needed <= runtime_lock, f"production needs, but the lock lacks: {needed - runtime_lock}"
    assert runtime_lock <= needed, f"pinned for production, needed by nothing: {runtime_lock - needed}"
    test_needs = _closure(_own_requirements(DEV_TXT)) - needed
    assert test_needs == dev_lock, (test_needs ^ dev_lock)


def test_the_installed_versions_are_the_locked_ones():
    """Whatever ran this suite ran it on the locked versions (CI installs the
    dev lock fresh; a stale dev venv is caught here, not in production)."""
    pins = {**_own_pins(RUNTIME_LOCK), **_own_pins(DEV_LOCK)}
    drift = {name: (want, md.version(name)) for name, want in pins.items()
             if md.version(name) != want}
    assert not drift, f"installed ≠ locked: {drift} — pip install --no-deps -r backend/requirements-dev.lock"


def _pip_install_lines(text: str) -> list[str]:
    joined = text.replace("\\\n", " ")
    return [line for line in joined.splitlines() if "pip install" in line and "--upgrade pip" not in line]


def test_the_production_builds_install_the_lock_strictly():
    docker = "\n".join(line for line in (BACKEND / "Dockerfile").read_text(
        encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
    assert "COPY backend/requirements.lock backend/requirements.lock" in docker
    nix = tomllib.loads((REPO / "nixpacks.toml").read_text(encoding="utf-8"))
    nix_cmds = "\n".join(nix["phases"]["install"]["cmds"])
    for where, text in (("Dockerfile", docker), ("nixpacks.toml", nix_cmds)):
        installs = _pip_install_lines(text)
        assert len(installs) == 1, (where, installs)
        line = installs[0]
        assert "-r backend/requirements.lock" in line and "--no-deps" in line, (where, line)
        assert "pip check" in line, (where, line)
        assert "requirements.txt" not in text and "requirements-dev" not in text, where


def test_ci_installs_the_dev_lock_strictly():
    ci = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    runs = "\n".join(step.get("run", "") for step in ci["jobs"]["backend"]["steps"])
    assert "pip install --no-deps -r backend/requirements-dev.lock" in runs
    assert "pip check" in runs
    assert "requirements.txt" not in runs


def test_no_production_module_imports_a_test_only_package():
    banned = {"pytest", "_pytest", "pytest_asyncio", "pikepdf", "packaging",
              "deprecated", "wrapt", "pluggy", "iniconfig"}
    found = []
    for path in sorted(BACKEND.rglob("*.py")):
        rel = path.relative_to(BACKEND)
        if rel.parts[0] in ("tests", "scripts") or rel.name == "conftest.py" \
                or rel.name.startswith("test_") or "__pycache__" in rel.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            found += [f"{rel}: {n}" for n in names if n.split(".")[0] in banned]
    assert not found, found
