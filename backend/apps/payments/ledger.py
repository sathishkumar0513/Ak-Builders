"""
Customer ledger postings. Every money document writes here inside the same transaction:

    Invoice issued ............ DEBIT  grand total     (customer owes us)
    Advance received .......... CREDIT amount
    Payment received .......... CREDIT amount
    Advance refunded .......... DEBIT  amount
    Cheque bounced ............ DEBIT  amount          (the earlier credit is undone)
    Invoice / receipt cancelled  REVERSAL of the original entry (opposite side)

Advance *adjustment* against an invoice posts nothing: the advance was already credited
when it was received, so the balance is already correct.

Outstanding = Σ debit − Σ credit (negative = customer has unused advance with us).
"""

from decimal import Decimal

from django.db.models import Sum, Value
from django.db.models.functions import Coalesce

from apps.core.middleware import get_current_user

from .models import CustomerLedgerEntry

ZERO = Decimal("0.00")
E = CustomerLedgerEntry.EntryType


def post(*, customer, date, entry_type, debit=ZERO, credit=ZERO, reference, narration="", project=None):
    return CustomerLedgerEntry.objects.create(
        customer=customer,
        project=project,
        date=date,
        entry_type=entry_type,
        debit=debit,
        credit=credit,
        reference_type=reference._meta.label,
        reference_id=reference.pk,
        reference_number=_number_of(reference),
        narration=narration[:255],
        created_by=get_current_user(),
    )


def reverse(*, reference, date, narration=""):
    """Post the opposite of every entry for a document (used when it is cancelled)."""
    entries = CustomerLedgerEntry.objects.filter(
        reference_type=reference._meta.label, reference_id=reference.pk
    ).exclude(entry_type=E.REVERSAL)
    for e in entries:
        CustomerLedgerEntry.objects.create(
            customer=e.customer,
            project=e.project,
            date=date,
            entry_type=E.REVERSAL,
            debit=e.credit,
            credit=e.debit,
            reference_type=e.reference_type,
            reference_id=e.reference_id,
            reference_number=e.reference_number,
            narration=(narration or f"Reversal of {e.get_entry_type_display()}")[:255],
            created_by=get_current_user(),
        )


def update_invoice_posting(invoice):
    """Invoice edited while still unpaid → keep its single debit entry equal to the new total."""
    CustomerLedgerEntry.objects.filter(
        reference_type=invoice._meta.label, reference_id=invoice.pk, entry_type=E.INVOICE
    ).update(
        debit=invoice.grand_total,
        date=invoice.invoice_date,
        project=invoice.project,
        narration=_invoice_narration(invoice),
    )


def _invoice_narration(invoice):
    return f"Invoice {invoice.number}" + (f" · {invoice.project.code}" if invoice.project_id else "")


def _number_of(obj):
    for attr in ("number", "receipt_number", "refund_number", "voucher_number"):
        if getattr(obj, attr, None):
            return getattr(obj, attr)
    return ""


def balance(customer, until=None) -> Decimal:
    qs = CustomerLedgerEntry.objects.filter(customer=customer)
    if until:
        qs = qs.filter(date__lte=until)
    agg = qs.aggregate(d=Coalesce(Sum("debit"), Value(ZERO)), c=Coalesce(Sum("credit"), Value(ZERO)))
    return agg["d"] - agg["c"]


def statement(customer, date_from=None, date_to=None):
    """Rows with running balance + opening balance before date_from."""
    opening = ZERO
    qs = (
        CustomerLedgerEntry.objects.filter(customer=customer).select_related("project").order_by("date", "id")
    )
    if date_from:
        before = qs.filter(date__lt=date_from).aggregate(
            d=Coalesce(Sum("debit"), Value(ZERO)), c=Coalesce(Sum("credit"), Value(ZERO))
        )
        opening = before["d"] - before["c"]
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    running = opening
    rows = []
    for e in qs:
        running += e.debit - e.credit
        rows.append(
            {
                "id": e.id,
                "date": e.date,
                "entry_type": e.entry_type,
                "entry_type_display": e.get_entry_type_display(),
                "reference_type": e.reference_type,
                "reference_id": e.reference_id,
                "reference_number": e.reference_number,
                "project": e.project.code if e.project_id else None,
                "narration": e.narration,
                "debit": e.debit,
                "credit": e.credit,
                "balance": running,
            }
        )
    total_debit = sum((r["debit"] for r in rows), ZERO)
    total_credit = sum((r["credit"] for r in rows), ZERO)
    return {
        "opening_balance": opening,
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "closing_balance": running,
    }
