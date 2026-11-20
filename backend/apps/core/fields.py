from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class MoneyField(models.DecimalField):
    """Decimal(12,2) money in INR. Never use FloatField for money."""

    def __init__(self, *args, allow_negative=False, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("default", Decimal("0.00"))
        self.allow_negative = allow_negative
        if not allow_negative:
            kwargs.setdefault("validators", [MinValueValidator(Decimal("0.00"))])
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.allow_negative:
            kwargs["allow_negative"] = True
        return name, path, args, kwargs


class QuantityField(models.DecimalField):
    """Decimal(12,3) quantity — supports kg/ton/sq.ft fractions."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 3)
        kwargs.setdefault("default", Decimal("0.000"))
        super().__init__(*args, **kwargs)


class PercentField(models.DecimalField):
    """Decimal(5,2) percentage, e.g. GST 18.00 or discount 2.50."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 5)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("default", Decimal("0.00"))
        super().__init__(*args, **kwargs)
