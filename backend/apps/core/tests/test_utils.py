from datetime import date
from decimal import Decimal as D

import pytest

from apps.core.numbering import next_document_number
from apps.core.utils import (
    amount_in_words,
    financial_year,
    format_inr,
    is_interstate,
    money,
    round_off,
    split_gst,
)


def test_money_rounds_half_up():
    assert money("10.005") == D("10.01")
    assert money(0.1 + 0.2) == D("0.30")


def test_round_off():
    assert round_off("1234.49") == (D("1234.00"), D("-0.49"))
    assert round_off("1234.50") == (D("1235.00"), D("0.50"))


def test_format_inr_indian_grouping():
    assert format_inr("1234567.5") == "₹12,34,567.50"
    assert format_inr("999") == "₹999.00"
    assert format_inr("100000") == "₹1,00,000.00"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0", "Rupees Zero Only"),
        ("15", "Rupees Fifteen Only"),
        ("125050.75", "Rupees One Lakh Twenty Five Thousand Fifty and Seventy Five Paise Only"),
        ("10000000", "Rupees One Crore Only"),
        ("2345678", "Rupees Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Only"),
    ],
)
def test_amount_in_words(value, expected):
    assert amount_in_words(value) == expected


def test_financial_year():
    assert financial_year(date(2026, 11, 11)) == "2026-27"
    assert financial_year(date(2027, 3, 31)) == "2026-27"
    assert financial_year(date(2027, 4, 1)) == "2027-28"


def test_gst_split_intra_and_inter_state():
    assert not is_interstate("33", "33")
    assert is_interstate("33", "32")
    intra = split_gst("1000", "18", interstate=False)
    assert intra == {"cgst": D("90.00"), "sgst": D("90.00"), "igst": D("0.00")}
    inter = split_gst("1000", "18", interstate=True)
    assert inter["igst"] == D("180.00") and inter["cgst"] == D("0.00")
    # odd paise: total tax 0.09 → CGST 0.05 + SGST 0.04, never loses a paisa
    odd = split_gst("0.50", "18", interstate=False)
    assert odd["cgst"] + odd["sgst"] == D("0.09")


@pytest.mark.django_db
def test_document_number_series():
    first = next_document_number("INVOICE", on=date(2026, 11, 11))
    second = next_document_number("INVOICE", on=date(2026, 11, 12))
    assert first == "AK/2026-27/0001"
    assert second == "AK/2026-27/0002"
    # new financial year restarts at 0001
    assert next_document_number("INVOICE", on=date(2027, 4, 1)) == "AK/2027-28/0001"
