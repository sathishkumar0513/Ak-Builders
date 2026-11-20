from django.db import models

from apps.core.documents import GSTLineItemModel, GSTTotalsModel
from apps.core.fields import MoneyField
from apps.core.models import BaseModel


class Quotation(BaseModel, GSTTotalsModel):
    """
    Versioned quotation. A revision keeps the same `number` and bumps `revision`
    (AK/QT/2026-27/0007 Rev 2). Only one revision per number is `is_latest`.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SENT = "SENT", "Sent"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        CONVERTED = "CONVERTED", "Converted to project"

    number = models.CharField(max_length=30, db_index=True)
    revision = models.PositiveSmallIntegerField(default=1)
    previous_revision = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="next_revisions"
    )
    is_latest = models.BooleanField(default=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="quotations")
    title = models.CharField(max_length=200, blank=True, help_text="e.g. 'Kitchen renovation – Ground floor'")
    site_address = models.TextField(blank=True)
    quotation_date = models.DateField(db_index=True)
    valid_until = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    header_discount = MoneyField()
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-quotation_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["number", "revision"], name="uniq_quotation_revision")]

    def __str__(self):
        return f"{self.number} Rev {self.revision}"


class QuotationItem(GSTLineItemModel):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="items")
