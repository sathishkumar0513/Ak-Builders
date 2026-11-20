from decimal import Decimal as D

import pytest

from apps.core.calculations import calculate_document


def test_intra_state_with_line_discount_and_round_off():
    t = calculate_document(
        [
            {"quantity": "10", "rate": "410.00", "discount_percent": "2", "gst_rate": "18"},  # cement 10 bags
            {"quantity": "125.5", "rate": "68.00", "discount_percent": "0", "gst_rate": "18"},  # TMT kg
        ],
        interstate=False,
    )
    # line1: gross 4100, disc 82, taxable 4018, cgst 361.62 sgst 361.62
    l1 = t.lines[0]
    assert (l1.gross, l1.discount_amount, l1.taxable_amount) == (D("4100.00"), D("82.00"), D("4018.00"))
    assert l1.cgst_amount == D("361.62") and l1.sgst_amount == D("361.62") and l1.igst_amount == 0
    # line2: 125.5 × 68 = 8534.00 → tax 1536.12 → 768.06 each
    assert t.lines[1].cgst_amount == D("768.06")
    assert t.taxable_amount == D("12552.00")
    assert t.cgst_amount == t.sgst_amount == D("1129.68")
    assert t.grand_total == D("14811.00") and t.round_off == D("-0.36")
    assert t.amount_in_words == "Rupees Fourteen Thousand Eight Hundred Eleven Only"


def test_inter_state_igst_and_extra_charges():
    t = calculate_document(
        [{"quantity": 1, "rate": "1000", "gst_rate": "18"}], interstate=True, extra_charges="250"
    )
    assert t.igst_amount == D("180.00") and t.cgst_amount == 0
    assert t.grand_total == D("1430.00")


def test_header_discount_spread_before_tax():
    t = calculate_document(
        [{"quantity": 1, "rate": "1000", "gst_rate": "18"}, {"quantity": 1, "rate": "500", "gst_rate": "5"}],
        interstate=False,
        header_discount="150",
    )
    # 150 spread 100 / 50 → taxable 900 & 450
    assert [line.taxable_amount for line in t.lines] == [D("900.00"), D("450.00")]
    assert t.discount_total == D("150.00")
    assert t.cgst_amount == D("81.00") + D("11.25")
    assert {s["rate"] for s in t.gst_summary} == {D("18"), D("5")}


def test_header_discount_cannot_exceed_taxable():
    with pytest.raises(ValueError):
        calculate_document(
            [{"quantity": 1, "rate": "100", "gst_rate": "18"}], interstate=False, header_discount="101"
        )
