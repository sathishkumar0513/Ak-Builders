import json

from .gst_cases import FILE, expected


def test_server_matches_shared_gst_cases():
    """The same 300 cases are checked by frontend/src/utils/gst.test.js (JavaScript preview)."""
    cases = json.loads(FILE.read_text())
    assert len(cases) == 300
    for i, case in enumerate(cases):
        assert expected(case) == case["expected"], f"case {i}"
