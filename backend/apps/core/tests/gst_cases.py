"""
Shared GST test cases for the server (Python) and the live preview (JavaScript).

    python -m apps.core.tests.gst_cases      # regenerate gst_cases.json after a deliberate rule change

The same JSON is checked by apps/core/tests/test_gst_parity.py and
frontend/src/utils/gst.test.js, so the preview can never drift from the saved totals.
"""

import json
import random
from decimal import Decimal
from pathlib import Path

FILE = Path(__file__).with_name("gst_cases.json")


def _case(rng):
    lines = []
    for _ in range(rng.randint(1, 6)):
        lines.append(
            {
                "quantity": str(rng.choice([1, 2, 3, 7, 10, 12.5, 0.75, 33.333, 150, 1.005])),
                "rate": str(rng.choice([1, 9.99, 45.5, 123.45, 350, 399.99, 1234.56, 4999.95, 61.11])),
                "discount_percent": str(rng.choice([0, 0, 0, 2.5, 5, 7.5, 10, 12.75, 33.33])),
                "gst_rate": str(rng.choice([0, 5, 12, 18, 18, 28])),
            }
        )
    gross = sum(Decimal(item["quantity"]) * Decimal(item["rate"]) for item in lines)
    header = min(
        rng.choice([0, 0, 1, 10, 99.99, round(float(gross) * 0.05, 2)]), round(float(gross) * 0.4, 2)
    )
    return {
        "lines": lines,
        "interstate": rng.random() < 0.3,
        "header_discount": str(header),
        "extra_charges": str(rng.choice([0, 0, 150, 499.5, 1200])),
    }


def expected(case):
    from apps.core.calculations import calculate_document

    t = calculate_document(
        case["lines"],
        interstate=case["interstate"],
        header_discount=case["header_discount"],
        extra_charges=case["extra_charges"],
    )
    return {
        "subtotal": str(t.subtotal),
        "discount": str(t.discount_total),
        "taxable": str(t.taxable_amount),
        "cgst": str(t.cgst_amount),
        "sgst": str(t.sgst_amount),
        "igst": str(t.igst_amount),
        "roundOff": str(t.round_off),
        "grandTotal": str(t.grand_total),
        "lines": [{"taxable": str(x.taxable_amount), "total": str(x.line_total)} for x in t.lines],
    }


def build(n=300, seed=2026):
    rng = random.Random(seed)
    cases = [_case(rng) for _ in range(n)]
    return [{**c, "expected": expected(c)} for c in cases]


if __name__ == "__main__":
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()
    FILE.write_text(json.dumps(build(), indent=1))
    print(f"wrote {FILE}")
