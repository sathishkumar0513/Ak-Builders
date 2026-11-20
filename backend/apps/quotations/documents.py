"""PDF + email for quotations."""

from django.conf import settings
from django.core.mail import EmailMessage

from apps.core.documents_util import gst_summary_from_items
from apps.core.models import CompanySettings
from apps.core.pdf import render_gst_document
from apps.core.utils import INDIAN_STATES, format_inr


def pdf_filename(q):
    return f"Quotation-{q.number.replace('/', '-')}-R{q.revision}.pdf"


def quotation_pdf(q) -> bytes:
    company = CompanySettings.load()
    c = q.customer
    items = list(q.items.all())
    party = [
        c.name,
        c.contact_person and f"Attn: {c.contact_person}",
        c.address,
        ", ".join(filter(None, [c.city, c.pincode])),
        f"Phone: {c.phone}" + (f" / {c.alternate_phone}" if c.alternate_phone else ""),
        c.email,
        c.gstin and f"GSTIN: {c.gstin}",
    ]
    site = [
        q.title or "",
        q.site_address or "Same as billing address",
        f"Place of supply: {INDIAN_STATES.get(q.place_of_supply, '')} ({q.place_of_supply})",
        "Tax: IGST (inter-state)" if q.is_interstate else "Tax: CGST + SGST (intra-state)",
    ]
    meta = [
        ("Quotation no.", q.number),
        ("Revision", f"Rev {q.revision}"),
        ("Date", q.quotation_date.strftime("%d/%m/%Y")),
        ("Valid until", q.valid_until.strftime("%d/%m/%Y")),
    ]
    return render_gst_document(
        company=company,
        title="Quotation",
        meta=meta,
        party_title="Quotation for",
        party_lines=party,
        extra_box=("Project / site", site),
        items=items,
        doc=q,
        gst_summary=gst_summary_from_items(items),
        terms=q.terms_and_conditions,
        notes=q.notes,
        show_bank=True,
        footer_text=f"{company.name} · {q.number} Rev {q.revision} · This is a computer-generated quotation.",
    )


def default_share_message(q):
    company = CompanySettings.load()
    return (
        f"Dear {q.customer.name},\n\n"
        f"Please find our quotation {q.number} (Rev {q.revision}){' for ' + q.title if q.title else ''}.\n"
        f"Amount: {format_inr(q.grand_total)} (incl. GST)\n"
        f"Valid until: {q.valid_until.strftime('%d/%m/%Y')}\n\n"
        f"For any questions, call us at {company.phone or '—'}.\n\nRegards,\n{company.name}"
    )


def email_quotation(q, *, to, cc=None, subject=None, message=None):
    company = CompanySettings.load()
    email = EmailMessage(
        subject=subject or f"Quotation {q.number} (Rev {q.revision}) from {company.name}",
        body=message or default_share_message(q),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        cc=cc or [],
        reply_to=[company.email] if company.email else None,
    )
    email.attach(pdf_filename(q), quotation_pdf(q), "application/pdf")
    email.send(fail_silently=False)
