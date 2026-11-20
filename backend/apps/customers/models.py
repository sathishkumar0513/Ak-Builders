from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import BaseModel
from apps.core.utils import STATE_CHOICES

phone_validator = RegexValidator(r"^[6-9]\d{9}$", "Enter a valid 10-digit Indian mobile number.")
gstin_validator = RegexValidator(
    r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", "Enter a valid 15-character GSTIN."
)
pincode_validator = RegexValidator(r"^\d{6}$", "Enter a valid 6-digit pincode.")


class Customer(BaseModel):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        COMPANY = "COMPANY", "Company"

    name = models.CharField(max_length=150, db_index=True)
    customer_type = models.CharField(
        max_length=12, choices=CustomerType.choices, default=CustomerType.INDIVIDUAL
    )
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=10, validators=[phone_validator], db_index=True)
    alternate_phone = models.CharField(max_length=10, validators=[phone_validator], blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    state_code = models.CharField(max_length=2, choices=STATE_CHOICES, default="33")
    pincode = models.CharField(max_length=6, validators=[pincode_validator], blank=True)
    gstin = models.CharField(max_length=15, validators=[gstin_validator], blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name", "phone"])]

    def __str__(self):
        return f"{self.name} ({self.phone})"
