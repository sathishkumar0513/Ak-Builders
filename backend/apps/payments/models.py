from django.conf import settings
from django.db import models

from apps.core.fields import MoneyField
from apps.core.models import BaseModel, PaymentMode, TimeStampedModel


class ChequeFieldsMixin(models.Model):
    cheque_number = models.CharField(max_length=20, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)

    class Meta:
        abstract = True


class AdvancePayment(BaseModel, ChequeFieldsMixin):
    """
    Money received before billing. balance = amount - adjusted_amount - refunded_amount.
    Adjusted against invoices through AdvanceAdjustment rows.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        PARTIAL = "PARTIAL", "Partially adjusted"
        ADJUSTED = "ADJUSTED", "Fully adjusted"
        REFUNDED = "REFUNDED", "Refunded"

    receipt_number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="advances")
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="advances"
    )
    quotation = models.ForeignKey(
        "quotations.Quotation", null=True, blank=True, on_delete=models.SET_NULL, related_name="advances"
    )
    date = models.DateField(db_index=True)
    amount = MoneyField()
    mode = models.CharField(max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH)
    reference_number = models.CharField(max_length=100, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    adjusted_amount = MoneyField()
    refunded_amount = MoneyField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="advance_amount_positive"),
            models.CheckConstraint(
                condition=models.Q(amount__gte=models.F("adjusted_amount") + models.F("refunded_amount")),
                name="advance_not_over_used",
            ),
        ]

    def __str__(self):
        return f"{self.receipt_number} – ₹{self.amount}"

    @property
    def balance(self):
        return self.amount - self.adjusted_amount - self.refunded_amount


class AdvanceAdjustment(TimeStampedModel):
    advance = models.ForeignKey(AdvancePayment, on_delete=models.PROTECT, related_name="adjustments")
    invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.PROTECT, related_name="advance_adjustments"
    )
    amount = MoneyField()
    date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="adjustment_positive")]


class AdvanceRefund(BaseModel):
    refund_number = models.CharField(max_length=30, unique=True)
    advance = models.ForeignKey(AdvancePayment, on_delete=models.PROTECT, related_name="refunds")
    date = models.DateField()
    amount = MoneyField()
    mode = models.CharField(max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH)
    reference_number = models.CharField(max_length=100, blank=True)
    reason = models.CharField(max_length=255)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="refund_positive")]


class Payment(BaseModel, ChequeFieldsMixin):
    """Customer payment against an invoice and/or project stage."""

    class ChequeStatus(models.TextChoices):
        NA = "NA", "Not a cheque"
        PENDING = "PENDING", "Pending clearance"
        CLEARED = "CLEARED", "Cleared"
        BOUNCED = "BOUNCED", "Bounced"

    receipt_number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="payments")
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    invoice = models.ForeignKey(
        "invoices.Invoice", null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    payment_stage = models.ForeignKey(
        "projects.PaymentStage", null=True, blank=True, on_delete=models.SET_NULL, related_name="payments"
    )
    date = models.DateField(db_index=True)
    amount = MoneyField()
    mode = models.CharField(
        max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH, db_index=True
    )
    reference_number = models.CharField(max_length=100, blank=True, help_text="UPI / bank transaction ID")
    cheque_status = models.CharField(max_length=10, choices=ChequeStatus.choices, default=ChequeStatus.NA)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["customer", "date"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive")
        ]

    def __str__(self):
        return f"{self.receipt_number} – ₹{self.amount}"


class CustomerLedgerEntry(models.Model):
    """
    Running customer account. Debit = customer owes us (invoice, refund paid out).
    Credit = we received money (payment, advance). Advance *adjustment* is not posted
    again because the advance was already credited when received.
    """

    class EntryType(models.TextChoices):
        OPENING = "OPENING", "Opening balance"
        INVOICE = "INVOICE", "Invoice"
        PAYMENT = "PAYMENT", "Payment received"
        ADVANCE = "ADVANCE", "Advance received"
        REFUND = "REFUND", "Advance refunded"
        INVOICE_CANCEL = "INV_CANCEL", "Invoice cancelled"
        CHEQUE_BOUNCE = "BOUNCE", "Cheque bounced"
        REVERSAL = "REVERSAL", "Reversal (cancelled entry)"

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="ledger_entries"
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date = models.DateField(db_index=True)
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    debit = MoneyField()
    credit = MoneyField()
    reference_type = models.CharField(max_length=50)
    reference_id = models.PositiveBigIntegerField()
    reference_number = models.CharField(max_length=30, blank=True)
    narration = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["date", "id"]
        verbose_name_plural = "Customer ledger entries"
        indexes = [
            models.Index(fields=["customer", "date"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]


class PaymentReminder(TimeStampedModel):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="reminders")
    invoice = models.ForeignKey(
        "invoices.Invoice", null=True, blank=True, on_delete=models.CASCADE, related_name="reminders"
    )
    payment_stage = models.ForeignKey(
        "projects.PaymentStage", null=True, blank=True, on_delete=models.CASCADE, related_name="reminders"
    )
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.WHATSAPP)
    scheduled_for = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=255, blank=True)
