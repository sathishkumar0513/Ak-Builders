from django.conf import settings
from django.db import models

from apps.core.documents import GSTLineItemModel, GSTTotalsModel
from apps.core.fields import MoneyField, QuantityField
from apps.core.models import BaseModel, PaymentMode
from apps.core.utils import STATE_CHOICES


class Supplier(BaseModel):
    name = models.CharField(max_length=150, db_index=True)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=15, db_index=True)
    alternate_phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=2, choices=STATE_CHOICES, default="33")
    pincode = models.CharField(max_length=6, blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    opening_balance = MoneyField()  # amount we owed the supplier when we started using the system
    bank_details = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Purchase(BaseModel, GSTTotalsModel):
    """Purchase order / purchase bill. Receiving quantities increases stock (via StockMovement)."""

    class Status(models.TextChoices):
        ORDERED = "ORDERED", "Ordered"
        PARTIAL = "PARTIAL", "Partially received"
        RECEIVED = "RECEIVED", "Received"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"

    po_number = models.CharField(max_length=30, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    supplier_invoice_number = models.CharField(max_length=50, blank=True, db_index=True)
    supplier_invoice_date = models.DateField(null=True, blank=True)
    purchase_date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ORDERED)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    transport_charges = MoneyField()
    amount_paid = MoneyField()
    balance_due = MoneyField()
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchases",
        help_text="Optional: material bought directly for one site",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def __str__(self):
        return self.po_number


class PurchaseItem(GSTLineItemModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    received_quantity = QuantityField()

    class Meta(GSTLineItemModel.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(received_quantity__lte=models.F("quantity")),
                name="received_not_more_than_ordered",
            )
        ]


class SupplierPayment(BaseModel):
    voucher_number = models.CharField(max_length=30, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="payments")
    purchase = models.ForeignKey(
        Purchase, null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    date = models.DateField(db_index=True)
    amount = MoneyField()
    mode = models.CharField(max_length=10, choices=PaymentMode.choices, default=PaymentMode.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="supplier_payment_positive")
        ]

    def __str__(self):
        return f"{self.voucher_number} – {self.supplier}"
