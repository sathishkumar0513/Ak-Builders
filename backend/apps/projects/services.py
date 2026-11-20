"""Project, payment-stage, site-material and progress logic."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce

from apps.core.exceptions import BusinessRuleError
from apps.core.models import DocumentSequence
from apps.core.numbering import next_document_number
from apps.core.utils import ZERO, money
from apps.materials.models import Material, StockMovement
from apps.materials.services import record_movement

from .models import PaymentStage, ProgressNote, ProgressPhoto, Project, ProjectMaterialIssue

PS = PaymentStage.Status


def _sum(qs, field="amount"):
    return qs.aggregate(v=Coalesce(Sum(field), Value(ZERO)))["v"]


# ---------------------------------------------------------------------------
# projects
# ---------------------------------------------------------------------------
@transaction.atomic
def create_project(*, data, stages=None):
    p = Project(**data)
    if p.quotation_id and p.quotation.customer_id != p.customer_id:
        raise BusinessRuleError("The quotation belongs to another customer.", field="quotation")
    p.code = next_document_number(DocumentSequence.DocType.PROJECT, p.start_date or date.today())
    p.save()
    if stages:
        set_stages(project=p, stages=stages)
    return p


@transaction.atomic
def update_project(*, project, data):
    p = Project.objects.select_for_update().get(pk=project.pk)
    if "customer" in data and data["customer"] != p.customer and (p.invoices.exists() or p.payments.exists()):
        raise BusinessRuleError(
            "Invoices or payments exist — the customer can't be changed.", field="customer"
        )
    old_value = p.contract_value
    for k, v in data.items():
        setattr(p, k, v)
    if p.status == Project.Status.COMPLETED and not p.actual_end_date:
        p.actual_end_date = date.today()
    if p.expected_end_date and p.start_date and p.expected_end_date < p.start_date:
        raise BusinessRuleError("Expected end date is before the start date.", field="expected_end_date")
    p.save()
    if p.contract_value != old_value and p.payment_stages.exists():
        _rescale_unbilled_stages(p)
    return p


def _rescale_unbilled_stages(p):
    """Contract value changed → recompute stage amounts from percentages (only if no stage is billed/paid)."""
    stages = list(p.payment_stages.all())
    locked = [s for s in stages if s.invoices.exclude(status="CANCELLED").exists() or s.amount_received > 0]
    if locked:
        return
    _apply_amounts(p, stages)
    for s in stages:
        s.save(update_fields=["amount"])


def _apply_amounts(p, stages):
    remaining = p.contract_value
    for i, s in enumerate(stages):
        s.amount = remaining if i == len(stages) - 1 else money(p.contract_value * s.percentage / 100)
        remaining -= s.amount


@transaction.atomic
def set_stages(*, project, stages):
    """
    Replace the stage plan. stages: [{"id"?, "name", "percentage", "due_date"?}] — must total 100%.
    Stages that are already invoiced or paid must be kept with the same percentage.
    """
    p = Project.objects.select_for_update().get(pk=project.pk)
    if p.contract_value <= 0:
        raise BusinessRuleError("Set the contract value first.", field="contract_value")
    total = sum((Decimal(str(s["percentage"])) for s in stages), Decimal("0"))
    if stages and total != Decimal("100"):
        raise BusinessRuleError(
            f"Stage percentages must add up to 100% (now {total.normalize():f}%).", field="stages"
        )
    existing = {s.id: s for s in p.payment_stages.all()}
    keep_ids = {s.get("id") for s in stages if s.get("id")}
    for sid, s in existing.items():
        busy = s.invoices.exclude(status="CANCELLED").exists() or s.amount_received > 0
        if sid not in keep_ids:
            if busy:
                raise BusinessRuleError(
                    f"Stage '{s.name}' is already invoiced or paid and cannot be removed.", field="stages"
                )
            s.delete()
    objs = []
    for i, data in enumerate(stages):
        s = existing.get(data.get("id")) or PaymentStage(project=p)
        new_pct = Decimal(str(data["percentage"]))
        if (
            s.pk
            and s.percentage != new_pct
            and (s.invoices.exclude(status="CANCELLED").exists() or s.amount_received > 0)
        ):
            raise BusinessRuleError(
                f"Stage '{s.name}' is already invoiced or paid — its percentage can't change.", field="stages"
            )
        s.name, s.percentage, s.sort_order = data["name"], new_pct, i
        s.due_date = data.get("due_date") or s.due_date
        objs.append(s)
    _apply_amounts(p, objs)
    for s in objs:
        s.save()
        recompute_stage(s)
    return objs


def recompute_stage(stage):
    """received = settled part of the stage's invoices + direct stage payments (not bounced)."""
    from apps.invoices.models import Invoice
    from apps.payments.models import Payment

    s = PaymentStage.objects.get(pk=stage.pk)
    invoices = Invoice.objects.filter(payment_stage=s).exclude(status=Invoice.Status.CANCELLED)
    via_invoice = sum((i.amount_paid + i.advance_adjusted for i in invoices), ZERO)
    direct = _sum(
        Payment.objects.filter(payment_stage=s, invoice__isnull=True).exclude(
            cheque_status=Payment.ChequeStatus.BOUNCED
        )
    )
    s.amount_received = via_invoice + direct
    if s.amount_received >= s.amount and s.amount > 0:
        s.status = PS.PAID
    elif s.amount_received > 0:
        s.status = PS.PARTIAL
    elif invoices.exists() or (s.due_date and s.due_date <= date.today()):
        s.status = PS.DUE
    else:
        s.status = PS.PENDING
    s.save(update_fields=["amount_received", "status", "updated_at"])
    return s


# ---------------------------------------------------------------------------
# site material
# ---------------------------------------------------------------------------
@transaction.atomic
def issue_material(
    *,
    project,
    material,
    quantity,
    issue_date=None,
    is_return=False,
    notes="",
    received_by_name="",
    vehicle_number="",
    issued_by=None,
):
    """Store → site (stock −) or site → store (stock +). Costed at the material's current purchase price."""
    if project.status in (Project.Status.COMPLETED, Project.Status.CANCELLED) and not is_return:
        raise BusinessRuleError(
            f"Project is {project.get_status_display().lower()} — material can't be issued."
        )
    qty = Decimal(str(quantity))
    if is_return:
        net = site_balance(project, material)
        if qty > net:
            raise BusinessRuleError(
                f"Only {net.normalize():f} {material.unit} of {material} is at this site.", field="quantity"
            )
    material = Material.objects.get(pk=material.pk)
    rate = material.purchase_price
    issue = ProjectMaterialIssue.objects.create(
        project=project,
        material=material,
        issue_date=issue_date or date.today(),
        quantity=qty,
        rate=rate,
        amount=money(qty * rate),
        is_return=is_return,
        notes=notes,
        received_by_name=received_by_name,
        vehicle_number=vehicle_number,
        issued_by=issued_by,
    )
    record_movement(
        material=material,
        movement_type=(
            StockMovement.MovementType.SITE_RETURN if is_return else StockMovement.MovementType.SITE_ISSUE
        ),
        quantity=qty,
        rate=rate,
        date=issue.issue_date,
        project=project,
        reference_type="ProjectMaterialIssue",
        reference_id=issue.pk,
        note=f"{project.code} · {notes}".strip(" ·"),
    )
    return issue


@transaction.atomic
def undo_issue(*, issue):
    """Cancel a wrong entry: the opposite stock movement is recorded, then the entry is soft-deleted."""
    record_movement(
        material=issue.material,
        movement_type=(
            StockMovement.MovementType.SITE_ISSUE
            if issue.is_return
            else StockMovement.MovementType.SITE_RETURN
        ),
        quantity=issue.quantity,
        rate=issue.rate,
        date=date.today(),
        project=issue.project,
        reference_type="ProjectMaterialIssue",
        reference_id=issue.pk,
        note=f"Correction: entry of {issue.issue_date:%d/%m/%Y} removed",
    )
    issue.soft_delete()


def site_balance(project, material):
    qs = ProjectMaterialIssue.objects.filter(project=project, material=material)
    return _sum(qs.filter(is_return=False), "quantity") - _sum(qs.filter(is_return=True), "quantity")


def site_material_summary(project):
    rows = {}
    for i in ProjectMaterialIssue.objects.filter(project=project).select_related("material"):
        r = rows.setdefault(
            i.material_id,
            {
                "material": i.material_id,
                "name": str(i.material),
                "unit": i.material.unit,
                "issued": ZERO,
                "returned": ZERO,
                "cost": ZERO,
            },
        )
        if i.is_return:
            r["returned"] += i.quantity
            r["cost"] -= i.amount
        else:
            r["issued"] += i.quantity
            r["cost"] += i.amount
    for r in rows.values():
        r["net"] = r["issued"] - r["returned"]
    return sorted(rows.values(), key=lambda r: r["name"])


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------
@transaction.atomic
def add_progress(*, project, note, on=None, progress_percent=None, workers_on_site=None, photos=()):
    n = ProgressNote.objects.create(
        project=project,
        date=on or date.today(),
        note=note,
        progress_percent=progress_percent,
        workers_on_site=workers_on_site,
    )
    for f in photos:
        ProgressPhoto.objects.create(note=n, image=f)
    if progress_percent is not None:
        project.progress_percent = progress_percent
        if project.status == Project.Status.PLANNED:
            project.status = Project.Status.IN_PROGRESS
        project.save(update_fields=["progress_percent", "status", "updated_at"])
    return n


# ---------------------------------------------------------------------------
# money summary
# ---------------------------------------------------------------------------
def project_summary(project):
    from apps.expenses.models import Expense
    from apps.invoices.models import Invoice
    from apps.payments.models import AdvancePayment, Payment

    issues = ProjectMaterialIssue.objects.filter(project=project)
    material_cost = _sum(issues.filter(is_return=False)) - _sum(issues.filter(is_return=True))
    direct_purchases = _sum(project.purchases.exclude(status="CANCELLED"), "taxable_amount")
    expenses = _sum(Expense.objects.filter(project=project))
    invoices = Invoice.objects.filter(project=project).exclude(status=Invoice.Status.CANCELLED)
    billed = _sum(invoices, "grand_total")
    payments = _sum(
        Payment.objects.filter(project=project).exclude(cheque_status=Payment.ChequeStatus.BOUNCED)
    )
    advances = AdvancePayment.objects.filter(project=project)
    advance_received = _sum(advances)
    refunded = sum((a.refunded_amount for a in advances), ZERO)
    received = payments + advance_received - refunded
    total_cost = material_cost + direct_purchases + expenses
    return {
        "contract_value": project.contract_value,
        "material_cost": material_cost,
        "direct_purchases": direct_purchases,
        "expenses": expenses,
        "total_cost": total_cost,
        "billed": billed,
        "received": received,
        "advance_unused": sum((a.balance for a in advances), ZERO),
        "outstanding": _sum(invoices, "balance_due"),
        "unbilled": max(project.contract_value - billed, ZERO),
        "profit_on_received": received - total_cost,
        "expected_profit": project.contract_value - total_cost,
    }


def visible_projects_for(user, qs):
    """Site engineers only see the projects assigned to them."""
    if getattr(user, "role_code", None) == "SITE_ENGINEER":
        return qs.filter(assigned_engineer=user)
    return qs
