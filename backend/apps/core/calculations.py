"""
GST document calculator shared by Purchases (Phase 3), Quotations (Phase 4) and Invoices (Phase 5).

Per line:
    gross          = quantity × rate
    discount       = gross × discount_percent / 100
    taxable        = gross − discount
    CGST/SGST/IGST = taxable × gst_rate / 100   (split by intra/inter-state)
    line_total     = taxable + taxes

Header:
    header_discount is spread over lines in proportion to their taxable value (so GST is
    charged on the discounted amount, as GST law requires), extra_charges (transport etc.)
    are added after tax, and the grand total is rounded to the nearest rupee.

Everything is Decimal and rounded to paise with ROUND_HALF_UP — never float.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from .utils import ZERO, amount_in_words, money, round_off, split_gst, to_decimal

QTY_PLACES = Decimal("0.001")


@dataclass
class LineResult:
    gross: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    line_total: Decimal


@dataclass
class DocumentTotals:
    subtotal: Decimal = ZERO
    discount_total: Decimal = ZERO
    taxable_amount: Decimal = ZERO
    cgst_amount: Decimal = ZERO
    sgst_amount: Decimal = ZERO
    igst_amount: Decimal = ZERO
    extra_charges: Decimal = ZERO
    round_off: Decimal = ZERO
    grand_total: Decimal = ZERO
    amount_in_words: str = ""
    lines: list = field(default_factory=list)
    gst_summary: list = field(default_factory=list)  # [{rate, taxable, cgst, sgst, igst}]

    def header_fields(self):
        return {
            "subtotal": self.subtotal,
            "discount_total": self.discount_total,
            "taxable_amount": self.taxable_amount,
            "cgst_amount": self.cgst_amount,
            "sgst_amount": self.sgst_amount,
            "igst_amount": self.igst_amount,
            "round_off": self.round_off,
            "grand_total": self.grand_total,
            "amount_in_words": self.amount_in_words,
        }


def calculate_document(
    lines, *, interstate: bool, header_discount=ZERO, extra_charges=ZERO
) -> DocumentTotals:
    """
    lines: iterable of dicts/objects with quantity, rate, discount_percent, gst_rate.
    Returns DocumentTotals with a LineResult per input line (same order).
    """
    get = (lambda item, k: item.get(k)) if lines and isinstance(next(iter(lines)), dict) else getattr
    header_discount = money(header_discount)
    extra_charges = money(extra_charges)

    # 1) line gross / line discount / provisional taxable
    prepared = []
    for item in lines:
        qty = to_decimal(get(item, "quantity")).quantize(QTY_PLACES)
        rate = money(get(item, "rate"))
        disc_pct = to_decimal(get(item, "discount_percent") or 0)
        gst = to_decimal(get(item, "gst_rate") or 0)
        gross = money(qty * rate)
        discount = money(gross * disc_pct / 100)
        prepared.append([gross, discount, gross - discount, gst])

    # 2) spread header discount proportionally (last line takes the paise remainder)
    taxable_before = sum((p[2] for p in prepared), ZERO)
    if header_discount > taxable_before:
        raise ValueError("Discount cannot be more than the taxable amount.")
    if header_discount and taxable_before:
        remaining = header_discount
        for i, p in enumerate(prepared):
            share = remaining if i == len(prepared) - 1 else money(header_discount * p[2] / taxable_before)
            share = min(share, p[2])
            p[1] += share
            p[2] -= share
            remaining -= share

    # 3) tax per line
    totals = DocumentTotals(extra_charges=extra_charges)
    summary = {}
    for gross, discount, taxable, gst in prepared:
        tax = split_gst(taxable, gst, interstate)
        line_total = taxable + tax["cgst"] + tax["sgst"] + tax["igst"]
        totals.lines.append(
            LineResult(gross, discount, taxable, tax["cgst"], tax["sgst"], tax["igst"], line_total)
        )
        totals.subtotal += gross
        totals.discount_total += discount
        totals.taxable_amount += taxable
        totals.cgst_amount += tax["cgst"]
        totals.sgst_amount += tax["sgst"]
        totals.igst_amount += tax["igst"]
        s = summary.setdefault(gst, {"rate": gst, "taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO})
        s["taxable"] += taxable
        s["cgst"] += tax["cgst"]
        s["sgst"] += tax["sgst"]
        s["igst"] += tax["igst"]

    raw_total = (
        totals.taxable_amount + totals.cgst_amount + totals.sgst_amount + totals.igst_amount + extra_charges
    )
    totals.grand_total, totals.round_off = round_off(raw_total)
    totals.amount_in_words = amount_in_words(totals.grand_total)
    totals.gst_summary = sorted(summary.values(), key=lambda s: s["rate"])
    return totals
