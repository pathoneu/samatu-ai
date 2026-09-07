"""The evidence viewer in the browser lays a sharp crop of the visible region
over the fitted sheet. To place it, `frontend/src/lib/sheetZoom.js` replicates
`_padded` from backend/api/evidence.py. These fixtures are the SAME four
rectangles asserted in `frontend/src/lib/sheetZoom.test.js`; if the padding
rule changes, change the replica too (or the overlay drifts off its spot)."""

import pytest

from api.evidence import _padded


@pytest.mark.parametrize("rect, want", [
    ([0.30, 0.30, 0.60, 0.60], (0.288, 0.288, 0.612, 0.612)),          # plain padding
    ([0.50, 0.50, 0.52, 0.51], (0.46, 0.4825, 0.56, 0.5275)),          # floors around a label
    ([0.00, 0.00, 0.05, 0.02], (0.0, 0.0, 0.1, 0.045)),                # slid back onto the sheet
    ([0.97, 0.99, 1.00, 1.00], (0.9, 0.955, 1.0, 1.0)),
    ([0, 0, 1, 1], (0.0, 0.0, 1.0, 1.0)),                              # whole sheet stays whole
])
def test_padding_rule_matches_the_browser_replica(rect, want):
    got = _padded(rect)
    assert got == pytest.approx(want, abs=1e-9), "update frontend/src/lib/sheetZoom.js paddedRect too"
