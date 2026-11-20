from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.fields import MoneyField, PercentField, QuantityField
from apps.core.models import BaseModel, TimeStampedModel, Unit


class MaterialCategory(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Material categories"

    def __str__(self):
        return self.name


class Material(BaseModel):
    category = models.ForeignKey(MaterialCategory, on_delete=models.PROTECT, related_name="materials")
    name = models.CharField(max_length=150, db_index=True)
    brand = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=50, blank=True, db_index=True)
    hsn_code = models.CharField(max_length=8, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.PIECE)
    purchase_price = MoneyField()
    selling_price = MoneyField()
    gst_rate = PercentField(default=Decimal("18.00"))
    stock_quantity = QuantityField()  # kept in sync by StockMovement service — never edit directly
    reorder_level = QuantityField()
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["category__name", "name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0), name="material_stock_not_negative"
            ),
            models.UniqueConstraint(
                fields=["name", "brand"],
                condition=models.Q(is_deleted=False),
                name="uniq_material_name_brand",
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.brand}".strip()

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.reorder_level


class PriceHistory(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="price_history")
    old_purchase_price = MoneyField()
    new_purchase_price = MoneyField()
    old_selling_price = MoneyField()
    new_selling_price = MoneyField()
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name_plural = "Price history"


class StockMovement(TimeStampedModel):
    """
    Immutable stock ledger. Every stock change (purchase receipt, site issue, return, adjustment)
    writes one row and updates Material.stock_quantity in the same transaction.
    """

    class MovementType(models.TextChoices):
        PURCHASE_IN = "PURCHASE_IN", "Purchase received"
        SITE_ISSUE = "SITE_ISSUE", "Issued to site"
        SITE_RETURN = "SITE_RETURN", "Returned from site"
        SALE_OUT = "SALE_OUT", "Sold (invoice)"
        ADJUST_IN = "ADJUST_IN", "Adjustment +"
        ADJUST_OUT = "ADJUST_OUT", "Adjustment -"
        OPENING = "OPENING", "Opening stock"

    INWARD = {"PURCHASE_IN", "SITE_RETURN", "ADJUST_IN", "OPENING"}

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=15, choices=MovementType.choices)
    quantity = QuantityField()  # always positive; direction comes from movement_type
    balance_after = QuantityField()
    rate = MoneyField()
    date = models.DateField(db_index=True)
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="stock_movements"
    )
    reference_type = models.CharField(max_length=50, blank=True)  # "Purchase", "ProjectMaterialIssue"
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["material", "date"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]

    @property
    def signed_quantity(self):
        return self.quantity if self.movement_type in self.INWARD else -self.quantity
