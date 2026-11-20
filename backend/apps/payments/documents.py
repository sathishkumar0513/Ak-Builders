from apps.core.models import CompanySettings
from apps.core.pdf import render_receipt
from apps.core.utils import amount_in_words, format_inr


def _party(c):
    return [
        c.name,
        ", ".join(filter(None, [c.address, c.city, c.pincode])),
        f"Phone: {c.phone}",
        c.gstin and f"GSTIN: {c.gstin}",
    ]


def _mode_rows(p):
    rows = [("Payment mode", p.get_mode_display())]
    if p.mode == "CHEQUE":
        rows += [
            ("Cheque no.", p.cheque_number),
            ("Cheque date", p.cheque_date and f"{p.cheque_date:%d/%m/%Y}"),
            ("Bank", p.bank_name),
        ]
    rows.append(("Reference / UTR", p.reference_number))
    return rows


def filename(prefix, number):
    return f"{prefix}-{number.replace('/', '-')}.pdf"


def payment_receipt_pdf(p) -> bytes:
    company = CompanySettings.load()
    rows = _mode_rows(p)
    if p.invoice_id:
        from apps.invoices.models import Invoice

        inv = Invoice.objects.get(pk=p.invoice_id)  # always the current balance
        rows += [
            (
                "Against invoice",
                f"{inv.number} dated {inv.invoice_date:%d/%m/%Y} ({format_inr(inv.grand_total)})",
            ),
            ("Invoice balance now", format_inr(inv.balance_due)),
        ]
    if p.project_id:
        rows.append(("Project", f"{p.project.name} ({p.project.code})"))
    if p.payment_stage_id:
        rows.append(("Payment stage", p.payment_stage.name))
    if p.cheque_status == "PENDING":
        rows.append(("Note", "Receipt is subject to realisation of the cheque."))
    stamp = "CANCELLED" if p.is_deleted else ("BOUNCED" if p.cheque_status == "BOUNCED" else None)
    return render_receipt(
        company=company,
        title="Payment Receipt",
        number=p.receipt_number,
        on=p.date,
        party_title="Received from",
        party_lines=_party(p.customer),
        rows=rows,
        amount=p.amount,
        amount_words=amount_in_words(p.amount),
        notes=p.notes,
        stamp=stamp,
        footer_text=f"{company.name} · Receipt {p.receipt_number}",
    )


def advance_receipt_pdf(a) -> bytes:
    company = CompanySettings.load()
    rows = _mode_rows(a)
    if a.project_id:
        rows.append(("Project", f"{a.project.name} ({a.project.code})"))
    if a.quotation_id:
        rows.append(("Against quotation", f"{a.quotation.number} Rev {a.quotation.revision}"))
    rows += [
        ("Adjusted so far", format_inr(a.adjusted_amount)),
        ("Refunded", format_inr(a.refunded_amount)),
        ("Unused balance", format_inr(a.balance)),
    ]
    return render_receipt(
        company=company,
        title="Advance Receipt",
        number=a.receipt_number,
        on=a.date,
        party_title="Received from",
        party_lines=_party(a.customer),
        rows=rows,
        amount=a.amount,
        amount_words=amount_in_words(a.amount),
        notes=a.notes,
        stamp="CANCELLED" if a.is_deleted else None,
        footer_text=f"{company.name} · Advance receipt {a.receipt_number}",
    )


def refund_pdf(r) -> bytes:
    company = CompanySettings.load()
    rows = [
        (
            "Refund of advance",
            f"{r.advance.receipt_number} dated {r.advance.date:%d/%m/%Y} "
            f"({format_inr(r.advance.amount)})",
        ),
        ("Reason", r.reason),
        ("Mode", r.get_mode_display()),
        ("Reference", r.reference_number),
    ]
    return render_receipt(
        company=company,
        title="Refund Voucher",
        number=r.refund_number,
        on=r.date,
        party_title="Paid to",
        party_lines=_party(r.advance.customer),
        rows=rows,
        amount=r.amount,
        amount_words=amount_in_words(r.amount),
        footer_text=f"{company.name} · Refund {r.refund_number}",
    )


def receipt_message(p, kind="payment"):
    company = CompanySettings.load()
    number = p.receipt_number
    return (
        f"Dear {p.customer.name},\n\nWe have received {format_inr(p.amount)} by {p.get_mode_display()} on "
        f"{p.date:%d/%m/%Y} ({'advance ' if kind == 'advance' else ''}receipt {number}). Thank you!\n\n"
        f"{company.name}" + (f"\n{company.phone}" if company.phone else "")
    )
