from django.conf import settings
from django.db import models

from apps.core.fields import MoneyField
from apps.core.models import BaseModel, PaymentMode
from apps.core.uploads import expense_bill_path


class Expense(BaseModel):
    class Category(models.TextChoices):
        LABOUR = "LABOUR", "Labour wages"
        TRANSPORT = "TRANSPORT", "Transport"
        SITE = "SITE", "Site expense"
        LOCAL_MATERIAL = "LOCAL_MAT", "Local material purchase"
        EQUIPMENT = "EQUIPMENT", "Equipment / tool hire"
        FUEL = "FUEL", "Fuel"
        OFFICE = "OFFICE", "Office / rent"
        MISC = "MISC", "Miscellaneous"

    voucher_number = models.CharField(max_length=30, unique=True)
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="expenses",
        help_text="Leave empty for office/overhead expenses",
    )
    category = models.CharField(max_length=10, choices=Category.choices, db_index=True)
    date = models.DateField(db_index=True)
    amount = MoneyField()
    paid_to = models.CharField(max_length=150, blank=True)
    mode = models.CharField(max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH)
    reference_number = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255, blank=True)
    # Labour-specific (optional)
    workers_count = models.PositiveSmallIntegerField(null=True, blank=True)
    work_days = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bill_attachment = models.FileField(upload_to=expense_bill_path, blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["project", "category", "date"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="expense_amount_positive")
        ]

    @property
    def is_approved(self):
        return self.approved_by_id is not None or self.approved_at is not None

    def __str__(self):
        return f"{self.voucher_number} – {self.get_category_display()} ₹{self.amount}"
