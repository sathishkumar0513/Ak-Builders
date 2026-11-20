from decimal import Decimal

ZERO = Decimal("0.00")


def gst_summary_from_items(items):
    """Group saved line items by GST rate → [{rate, taxable, cgst, sgst, igst}] for the PDF tax table."""
    summary = {}
    for it in items:
        s = summary.setdefault(
            it.gst_rate, {"rate": it.gst_rate, "taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO}
        )
        s["taxable"] += it.taxable_amount
        s["cgst"] += it.cgst_amount
        s["sgst"] += it.sgst_amount
        s["igst"] += it.igst_amount
    return sorted(summary.values(), key=lambda s: s["rate"])
