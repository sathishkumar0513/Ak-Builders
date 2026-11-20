"""
Abstract models shared by Quotation, Invoice and Purchase (header totals + GST line items).
Totals are calculated in services (Phase 4/5) with apps.core.utils helpers — never in the browser alone.
"""

from django.db import models

from .fields import MoneyField, PercentField, QuantityField
from .models import Unit


class GSTTotalsModel(models.Model):
    place_of_supply = models.CharField(max_length=2, default="33")  # state code
    is_interstate = models.BooleanField(default=False)  # True → IGST, False → CGST+SGST
    subtotal = MoneyField()  # Σ qty × rate
    discount_total = MoneyField()  # Σ line discounts + header discount
    taxable_amount = MoneyField()
    cgst_amount = MoneyField()
    sgst_amount = MoneyField()
    igst_amount = MoneyField()
    round_off = MoneyField(allow_negative=True)
    grand_total = MoneyField()
    amount_in_words = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True

    @property
    def total_tax(self):
        return self.cgst_amount + self.sgst_amount + self.igst_amount


class GSTLineItemModel(models.Model):
    class ItemType(models.TextChoices):
        MATERIAL = "MATERIAL", "Material"
        SERVICE = "SERVICE", "Service / Labour / Work"

    item_type = models.CharField(max_length=10, choices=ItemType.choices, default=ItemType.MATERIAL)
    material = models.ForeignKey(
        "materials.Material", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    description = models.CharField(max_length=255)
    hsn_code = models.CharField(max_length=8, blank=True)  # HSN for goods, SAC for services
    quantity = QuantityField()
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.NOS)
    rate = MoneyField()
    discount_percent = PercentField()
    discount_amount = MoneyField()
    taxable_amount = MoneyField()
    gst_rate = PercentField()
    cgst_amount = MoneyField()
    sgst_amount = MoneyField()
    igst_amount = MoneyField()
    line_total = MoneyField()
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.description
