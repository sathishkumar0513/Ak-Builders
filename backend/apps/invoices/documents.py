from django.conf import settings
from django.core.mail import EmailMessage

from apps.core.documents_util import gst_summary_from_items
from apps.core.models import CompanySettings
from apps.core.pdf import render_gst_document
from apps.core.utils import INDIAN_STATES, format_inr


def pdf_filename(inv):
    return f"Invoice-{inv.number.replace('/', '-')}.pdf"


def invoice_pdf(inv) -> bytes:
    company = CompanySettings.load()
    c = inv.customer
    items = list(inv.items.all())
    party = [
        inv.billing_name,
        inv.billing_address,
        f"Phone: {c.phone}",
        inv.billing_gstin and f"GSTIN: {inv.billing_gstin}",
        f"State: {INDIAN_STATES.get(c.state_code, '')} ({c.state_code})",
    ]
    site = []
    if inv.project_id:
        site += [f"{inv.project.name} ({inv.project.code})", inv.project.site_address]
    if inv.payment_stage_id:
        site.append(f"Stage: {inv.payment_stage.name}")
    if inv.quotation_id:
        site.append(f"Ref. quotation {inv.quotation.number} Rev {inv.quotation.revision}")
    site += [
        f"Place of supply: {INDIAN_STATES.get(inv.place_of_supply, '')} ({inv.place_of_supply})",
        "Tax: IGST (inter-state)" if inv.is_interstate else "Tax: CGST + SGST (intra-state)",
    ]
    meta = [("Invoice no.", inv.number), ("Invoice date", inv.invoice_date.strftime("%d/%m/%Y"))]
    if inv.due_date:
        meta.append(("Due date", inv.due_date.strftime("%d/%m/%Y")))
    settlement = []
    if inv.advance_adjusted:
        settlement.append(("Advance adjusted", f"− {format_inr(inv.advance_adjusted)}"))
    if inv.amount_paid:
        settlement.append(("Received", f"− {format_inr(inv.amount_paid)}"))
    if settlement:
        settlement.append(("Balance due", format_inr(inv.balance_due)))
    stamp = "CANCELLED" if inv.status == "CANCELLED" else ("PAID" if inv.status == "PAID" else None)
    return render_gst_document(
        company=company,
        title="Tax Invoice",
        meta=meta,
        party_title="Bill to",
        party_lines=party,
        extra_box=("Project / supply details", site),
        items=items,
        doc=inv,
        gst_summary=gst_summary_from_items(items),
        terms=inv.terms_and_conditions,
        notes=inv.notes,
        settlement_rows=settlement,
        stamp=stamp,
        footer_text=f"{company.name} · Invoice {inv.number} · This is a computer-generated invoice.",
    )


def share_message(inv):
    company = CompanySettings.load()
    lines = [
        f"Dear {inv.billing_name},",
        "",
        f"Please find invoice {inv.number} dated {inv.invoice_date:%d/%m/%Y}.",
    ]
    lines.append(f"Invoice amount: {format_inr(inv.grand_total)}")
    if inv.advance_adjusted or inv.amount_paid:
        lines.append(f"Balance due: {format_inr(inv.balance_due)}")
    if inv.due_date:
        lines.append(f"Due date: {inv.due_date:%d/%m/%Y}")
    if company.upi_id:
        lines.append(f"UPI: {company.upi_id}")
    if company.bank_account_number:
        lines.append(f"Bank: {company.bank_name} A/c {company.bank_account_number} IFSC {company.bank_ifsc}")
    lines += ["", f"Thank you,\n{company.name}" + (f"\n{company.phone}" if company.phone else "")]
    return "\n".join(lines)


def reminder_message(inv):
    company = CompanySettings.load()
    overdue = ""
    if inv.due_date:
        from datetime import date

        days = (date.today() - inv.due_date).days
        overdue = f" (overdue by {days} day{'s' if days != 1 else ''})" if days > 0 else ""
    msg = (
        f"Dear {inv.billing_name},\n\nThis is a gentle reminder that {format_inr(inv.balance_due)} "
        "is pending on "
        f"invoice {inv.number} dated {inv.invoice_date:%d/%m/%Y}"
        f"{f', due on {inv.due_date:%d/%m/%Y}' if inv.due_date else ''}{overdue}.\n"
    )
    if company.upi_id:
        msg += f"\nUPI: {company.upi_id}"
    if company.bank_account_number:
        msg += f"\nBank: {company.bank_name} A/c {company.bank_account_number} IFSC {company.bank_ifsc}"
    msg += f"\n\nPlease ignore if already paid. Thank you,\n{company.name}" + (
        f"\n{company.phone}" if company.phone else ""
    )
    return msg


def email_invoice(inv, *, to, cc=None, subject=None, message=None):
    company = CompanySettings.load()
    email = EmailMessage(
        subject=subject or f"Invoice {inv.number} from {company.name}",
        body=message or share_message(inv),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        cc=cc or [],
        reply_to=[company.email] if company.email else None,
    )
    email.attach(pdf_filename(inv), invoice_pdf(inv), "application/pdf")
    email.send(fail_silently=False)
