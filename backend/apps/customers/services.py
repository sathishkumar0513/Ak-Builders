from decimal import Decimal

from django.db.models import Sum, Value
from django.db.models.functions import Coalesce

ZERO = Decimal("0.00")


def outstanding_annotation():
    """Σ ledger debit − Σ ledger credit (positive = customer owes us; negative = unused advance)."""
    return Coalesce(Sum("ledger_entries__debit"), Value(ZERO)) - Coalesce(
        Sum("ledger_entries__credit"), Value(ZERO)
    )


def customer_summary(customer):
    from apps.invoices.models import Invoice
    from apps.payments.models import AdvancePayment, CustomerLedgerEntry, Payment
    from apps.projects.models import Project
    from apps.quotations.models import Quotation

    ledger = CustomerLedgerEntry.objects.filter(customer=customer).aggregate(
        debit=Coalesce(Sum("debit"), Value(ZERO)), credit=Coalesce(Sum("credit"), Value(ZERO))
    )
    advances = AdvancePayment.objects.filter(customer=customer).exclude(status=AdvancePayment.Status.REFUNDED)
    advance_balance = sum((a.balance for a in advances), ZERO)
    invoices = Invoice.objects.filter(customer=customer).exclude(status=Invoice.Status.CANCELLED)
    return {
        "total_billed": invoices.aggregate(v=Coalesce(Sum("grand_total"), Value(ZERO)))["v"],
        "total_received": Payment.objects.filter(customer=customer).aggregate(
            v=Coalesce(Sum("amount"), Value(ZERO))
        )["v"]
        + advances.aggregate(v=Coalesce(Sum("amount"), Value(ZERO)))["v"],
        "outstanding": ledger["debit"] - ledger["credit"],
        "advance_balance": advance_balance,
        "counts": {
            "projects": Project.objects.filter(customer=customer).count(),
            "quotations": Quotation.objects.filter(customer=customer, is_latest=True).count(),
            "invoices": invoices.count(),
            "payments": Payment.objects.filter(customer=customer).count(),
        },
        "recent_quotations": list(
            Quotation.objects.filter(customer=customer, is_latest=True)
            .order_by("-quotation_date")[:5]
            .values("id", "number", "revision", "quotation_date", "status", "grand_total")
        ),
        "recent_projects": list(
            Project.objects.filter(customer=customer)
            .order_by("-created_at")[:5]
            .values("id", "code", "name", "status")
        ),
        "recent_payments": list(
            Payment.objects.filter(customer=customer)
            .order_by("-date")[:5]
            .values("id", "receipt_number", "date", "amount", "mode")
        ),
    }
