"""
Purchase & supplier-payment business logic. All money operations run inside transaction.atomic()
and lock the rows they change (select_for_update) so two users can't double-receive or over-pay.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.calculations import calculate_document
from apps.core.exceptions import BusinessRuleError
from apps.core.models import CompanySettings, DocumentSequence
from apps.core.numbering import next_document_number
from apps.core.utils import ZERO, is_interstate, money
from apps.materials.models import Material, StockMovement
from apps.materials.services import change_prices, record_movement

from .models import Purchase, PurchaseItem, Supplier, SupplierPayment

MONEY = DecimalField(max_digits=14, decimal_places=2)


# ---------------------------------------------------------------------------
# Supplier balances
# ---------------------------------------------------------------------------
def _sum_subquery(model, field, **filters):
    qs = (
        model.objects.filter(supplier=OuterRef("pk"), **filters)
        .values("supplier")
        .annotate(total=Sum(field))
        .values("total")
    )
    return Coalesce(Subquery(qs, output_field=MONEY), Value(ZERO), output_field=MONEY)


def annotate_supplier_balances(qs):
    """total_purchases, total_paid, payable (= opening + purchases − payments).
    Subqueries avoid double-counting from joins."""
    qs = qs.annotate(
        total_purchases=_sum_subquery(
            Purchase,
            "grand_total",
            is_deleted=False,
            status__in=[
                Purchase.Status.ORDERED,
                Purchase.Status.PARTIAL,
                Purchase.Status.RECEIVED,
            ],
        ),
        total_paid=_sum_subquery(SupplierPayment, "amount", is_deleted=False),
    )
    from django.db.models import F

    return qs.annotate(payable=F("opening_balance") + F("total_purchases") - F("total_paid"))


def supplier_payable(supplier) -> Decimal:
    return annotate_supplier_balances(Supplier.objects.filter(pk=supplier.pk)).get().payable


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------
def _prepare_items(items):
    """Fill description / HSN / unit / GST from the material when not given."""
    prepared = []
    for i, raw in enumerate(items):
        item = dict(raw)
        material = item.get("material")
        if item.get("item_type", PurchaseItem.ItemType.MATERIAL) == PurchaseItem.ItemType.MATERIAL:
            if material is None:
                raise BusinessRuleError(f"Line {i + 1}: select a material.", field="items")
            item.setdefault("description", str(material))
            item["description"] = item["description"] or str(material)
            item["hsn_code"] = item.get("hsn_code") or material.hsn_code
            item["unit"] = item.get("unit") or material.unit
            if item.get("gst_rate") is None:
                item["gst_rate"] = material.gst_rate
        else:
            item["material"] = None
            if not item.get("description"):
                raise BusinessRuleError(f"Line {i + 1}: enter a description.", field="items")
        if Decimal(item["quantity"]) <= 0:
            raise BusinessRuleError(f"Line {i + 1}: quantity must be more than zero.", field="items")
        item.setdefault("discount_percent", ZERO)
        item.setdefault("gst_rate", ZERO)
        item["sort_order"] = i
        prepared.append(item)
    if not prepared:
        raise BusinessRuleError("Add at least one item.", field="items")
    return prepared


def _write_items_and_totals(purchase, items):
    company = CompanySettings.load()
    purchase.place_of_supply = company.state_code
    purchase.is_interstate = is_interstate(company.state_code, purchase.supplier.state_code)
    totals = calculate_document(
        items, interstate=purchase.is_interstate, extra_charges=purchase.transport_charges
    )
    for field, value in totals.header_fields().items():
        setattr(purchase, field, value)
    purchase.save()
    purchase.items.all().delete()
    PurchaseItem.objects.bulk_create(
        PurchaseItem(
            purchase=purchase,
            item_type=item.get("item_type", PurchaseItem.ItemType.MATERIAL),
            material=item.get("material"),
            description=item["description"],
            hsn_code=item.get("hsn_code", ""),
            quantity=item["quantity"],
            unit=item.get("unit") or "nos",
            rate=money(item["rate"]),
            discount_percent=item.get("discount_percent") or ZERO,
            gst_rate=item.get("gst_rate") or ZERO,
            discount_amount=line.discount_amount,
            taxable_amount=line.taxable_amount,
            cgst_amount=line.cgst_amount,
            sgst_amount=line.sgst_amount,
            igst_amount=line.igst_amount,
            line_total=line.line_total,
            sort_order=item["sort_order"],
        )
        for item, line in zip(items, totals.lines)
    )
    _refresh_payment_status(purchase)


def _check_supplier_invoice_unique(supplier, number, exclude_pk=None):
    if not number:
        return
    qs = Purchase.objects.filter(supplier=supplier, supplier_invoice_number__iexact=number).exclude(
        status=Purchase.Status.CANCELLED
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    existing = qs.first()
    if existing:
        raise BusinessRuleError(
            f"Supplier bill {number} is already entered in {existing.po_number}.",
            field="supplier_invoice_number",
        )


@transaction.atomic
def create_purchase(*, data, items, receive_now=False):
    items = _prepare_items(items)
    _check_supplier_invoice_unique(data["supplier"], data.get("supplier_invoice_number"))
    purchase = Purchase(**data)
    purchase.po_number = next_document_number(DocumentSequence.DocType.PURCHASE_ORDER, purchase.purchase_date)
    purchase.save()
    _write_items_and_totals(purchase, items)
    if receive_now:
        receive_items(
            purchase=purchase,
            lines=[
                {"item": it.pk, "quantity": it.quantity}
                for it in purchase.items.filter(material__isnull=False)
            ],
            date=purchase.purchase_date,
        )
    return purchase


@transaction.atomic
def update_purchase(*, purchase, data, items=None):
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status != Purchase.Status.ORDERED or purchase.items.filter(received_quantity__gt=0).exists():
        raise BusinessRuleError("Goods have already been received — this purchase can no longer be edited.")
    supplier = data.get("supplier", purchase.supplier)
    if supplier != purchase.supplier and purchase.amount_paid > 0:
        raise BusinessRuleError("Payments exist for this purchase — the supplier cannot be changed.")
    _check_supplier_invoice_unique(
        supplier,
        data.get("supplier_invoice_number", purchase.supplier_invoice_number),
        exclude_pk=purchase.pk,
    )
    for field, value in data.items():
        setattr(purchase, field, value)
    if items is not None:
        _write_items_and_totals(purchase, _prepare_items(items))
    else:
        purchase.save()
    if purchase.grand_total < purchase.amount_paid:
        raise BusinessRuleError(
            f"New total ₹{purchase.grand_total} is less than the ₹{purchase.amount_paid} already paid."
        )
    return purchase


@transaction.atomic
def receive_items(*, purchase, lines, date=None, update_purchase_price=True):
    """
    lines: [{"item": <PurchaseItem id>, "quantity": Decimal}]. Increases stock at the net unit cost
    (taxable ÷ qty — GST is input credit, not cost) and updates the material's purchase price.
    """
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status in (Purchase.Status.CANCELLED, Purchase.Status.RECEIVED):
        raise BusinessRuleError(f"This purchase is {purchase.get_status_display().lower()}.")
    date = date or purchase.purchase_date
    items = {it.pk: it for it in purchase.items.select_for_update(of=("self",)).select_related("material")}
    received_any = False
    for line in lines:
        qty = Decimal(str(line["quantity"]))
        if qty == 0:
            continue
        item = items.get(int(line["item"]))
        if item is None or item.material_id is None:
            raise BusinessRuleError("Invalid item for this purchase.", field="lines")
        pending = item.quantity - item.received_quantity
        if qty < 0 or qty > pending:
            raise BusinessRuleError(
                f"{item.description}: you can receive at most {pending.normalize():f} {item.unit}.",
                field="lines",
            )
        unit_cost = money(item.taxable_amount / item.quantity) if item.quantity else item.rate
        record_movement(
            material=item.material,
            movement_type=StockMovement.MovementType.PURCHASE_IN,
            quantity=qty,
            rate=unit_cost,
            date=date,
            reference_type="Purchase",
            reference_id=purchase.pk,
            note=f"{purchase.po_number} · {purchase.supplier.name}",
        )
        item.received_quantity += qty
        item.save(update_fields=["received_quantity"])
        received_any = True
        if update_purchase_price:
            material = Material.objects.get(pk=item.material_id)
            change_prices(
                material=material, purchase_price=unit_cost, reason=f"Purchase {purchase.po_number}"
            )
    if not received_any:
        raise BusinessRuleError("Enter the quantity received for at least one item.", field="lines")

    material_items = [it for it in items.values() if it.material_id]
    if all(it.received_quantity >= it.quantity for it in material_items):
        purchase.status = Purchase.Status.RECEIVED
    else:
        purchase.status = Purchase.Status.PARTIAL
    purchase.save(update_fields=["status", "updated_at"])
    return purchase


@transaction.atomic
def cancel_purchase(*, purchase, reason=""):
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.items.filter(received_quantity__gt=0).exists():
        raise BusinessRuleError(
            "Goods have been received — record a stock adjustment / return instead of cancelling."
        )
    if purchase.amount_paid > 0:
        raise BusinessRuleError("Payments exist for this purchase — cancel those payments first.")
    purchase.status = Purchase.Status.CANCELLED
    purchase.balance_due = ZERO
    if reason:
        purchase.notes = f"{purchase.notes}\nCancelled: {reason}".strip()
    purchase.save(update_fields=["status", "balance_due", "notes", "updated_at"])
    return purchase


def _refresh_payment_status(purchase):
    paid = purchase.payments.filter(is_deleted=False).aggregate(v=Coalesce(Sum("amount"), Value(ZERO)))["v"]
    purchase.amount_paid = paid
    purchase.balance_due = (
        ZERO if purchase.status == Purchase.Status.CANCELLED else max(purchase.grand_total - paid, ZERO)
    )
    if paid <= 0:
        purchase.payment_status = Purchase.PaymentStatus.UNPAID
    elif paid >= purchase.grand_total:
        purchase.payment_status = Purchase.PaymentStatus.PAID
    else:
        purchase.payment_status = Purchase.PaymentStatus.PARTIAL
    purchase._skip_audit = True
    purchase.save(update_fields=["amount_paid", "balance_due", "payment_status", "updated_at"])


# ---------------------------------------------------------------------------
# Supplier payments
# ---------------------------------------------------------------------------
@transaction.atomic
def record_supplier_payment(
    *, supplier, amount, date, mode, purchase=None, reference_number="", notes="", paid_by=None
):
    amount = money(amount)
    if amount <= 0:
        raise BusinessRuleError("Amount must be more than zero.", field="amount")
    supplier = Supplier.objects.select_for_update().get(pk=supplier.pk)
    if purchase is not None:
        purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
        if purchase.supplier_id != supplier.pk:
            raise BusinessRuleError("This purchase belongs to another supplier.", field="purchase")
        if purchase.status == Purchase.Status.CANCELLED:
            raise BusinessRuleError("This purchase is cancelled.", field="purchase")
        if amount > purchase.balance_due:
            raise BusinessRuleError(
                f"Amount is more than the balance due on {purchase.po_number} (₹{purchase.balance_due}).",
                field="amount",
            )
    else:
        payable = supplier_payable(supplier)
        if amount > payable:
            raise BusinessRuleError(
                f"Amount is more than the total payable to {supplier.name} (₹{payable}).", field="amount"
            )
    payment = SupplierPayment.objects.create(
        voucher_number=next_document_number(DocumentSequence.DocType.SUPPLIER_PAYMENT, date),
        supplier=supplier,
        purchase=purchase,
        amount=amount,
        date=date,
        mode=mode,
        reference_number=reference_number,
        notes=notes,
        paid_by=paid_by,
    )
    if purchase is not None:
        _refresh_payment_status(purchase)
    return payment


@transaction.atomic
def cancel_supplier_payment(*, payment):
    payment.soft_delete()
    if payment.purchase_id:
        _refresh_payment_status(Purchase.objects.select_for_update().get(pk=payment.purchase_id))
