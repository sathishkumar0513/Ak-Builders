"""
Stock and price logic. EVERY stock change in the system goes through record_movement(),
which locks the material row, refuses to go below zero and writes a StockMovement.
"""

from datetime import date as date_cls
from decimal import Decimal

from django.db import transaction

from apps.core.exceptions import BusinessRuleError
from apps.core.middleware import get_current_user
from apps.core.utils import money

from .models import Material, PriceHistory, StockMovement

QTY = Decimal("0.001")


def _fmt_qty(q):
    q = Decimal(q).normalize()
    return f"{q:f}"


@transaction.atomic
def record_movement(
    *,
    material,
    movement_type,
    quantity,
    rate=None,
    date=None,
    project=None,
    reference_type="",
    reference_id=None,
    note="",
):
    qty = Decimal(str(quantity)).quantize(QTY)
    if qty <= 0:
        raise BusinessRuleError("Quantity must be more than zero.", field="quantity")
    locked = Material.all_objects.select_for_update().get(
        pk=material.pk if hasattr(material, "pk") else material
    )
    inward = movement_type in StockMovement.INWARD
    new_balance = locked.stock_quantity + qty if inward else locked.stock_quantity - qty
    if new_balance < 0:
        raise BusinessRuleError(
            f"Not enough stock of {locked}: available {_fmt_qty(locked.stock_quantity)} {locked.unit}, "
            f"requested {_fmt_qty(qty)}.",
            field="quantity",
        )
    locked.stock_quantity = new_balance
    locked._skip_audit = True
    locked.save(update_fields=["stock_quantity", "updated_at"])
    if hasattr(material, "stock_quantity"):
        material.stock_quantity = new_balance  # keep caller's object in sync
    return StockMovement.objects.create(
        material=locked,
        movement_type=movement_type,
        quantity=qty,
        balance_after=new_balance,
        rate=money(rate if rate is not None else locked.purchase_price),
        date=date or date_cls.today(),
        project=project,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note[:255],
    )


def adjust_stock(*, material, direction, quantity, reason, date=None):
    if direction not in ("IN", "OUT"):
        raise BusinessRuleError("Direction must be IN or OUT.", field="direction")
    movement_type = (
        StockMovement.MovementType.ADJUST_IN if direction == "IN" else StockMovement.MovementType.ADJUST_OUT
    )
    return record_movement(
        material=material,
        movement_type=movement_type,
        quantity=quantity,
        date=date,
        reference_type="Adjustment",
        note=reason,
    )


@transaction.atomic
def change_prices(*, material, purchase_price=None, selling_price=None, reason=""):
    """Updates rates and writes PriceHistory only when something actually changed."""
    new_p = money(purchase_price) if purchase_price is not None else material.purchase_price
    new_s = money(selling_price) if selling_price is not None else material.selling_price
    if new_p == material.purchase_price and new_s == material.selling_price:
        return None
    history = PriceHistory.objects.create(
        material=material,
        old_purchase_price=material.purchase_price,
        new_purchase_price=new_p,
        old_selling_price=material.selling_price,
        new_selling_price=new_s,
        reason=reason[:255],
        changed_by=get_current_user(),
    )
    material.purchase_price = new_p
    material.selling_price = new_s
    material.save(update_fields=["purchase_price", "selling_price", "updated_at", "updated_by"])
    return history


@transaction.atomic
def create_material(*, data, opening_stock=None):
    material = Material.objects.create(**data)
    if opening_stock:
        record_movement(
            material=material,
            movement_type=StockMovement.MovementType.OPENING,
            quantity=opening_stock,
            rate=material.purchase_price,
            reference_type="Opening",
            note="Opening stock",
        )
    return material


@transaction.atomic
def update_material(*, material, data, price_reason=""):
    purchase_price = data.pop("purchase_price", None)
    selling_price = data.pop("selling_price", None)
    for field, value in data.items():
        setattr(material, field, value)
    material.save()
    change_prices(
        material=material,
        purchase_price=purchase_price,
        selling_price=selling_price,
        reason=price_reason or "Edited in material master",
    )
    return material


def low_stock_queryset():
    from django.db.models import F

    return Material.objects.filter(is_active=True, stock_quantity__lte=F("reorder_level")).select_related(
        "category"
    )
