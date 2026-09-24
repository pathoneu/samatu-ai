"""pdfminer.six 20251230 formats a DEBUG message with the whole parser stack for every token it reads —
eagerly, in an f-string, whether or not debug logging is on. On a drawing whose object streams hold large
arrays (objektas_g, 16 pages) one `pdfplumber.open(...).pages[n]` costs 51 s of `repr()`; with the two
messages made lazy it costs 0,3 s (measured 2026-09-24, same file, same machine). Upstream fixed it in
20260107 (`log.debug("nextobject: %r", obj)`); requirements.txt was raised to pdfplumber 0.11.10 (which pins
20260107, and pypdfium2 ≥ 5.9) the same day on the founder's go — the eval under the new libraries was
identical to the one before, line for line.

So on the pinned environment this module does nothing. It stays as the guard for the one case that would
bring the slowness back (an environment that resolves to 20251230 again): it patches the ONE method at
runtime, only when the installed pdfminer still carries the eager f-strings (a source check, not a version
guess): the method's source is rewritten with lazy `%r` arguments and re-executed in pdfminer's own
namespace. Any other pdfminer is left alone. `install()` is idempotent and never raises. Every pdfplumber
user in the app is covered (page texts, the door schedule, the legend and symbol scans, the height markers).
"""
from __future__ import annotations

import inspect
import re
import textwrap

_EAGER_KEYWORD = re.compile(
    r'log\.debug\(\s*f"do_keyword: pos=\{pos!r\}, token=\{token!r\}, stack=\{self\.curstack!r\}"\s*\)')
_EAGER_OBJECT = re.compile(r'log\.debug\(f"nextobject: \{obj!r\}"\)')
_installed: bool | None = None


def install() -> bool:
    """Patch `PSStackParser.nextobject` if it still formats its debug messages eagerly. Returns True when the
    patch is active (now or from an earlier call), False when nothing needed or could be patched."""
    global _installed
    if _installed is not None:
        return _installed
    _installed = False
    try:
        from pdfminer import psparser
        fn = psparser.PSStackParser.nextobject
        src = textwrap.dedent(inspect.getsource(fn))
        if not (_EAGER_KEYWORD.search(src) and _EAGER_OBJECT.search(src)):
            return False
        lazy = _EAGER_KEYWORD.sub('log.debug("do_keyword: pos=%r, token=%r, stack=%r", pos, token, self.curstack)', src)
        lazy = _EAGER_OBJECT.sub('log.debug("nextobject: %r", obj)', lazy)
        namespace: dict = {}
        exec(compile(lazy, fn.__code__.co_filename, "exec"), psparser.__dict__, namespace)  # noqa: S102
        patched = namespace.get("nextobject")
        if patched is None:
            return False
        psparser.PSStackParser.nextobject = patched
        _installed = True
        return True
    except Exception:  # noqa: BLE001 — a parser we cannot patch stays as it is
        return False


def is_installed() -> bool:
    return bool(_installed)
