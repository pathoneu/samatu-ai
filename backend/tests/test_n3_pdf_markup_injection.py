"""N3 (LOW) — reportlab markup/link injection + 500 in offer-PDF export.

2026-07-04 pentest, pass 2, finding N3. /generate-pdf passed user/AI-controlled
strings (imone, aprasymas, section names, uzsakovas, …) into reportlab's
Paragraph(), whose XML-ish mini-markup meant:
  - `<a href="http://evil">x</a>` rendered as a LIVE PDF link (phishing — and
    these strings can be AI-extracted from an untrusted drawing), and
  - malformed markup (`<unclosed & tag`) threw inside doc.build() → HTTP 500.

The fix escapes every user/AI string with xml.sax.saxutils.escape before it
reaches a Paragraph.

These tests REPLAY the PoC: an injected <a href> label must NOT survive as live
markup in the PDF, and malformed markup must not 500. Runs under the dev auth
bypass (.env SAMATU_AUTH_DISABLED=1) so /generate-pdf's require_user resolves.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app  # noqa: E402

client = TestClient(app)


def _generate(data: dict):
    return client.post("/generate-pdf", json=data)


def test_n3_anchor_tag_is_escaped_no_live_link():
    """An <a href> injected via a label must be escaped, not emitted as a live
    /URI annotation in the PDF stream."""
    payload = {
        "projektas": "T",
        "imone": '<a href="http://evil.example">click me</a>',
        "eilutes": [{
            "nr": "1",
            "aprasymas": '<a href="http://phish.example">Apdaila</a>',
            "mato_vnt": "m2", "kiekis": 10, "kaina": 5, "suma": 50,
            "skyrius": '<a href="http://evil2.example">Skyrius</a>',
        }],
    }
    r = _generate(payload)
    assert r.status_code == 200, r.text
    body = r.content
    # The injected host must not appear as an emitted /URI action target.
    assert b"/URI" not in body or b"evil.example" not in body
    assert b"evil.example" not in body
    assert b"phish.example" not in body
    assert b"evil2.example" not in body


def test_n3_malformed_markup_does_not_500():
    """Malformed markup previously threw inside doc.build() → HTTP 500. It must
    now be escaped and render cleanly."""
    payload = {
        "projektas": "T",
        "imone": "<unclosed & tag <<<",
        "uzsakovas": "A & B < C > D",
        "eilutes": [{
            "nr": "1", "aprasymas": "Sienos < 3m & > 2m",
            "mato_vnt": "m2", "kiekis": 1, "kaina": 1, "suma": 1,
            "skyrius": "Apdaila & <partial",
        }],
    }
    r = _generate(payload)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_n3_ampersand_entity_in_company_name_ok():
    """A plain ampersand (common in real company names, e.g. 'Jonas & Co')
    must not 500 and must not corrupt the document."""
    r = _generate({
        "projektas": "T",
        "imone": "Jonas & Petras UAB",
        "eilutes": [{"nr": "1", "aprasymas": "x", "mato_vnt": "vnt.",
                     "kiekis": 1, "kaina": 1, "suma": 1}],
    })
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
