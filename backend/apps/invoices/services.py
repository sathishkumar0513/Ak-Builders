"""
GST invoice logic.

balance_due = grand_total − advance_adjusted − amount_paid   (never below zero — DB CHECK)
status      = UNPAID (nothing settled) / PARTIAL / PAID / CANCELLED

amount_paid counts only payments that are not cancelled and whose cheque has not bounced.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.audit import log_action
from apps.core.calculations import calculate_document
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog, CompanySettings, DocumentSequence, TermsTemplate
from apps.core.numbering import next_document_number
from apps.core.utils import ZERO, is_interstate, money
from apps.materials.models import StockMovement
from apps.materials.services import record_movement
from apps.payments import ledger

from .models import Invoice, InvoiceItem

S = Invoice.Status


def default_terms():
    t = TermsTemplate.objects.filter(applies_to=TermsTemplate.AppliesTo.INVOICE, is_default=True).first()
    return t.content if t else ""


# ---------------------------------------------------------------------------
# items & totals
# ---------------------------------------------------------------------------
def _prepare_items(items):
    prepared = []
    for i, raw in enumerate(items):
        item = dict(raw)
        material = item.get("material")
        if item.get("item_type", InvoiceItem.ItemType.MATERIAL) == InvoiceItem.ItemType.MATERIAL:
            if material is None:
                raise BusinessRuleError(f"Line {i + 1}: select a material.", field="items")
            item["description"] = item.get("description") or str(material)
            item["hsn_code"] = item.get("hsn_code") or material.hsn_code
            item["unit"] = item.get("unit") or material.unit
            if item.get("gst_rate") is None:
                item["gst_rate"] = material.gst_rate
        else:
            item["material"] = None
            if not item.get("description"):
                raise BusinessRuleError(f"Line {i + 1}: enter a description.", field="items")
        if Decimal(str(item["quantity"])) <= 0:
            raise BusinessRuleError(f"Line {i + 1}: quantity must be more than zero.", field="items")
        item.setdefault("discount_percent", ZERO)
        if item.get("gst_rate") is None:
            item["gst_rate"] = ZERO
        item["sort_order"] = i
        prepared.append(item)
    if not prepared:
        raise BusinessRuleError("Add at least one item.", field="items")
    return prepared


def _write_items_and_totals(inv, items):
    company = CompanySettings.load()
    inv.place_of_supply = inv.customer.state_code
    inv.is_interstate = is_interstate(company.state_code, inv.customer.state_code)
    try:
        totals = calculate_document(items, interstate=inv.is_interstate, header_discount=inv.header_discount)
    except ValueError as exc:
        raise BusinessRuleError(str(exc), field="header_discount")
    for field, value in totals.header_fields().items():
        setattr(inv, field, value)
    inv.save()
    inv.items.all().delete()
    InvoiceItem.objects.bulk_create(
        InvoiceItem(
            invoice=inv,
            item_type=item.get("item_type", InvoiceItem.ItemType.MATERIAL),
            material=item.get("material"),
            description=item["description"],
            hsn_code=item.get("hsn_code") or "",
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


def _snapshot_customer(inv):
    c = inv.customer
    inv.billing_name = c.name
    inv.billing_address = ", ".join(filter(None, [c.address, c.city, c.pincode]))
    inv.billing_gstin = c.gstin


def _stock_out(inv):
    for it in inv.items.filter(material__isnull=False).select_related("material"):
        record_movement(
            material=it.material,
            movement_type=StockMovement.MovementType.SALE_OUT,
            quantity=it.quantity,
            rate=it.material.purchase_price,
            date=inv.invoice_date,
            reference_type="Invoice",
            reference_id=inv.pk,
            note=f"Invoice {inv.number} · {inv.billing_name}",
        )


def _stock_back(inv, note):
    for mv in StockMovement.objects.filter(
        reference_type="Invoice", reference_id=inv.pk, movement_type=StockMovement.MovementType.SALE_OUT
    ):
        record_movement(
            material=mv.material,
            movement_type=StockMovement.MovementType.ADJUST_IN,
            quantity=mv.quantity,
            rate=mv.rate,
            date=date.today(),
            reference_type="Invoice",
            reference_id=inv.pk,
            note=note,
        )


# ---------------------------------------------------------------------------
# recompute
# ---------------------------------------------------------------------------
def recompute_invoice(inv):
    """Re-derive paid / balance / status from payments and advance adjustments (single source of truth)."""
    from apps.payments.models import AdvanceAdjustment, Payment

    paid = (
        Payment.objects.filter(invoice=inv)
        .exclude(cheque_status=Payment.ChequeStatus.BOUNCED)
        .aggregate(v=Coalesce(Sum("amount"), Value(ZERO)))["v"]
    )
    adjusted = AdvanceAdjustment.objects.filter(invoice=inv).aggregate(
        v=Coalesce(Sum("amount"), Value(ZERO))
    )["v"]
    inv.amount_paid = paid
    inv.advance_adjusted = adjusted
    if inv.status != S.CANCELLED:
        settled = paid + adjusted
        if settled > inv.grand_total:
            raise BusinessRuleError(
                f"Payments exceed the invoice total of ₹{inv.grand_total}.", field="amount"
            )
        inv.balance_due = inv.grand_total - settled
        inv.status = S.PAID if inv.balance_due == 0 else (S.PARTIAL if settled > 0 else S.UNPAID)
    inv._skip_audit = True
    inv.save(update_fields=["amount_paid", "advance_adjusted", "balance_due", "status", "updated_at"])
    if inv.payment_stage_id:
        from apps.projects.services import recompute_stage

        recompute_stage(inv.payment_stage)
    return inv


# ---------------------------------------------------------------------------
# create / update / cancel
# ---------------------------------------------------------------------------
@transaction.atomic
def create_invoice(*, data, items, auto_adjust_advance=True):
    from apps.payments.services import auto_adjust_advances

    items = _prepare_items(items)
    company = CompanySettings.load()
    inv = Invoice(**data)
    inv.invoice_date = inv.invoice_date or date.today()
    inv.due_date = inv.due_date or inv.invoice_date + timedelta(days=company.invoice_due_days)
    if inv.due_date < inv.invoice_date:
        raise BusinessRuleError("Due date cannot be before the invoice date.", field="due_date")
    if inv.project_id and inv.project.customer_id != inv.customer_id:
        raise BusinessRuleError("This project belongs to another customer.", field="project")
    if inv.payment_stage_id and inv.payment_stage.project_id != inv.project_id:
        raise BusinessRuleError("The payment stage does not belong to this project.", field="payment_stage")
    if inv.deduct_stock and inv.project_id:
        raise BusinessRuleError(
            "Project material is issued from the Projects page — don't deduct stock again here.",
            field="deduct_stock",
        )
    if not inv.terms_and_conditions:
        inv.terms_and_conditions = default_terms()
    _snapshot_customer(inv)
    inv.number = next_document_number(DocumentSequence.DocType.INVOICE, inv.invoice_date)
    inv.status = S.UNPAID
    inv.save()
    _write_items_and_totals(inv, items)
    inv.balance_due = inv.grand_total
    inv.save(update_fields=["balance_due"])
    ledger.post(
        customer=inv.customer,
        project=inv.project,
        date=inv.invoice_date,
        entry_type=ledger.E.INVOICE,
        debit=inv.grand_total,
        reference=inv,
        narration=ledger._invoice_narration(inv),
    )
    if inv.deduct_stock:
        _stock_out(inv)
    if auto_adjust_advance:
        auto_adjust_advances(invoice=inv)
    return recompute_invoice(inv)


@transaction.atomic
def update_invoice(*, invoice, data, items=None):
    inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status != S.UNPAID or inv.advance_adjusted or inv.amount_paid:
        raise BusinessRuleError(
            "Only an unpaid invoice with no advance adjusted can be edited. Cancel and re-issue instead."
        )
    if "customer" in data and data["customer"] != inv.customer:
        raise BusinessRuleError("The customer of an invoice cannot be changed. Cancel and re-issue instead.")
    if inv.deduct_stock and items is not None:
        _stock_back(inv, f"Invoice {inv.number} edited")
    for field, value in data.items():
        setattr(inv, field, value)
    if inv.due_date and inv.due_date < inv.invoice_date:
        raise BusinessRuleError("Due date cannot be before the invoice date.", field="due_date")
    _snapshot_customer(inv)
    from apps.quotations.services import _item_dicts  # same shape for invoice items

    _write_items_and_totals(inv, _prepare_items(items if items is not None else _item_dicts(inv)))
    if inv.deduct_stock and items is not None:
        _stock_out(inv)
    ledger.update_invoice_posting(inv)
    return recompute_invoice(inv)


@transaction.atomic
def cancel_invoice(*, invoice, reason):
    from apps.payments.models import AdvanceAdjustment, Payment
    from apps.payments.services import recompute_advance

    inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status == S.CANCELLED:
        raise BusinessRuleError("Invoice is already cancelled.")
    if Payment.objects.filter(invoice=inv).exists():
        raise BusinessRuleError("Payments are recorded against this invoice. Cancel those receipts first.")
    if not reason:
        raise BusinessRuleError("Enter a reason for cancelling.", field="reason")
    # release advance adjustments back to the advances
    for adj in AdvanceAdjustment.objects.filter(invoice=inv).select_related("advance"):
        advance = adj.advance
        adj.delete()
        recompute_advance(advance)
    inv.status = S.CANCELLED
    inv.cancelled_reason = reason[:255]
    inv.balance_due = ZERO
    inv.advance_adjusted = ZERO
    inv._skip_audit = True
    inv.save(update_fields=["status", "cancelled_reason", "balance_due", "advance_adjusted", "updated_at"])
    log_action(
        AuditLog.Action.STATUS, inv, changes={"status": ["ACTIVE", "CANCELLED"], "reason": [None, reason]}
    )
    ledger.reverse(
        reference=inv, date=date.today(), narration=f"Invoice {inv.number} cancelled: {reason}"[:255]
    )
    if inv.deduct_stock:
        _stock_back(inv, f"Invoice {inv.number} cancelled")
    if inv.payment_stage_id:
        from apps.projects.services import recompute_stage

        recompute_stage(inv.payment_stage)
    return inv


# ---------------------------------------------------------------------------
# builders: from quotation / from project stage
# ---------------------------------------------------------------------------
def items_from_quotation(quotation):
    from apps.quotations.services import _item_dicts

    return _item_dicts(quotation)


def stage_invoice_items(stage, gst_rate=Decimal("18"), sac="995411"):
    """
    One service line whose GST-inclusive total equals the stage amount
    (the stage amounts come from the GST-inclusive quotation total).
    """
    gst_rate = Decimal(str(gst_rate))
    taxable = money(stage.amount / (1 + gst_rate / 100))
    project = stage.project
    return [
        {
            "item_type": InvoiceItem.ItemType.SERVICE,
            "material": None,
            "description": (
                f"{stage.name} — {stage.percentage.normalize():f}% of contract for "
                f"{project.name} ({project.code})"
            ),
            "hsn_code": sac,
            "quantity": Decimal("1"),
            "unit": "ls",
            "rate": taxable,
            "discount_percent": ZERO,
            "gst_rate": gst_rate,
        }
    ]


def overdue_queryset(today=None):
    today = today or date.today()
    return Invoice.objects.filter(status__in=[S.UNPAID, S.PARTIAL], due_date__lt=today).select_related(
        "customer"
    )


def ageing_bucket(inv, today=None):
    days = ((today or date.today()) - inv.due_date).days if inv.due_date else 0
    if days <= 0:
        return "Not due"
    return (
        "1–30 days"
        if days <= 30
        else "31–60 days" if days <= 60 else "61–90 days" if days <= 90 else "90+ days"
    )


def outstanding_for_customer(customer):
    return Invoice.objects.filter(customer=customer).filter(~Q(status__in=[S.CANCELLED, S.PAID]))
