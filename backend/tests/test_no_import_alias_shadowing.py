"""No function may assign a name that is also a module-level import alias.

2026-09-16, the first production run after the push: `extract_interior` did
`_re = _reclaim(...)` deep inside a 1000-line function whose nested helper
`_nkey` used the module's `import re as _re`. Python scopes names per function
at compile time, so that ONE assignment turned every `_re.sub` in the function
into an unbound free variable — the eksplikacija merge failed on every fresh
extraction for ten days, silently (caught and printed). No unit test runs that
path; this guard catches the whole class instead.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "extractor").glob("*.py")) + [ROOT / "main.py"] + sorted((ROOT / "api").glob("*.py"))


def _bound_names(target) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_bound_names(e) for e in target.elts))
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return set()


def _shadowings(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            aliases |= {a.asname for a in node.names if a.asname}
        elif isinstance(node, ast.ImportFrom):
            aliases |= {a.asname for a in node.names if a.asname}
    if not aliases:
        return []
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            bound: set[str] = set()
            if isinstance(node, ast.Assign):
                bound = set().union(*(_bound_names(t) for t in node.targets))
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                bound = _bound_names(node.target)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                bound = _bound_names(node.target)
            elif isinstance(node, ast.NamedExpr):
                bound = _bound_names(node.target)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                bound = set().union(*(_bound_names(i.optional_vars) for i in node.items if i.optional_vars))
            hit = bound & aliases
            if hit:
                out.append(f"{path.relative_to(ROOT)}:{node.lineno} in {fn.name}(): assigns {sorted(hit)}")
    return out


def test_no_function_assigns_a_module_import_alias():
    found = [s for f in FILES for s in _shadowings(f)]
    assert not found, "an import alias is reassigned inside a function (unbound free variable for any nested helper):\n" + "\n".join(found)
