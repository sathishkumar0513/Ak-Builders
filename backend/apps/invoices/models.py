from django.db import models

from apps.core.documents import GSTLineItemModel, GSTTotalsModel
from apps.core.fields import MoneyField
from apps.core.models import BaseModel


class Invoice(BaseModel, GSTTotalsModel):
    """GST tax invoice. Number series: AK/2026-27/0001."""

    class Status(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="invoices")
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="invoices"
    )
    quotation = models.ForeignKey(
        "quotations.Quotation", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    payment_stage = models.ForeignKey(
        "projects.PaymentStage", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    invoice_date = models.DateField(db_index=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID, db_index=True)
    # Customer snapshot at the time of billing (invoice must not change if customer is edited later)
    billing_name = models.CharField(max_length=150)
    billing_address = models.TextField(blank=True)
    billing_gstin = models.CharField(max_length=15, blank=True)
    header_discount = MoneyField()
    advance_adjusted = MoneyField()
    amount_paid = MoneyField()
    balance_due = MoneyField()
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    cancelled_reason = models.CharField(max_length=255, blank=True)
    deduct_stock = models.BooleanField(
        default=False,
        help_text="Direct material sale from the store: reduces stock (not used for project billing)",
    )

    class Meta:
        ordering = ["-invoice_date", "-id"]
        indexes = [models.Index(fields=["customer", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance_due__gte=0), name="invoice_balance_not_negative"
            )
        ]

    def __str__(self):
        return self.number


class InvoiceItem(GSTLineItemModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
