"""
Quotation business logic.

Status flow (only the latest revision can change status):

    DRAFT ──send──▶ SENT ──approve──▶ APPROVED ──convert──▶ CONVERTED
      │               │  └─reject──▶ REJECTED
      │               └─(valid_until passed)──▶ EXPIRED
      └──approve / reject (customer replied before it was sent)

Only DRAFT quotations are edited in place. Any other quotation (except CONVERTED) is changed by
creating a revision: same number, revision + 1, status DRAFT. The old revision stays for history.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.audit import log_action
from apps.core.calculations import calculate_document
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog, CompanySettings, DocumentSequence, TermsTemplate
from apps.core.numbering import next_document_number
from apps.core.utils import ZERO, is_interstate, money

from .models import Quotation, QuotationItem

S = Quotation.Status


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def default_terms():
    t = TermsTemplate.objects.filter(applies_to=TermsTemplate.AppliesTo.QUOTATION, is_default=True).first()
    return t.content if t else ""


def _prepare_items(items):
    prepared = []
    for i, raw in enumerate(items):
        item = dict(raw)
        material = item.get("material")
        if item.get("item_type", QuotationItem.ItemType.MATERIAL) == QuotationItem.ItemType.MATERIAL:
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


def _write_items_and_totals(quotation, items):
    company = CompanySettings.load()
    quotation.place_of_supply = quotation.customer.state_code
    quotation.is_interstate = is_interstate(company.state_code, quotation.customer.state_code)
    try:
        totals = calculate_document(
            items, interstate=quotation.is_interstate, header_discount=quotation.header_discount
        )
    except ValueError as exc:
        raise BusinessRuleError(str(exc), field="header_discount")
    for field, value in totals.header_fields().items():
        setattr(quotation, field, value)
    quotation.save()
    quotation.items.all().delete()
    QuotationItem.objects.bulk_create(
        QuotationItem(
            quotation=quotation,
            item_type=item.get("item_type", QuotationItem.ItemType.MATERIAL),
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
    return totals


def _locked(quotation):
    return Quotation.objects.select_for_update().get(pk=quotation.pk)


def _require_latest(q):
    if not q.is_latest:
        raise BusinessRuleError(
            f"This is an old revision (Rev {q.revision}). Open the latest revision instead."
        )


def _set_status(q, new_status, **extra):
    old = q.status
    q.status = new_status
    for k, v in extra.items():
        setattr(q, k, v)
    q._skip_audit = True  # logged explicitly below with a clear action
    q.save()
    log_action(AuditLog.Action.STATUS, q, changes={"status": [old, new_status]})
    return q


# ---------------------------------------------------------------------------
# create / update / revise / duplicate
# ---------------------------------------------------------------------------
@transaction.atomic
def create_quotation(*, data, items):
    items = _prepare_items(items)
    company = CompanySettings.load()
    q = Quotation(**data)
    q.quotation_date = q.quotation_date or date.today()
    q.valid_until = q.valid_until or q.quotation_date + timedelta(days=company.quotation_validity_days)
    if q.valid_until < q.quotation_date:
        raise BusinessRuleError("Valid-until date cannot be before the quotation date.", field="valid_until")
    if not q.terms_and_conditions:
        q.terms_and_conditions = default_terms()
    if not q.site_address:
        q.site_address = q.customer.address
    q.number = next_document_number(DocumentSequence.DocType.QUOTATION, q.quotation_date)
    q.revision = 1
    q.status = S.DRAFT
    q.save()
    _write_items_and_totals(q, items)
    return q


@transaction.atomic
def update_quotation(*, quotation, data, items=None):
    q = _locked(quotation)
    _require_latest(q)
    if q.status != S.DRAFT:
        raise BusinessRuleError(
            f"A {q.get_status_display().lower()} quotation can't be edited. Create a revision instead."
        )
    for field, value in data.items():
        setattr(q, field, value)
    if q.valid_until < q.quotation_date:
        raise BusinessRuleError("Valid-until date cannot be before the quotation date.", field="valid_until")
    # recalculate even when only the header changed (discount / customer state affect totals)
    _write_items_and_totals(q, _prepare_items(items if items is not None else _item_dicts(q)))
    return q


def _item_dicts(q):
    return [
        {
            "item_type": i.item_type,
            "material": i.material,
            "description": i.description,
            "hsn_code": i.hsn_code,
            "quantity": i.quantity,
            "unit": i.unit,
            "rate": i.rate,
            "discount_percent": i.discount_percent,
            "gst_rate": i.gst_rate,
        }
        for i in q.items.select_related("material")
    ]


COPY_FIELDS = ["customer", "title", "site_address", "header_discount", "terms_and_conditions", "notes"]


@transaction.atomic
def revise_quotation(*, quotation):
    """New revision (DRAFT) with the same number; dates reset to today with a fresh validity period."""
    q = _locked(quotation)
    _require_latest(q)
    if q.status in (S.DRAFT, S.CONVERTED):
        raise BusinessRuleError(
            "Draft quotations are edited directly."
            if q.status == S.DRAFT
            else "This quotation is already converted to a project."
        )
    company = CompanySettings.load()
    today = date.today()
    new = Quotation(
        number=q.number,
        revision=q.revision + 1,
        previous_revision=q,
        is_latest=True,
        status=S.DRAFT,
        quotation_date=today,
        valid_until=today + timedelta(days=company.quotation_validity_days),
        **{f: getattr(q, f) for f in COPY_FIELDS},
    )
    q.is_latest = False
    q._skip_audit = True
    q.save(update_fields=["is_latest", "updated_at"])
    new.save()
    items = _item_dicts(q)
    for i, it in enumerate(items):
        it["sort_order"] = i
    _write_items_and_totals(new, items)
    log_action(AuditLog.Action.CREATE, new, changes={"revision_of": [None, f"{q.number} Rev {q.revision}"]})
    return new


@transaction.atomic
def duplicate_quotation(*, quotation, customer=None):
    """Copy as a brand-new quotation (new number), optionally for another customer."""
    data = {f: getattr(quotation, f) for f in COPY_FIELDS}
    if customer is not None:
        data["customer"] = customer
        data["site_address"] = customer.address
    data["title"] = quotation.title
    return create_quotation(data=data, items=_item_dicts(quotation))


# ---------------------------------------------------------------------------
# status changes
# ---------------------------------------------------------------------------
def expire_due_quotations(today=None):
    """SENT quotations past their validity become EXPIRED. Run daily (Celery beat) and before listing."""
    today = today or date.today()
    return Quotation.objects.filter(status=S.SENT, is_latest=True, valid_until__lt=today).update(
        status=S.EXPIRED
    )


@transaction.atomic
def mark_sent(*, quotation):
    q = _locked(quotation)
    _require_latest(q)
    if q.status == S.SENT:
        return q
    if q.status != S.DRAFT:
        raise BusinessRuleError(f"Only a draft can be marked as sent (this one is {q.get_status_display()}).")
    if q.valid_until < date.today():
        raise BusinessRuleError(
            "The validity date has passed. Update the valid-until date first.", field="valid_until"
        )
    return _set_status(q, S.SENT, sent_at=timezone.now())


@transaction.atomic
def approve(*, quotation):
    q = _locked(quotation)
    _require_latest(q)
    if q.status not in (S.DRAFT, S.SENT):
        raise BusinessRuleError(f"A {q.get_status_display().lower()} quotation can't be approved.")
    return _set_status(q, S.APPROVED, approved_at=timezone.now(), rejection_reason="")


@transaction.atomic
def reject(*, quotation, reason=""):
    q = _locked(quotation)
    _require_latest(q)
    if q.status not in (S.DRAFT, S.SENT, S.APPROVED):
        raise BusinessRuleError(f"A {q.get_status_display().lower()} quotation can't be rejected.")
    return _set_status(q, S.REJECTED, rejection_reason=reason[:255])


DEFAULT_STAGES = [
    ("Advance (on work order)", Decimal("30")),
    ("Mid-work", Decimal("40")),
    ("Completion & handover", Decimal("30")),
]


@transaction.atomic
def convert_to_project(
    *,
    quotation,
    name="",
    start_date=None,
    expected_end_date=None,
    assigned_engineer=None,
    project_type=None,
    stages=None,
):
    """
    APPROVED → CONVERTED. Creates a Project (contract value = grand total) and payment stages.
    stages: [{"name", "percentage"}] summing to 100, or None for the default 30 / 40 / 30.
    """
    from apps.projects.models import PaymentStage, Project

    q = _locked(quotation)
    _require_latest(q)
    if q.status == S.CONVERTED:
        raise BusinessRuleError("Already converted to a project.")
    if q.status != S.APPROVED:
        raise BusinessRuleError("Only an approved quotation can be converted to a project.")

    stage_list = (
        [(s["name"], Decimal(str(s["percentage"]))) for s in stages] if stages is not None else DEFAULT_STAGES
    )
    if stage_list and sum(p for _, p in stage_list) != Decimal("100"):
        raise BusinessRuleError("Payment stage percentages must add up to 100%.", field="stages")
    if any(p <= 0 for _, p in stage_list):
        raise BusinessRuleError("Each stage percentage must be more than zero.", field="stages")

    project = Project.objects.create(
        code=next_document_number(DocumentSequence.DocType.PROJECT, start_date or date.today()),
        name=name or q.title or f"{q.customer.name} – {q.number}",
        project_type=project_type or Project.ProjectType.RENOVATION,
        customer=q.customer,
        quotation=q,
        site_address=q.site_address or q.customer.address or "—",
        site_city=q.customer.city,
        site_pincode=q.customer.pincode,
        start_date=start_date,
        expected_end_date=expected_end_date,
        assigned_engineer=assigned_engineer,
        contract_value=q.grand_total,
        status=Project.Status.PLANNED,
    )
    remaining = q.grand_total
    for i, (stage_name, pct) in enumerate(stage_list):
        amount = remaining if i == len(stage_list) - 1 else money(q.grand_total * pct / 100)
        remaining -= amount
        PaymentStage.objects.create(
            project=project, name=stage_name, percentage=pct, amount=amount, sort_order=i
        )
    _set_status(q, S.CONVERTED)
    return project


def soft_delete_quotation(*, quotation):
    if quotation.status in (S.APPROVED, S.CONVERTED):
        raise BusinessRuleError(f"An {quotation.get_status_display().lower()} quotation can't be deleted.")
    if quotation.is_latest and quotation.previous_revision_id:
        # deleting the latest revision re-activates the previous one
        prev = quotation.previous_revision
        prev.is_latest = True
        prev._skip_audit = True
        prev.save(update_fields=["is_latest", "updated_at"])
    quotation.is_latest = False
    quotation.save(update_fields=["is_latest", "updated_at"])
    quotation.soft_delete()
