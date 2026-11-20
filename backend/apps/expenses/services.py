"""Expense business rules. Views stay thin; everything that changes data lives here."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.permissions import FINANCE, SITE_ENGINEER
from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.core.numbering import next_document_number
from apps.core.uploads import validate_document_upload

from .models import Expense

ZERO = Decimal("0.00")


def is_engineer(user):
    return getattr(user, "role_code", None) == SITE_ENGINEER


def is_finance(user):
    return getattr(user, "role_code", None) in FINANCE


def visible_expenses_for(user, qs):
    """Site engineers see expenses of their own projects plus the ones they entered."""
    if is_engineer(user):
        return qs.filter(Q(project__assigned_engineer=user) | Q(created_by=user))
    return qs


def validate_bill(f):
    validate_document_upload(f, field="bill_attachment")


def _check(user, data, expense=None):
    project = data.get("project", expense.project if expense else None)
    on = data.get("date", expense.date if expense else None)
    if on and on > date.today():
        raise BusinessRuleError("Expense date can't be in the future.", field="date")
    if project is not None:
        if project.status == project.Status.CANCELLED:
            raise BusinessRuleError("This project is cancelled.", field="project")
        if is_engineer(user) and project.assigned_engineer_id != user.id:
            raise BusinessRuleError("You can only add expenses to your own projects.", field="project")
    elif is_engineer(user):
        raise BusinessRuleError("Choose the project this expense belongs to.", field="project")
    if data.get("category") == Expense.Category.LABOUR and data.get("workers_count") == 0:
        raise BusinessRuleError("Workers must be at least 1.", field="workers_count")
    validate_bill(data.get("bill_attachment"))


@transaction.atomic
def create_expense(*, user, **data):
    _check(user, data)
    exp = Expense(**data)
    exp.voucher_number = next_document_number("EXPENSE", data["date"])
    exp.created_by = user
    if is_finance(user):  # entered by office → approved straight away
        exp.approved_by = user
        exp.approved_at = timezone.now()
    exp.save()
    return exp


@transaction.atomic
def update_expense(expense, *, user, **data):
    if is_engineer(user):
        if expense.created_by_id != user.id:
            raise BusinessRuleError("You can only edit expenses you entered.")
        if expense.is_approved:
            raise BusinessRuleError("This expense is already approved. Ask the office to change it.")
    _check(user, data, expense)
    if "bill_attachment" in data and data["bill_attachment"] is None:
        data.pop("bill_attachment")  # keep the old bill unless a new one is sent / remove_bill used
    for k, v in data.items():
        setattr(expense, k, v)
    expense.save()
    return expense


@transaction.atomic
def approve_expense(expense, *, user):
    if expense.is_approved:
        raise BusinessRuleError("Already approved.")
    expense.approved_by = user
    expense.approved_at = timezone.now()
    expense.save(update_fields=["approved_by", "approved_at", "updated_at"])
    log_action("UPDATE", expense, changes={"approved": [False, True]}, user=user)
    return expense


@transaction.atomic
def delete_expense(expense, *, user):
    expense.soft_delete(user)
    return expense


def summary(qs):
    """Totals for whatever list the user is looking at (same filters)."""
    by_cat = qs.values("category").annotate(total=Sum("amount"), count=Count("id")).order_by("-total")
    labels = dict(Expense.Category.choices)
    agg = qs.aggregate(
        total=Sum("amount"), count=Count("id"), pending=Count("id", filter=Q(approved_at=None))
    )
    return {
        "total": agg["total"] or ZERO,
        "count": agg["count"],
        "pending_approval": agg["pending"],
        "by_category": [
            {
                "category": r["category"],
                "label": labels.get(r["category"], r["category"]),
                "total": r["total"],
                "count": r["count"],
            }
            for r in by_cat
        ],
    }
