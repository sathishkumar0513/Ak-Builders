"""
Dashboard figures. What each role receives:

- everyone: active projects (engineers: only theirs), project status chart, low stock
- Sales and above: customers, pending quotations, quotations expiring this week
- Accountant / Admin / Super Admin: all money cards, monthly revenue, payment modes,
  top customers, overdue invoices, recent receipts, expenses awaiting approval
- Site engineer: "my projects" with progress
"""

from datetime import date, timedelta

from django.db.models import Count, F, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth

from apps.accounts.permissions import FINANCE, SALES_AND_ABOVE, SITE_ENGINEER, SUPER_ADMIN
from apps.core.utils import financial_year

from .services import ZERO, _months_between, _sum, fy_start, receipts_qs

ACTIVE = ("PLANNED", "IN_PROGRESS", "ON_HOLD")


def _month_start(d, back=0):
    y, m = d.year, d.month - back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _by_month(qs, date_field, value_field):
    return {
        r["m"]: r["v"] for r in qs.annotate(m=TruncMonth(date_field)).values("m").annotate(v=Sum(value_field))
    }


def dashboard(user):
    from apps.customers.models import Customer
    from apps.expenses.models import Expense
    from apps.invoices.models import Invoice
    from apps.materials.models import Material
    from apps.payments.models import Payment
    from apps.projects.models import Project
    from apps.projects.services import visible_projects_for
    from apps.quotations.models import Quotation

    role = getattr(user, "role_code", None)
    is_super = role == SUPER_ADMIN
    finance = is_super or role in FINANCE
    sales = is_super or role in SALES_AND_ABOVE
    engineer = role == SITE_ENGINEER
    today = date.today()
    fy_from = fy_start(today)
    month_from = today.replace(day=1)

    projects = visible_projects_for(user, Project.objects.all())
    low = Material.objects.filter(is_active=True, stock_quantity__lte=F("reorder_level"))
    status_labels = dict(Project.Status.choices)

    out = {
        "today": today,
        "financial_year": financial_year(today),
        "role": role,
        "cards": {
            "active_projects": projects.filter(status__in=ACTIVE).count(),
            "low_stock": low.count(),
        },
        "project_status": [
            {"status": r["status"], "label": status_labels.get(r["status"], r["status"]), "count": r["n"]}
            for r in projects.values("status").annotate(n=Count("id")).order_by("status")
        ],
        "low_stock": [
            {
                "id": m.id,
                "name": m.name,
                "unit": m.get_unit_display(),
                "stock": m.stock_quantity,
                "reorder_level": m.reorder_level,
            }
            for m in low.order_by(F("stock_quantity") - F("reorder_level"), "name")[:6]
        ],
    }

    if sales:
        q = Quotation.objects.filter(is_latest=True)
        out["cards"]["total_customers"] = Customer.objects.count()
        out["cards"]["pending_quotations"] = q.filter(status__in=["DRAFT", "SENT"]).count()
        out["expiring_quotations"] = [
            {
                "id": x.id,
                "number": x.number,
                "customer": x.customer.name,
                "valid_until": x.valid_until,
                "grand_total": x.grand_total,
            }
            for x in q.filter(
                status="SENT", valid_until__gte=today, valid_until__lte=today + timedelta(days=7)
            )
            .select_related("customer")
            .order_by("valid_until")[:6]
        ]

    if engineer:
        out["my_projects"] = [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "status": p.status,
                "status_display": p.get_status_display(),
                "progress": p.progress_percent,
                "site_city": p.site_city,
            }
            for p in projects.filter(status__in=ACTIVE).order_by("-id")[:8]
        ]
        out["cards"]["my_pending_expenses"] = Expense.objects.filter(
            created_by=user, approved_at__isnull=True
        ).count()

    if finance:
        open_inv = Invoice.objects.filter(status__in=["UNPAID", "PARTIAL"])
        overdue = open_inv.filter(due_date__lt=today)
        out["cards"].update(
            {
                "received_fy": _money_in(fy_from, today),
                "received_month": _money_in(month_from, today),
                "outstanding": _sum(open_inv, "balance_due"),
                "overdue": _sum(overdue, "balance_due"),
                "overdue_count": overdue.count(),
                "billed_fy": _sum(
                    Invoice.objects.exclude(status="CANCELLED").filter(invoice_date__gte=fy_from),
                    "grand_total",
                ),
                "expenses_month": _sum(Expense.objects.filter(date__gte=month_from)),
                "pending_expense_approvals": Expense.objects.filter(approved_at__isnull=True).count(),
            }
        )

        # 12 months: billed vs received
        start = _month_start(today, 11)
        inv = Invoice.objects.exclude(status="CANCELLED").filter(invoice_date__gte=start)
        billed = _by_month(inv, "invoice_date", "grand_total")
        pays, advs, refs = receipts_qs(start, today)
        p_m, a_m, r_m = (
            _by_month(pays, "date", "amount"),
            _by_month(advs, "date", "amount"),
            _by_month(refs, "date", "amount"),
        )
        exp_m = _by_month(Expense.objects.filter(date__gte=start), "date", "amount")
        out["monthly"] = [
            {
                "month": m.strftime("%b %y"),
                "billed": billed.get(m) or ZERO,
                "received": (p_m.get(m) or ZERO) + (a_m.get(m) or ZERO) - (r_m.get(m) or ZERO),
                "expenses": exp_m.get(m) or ZERO,
            }
            for m in _months_between(start, today)
        ]

        # payment modes this FY (payments + advances)
        pays, advs, _ = receipts_qs(fy_from, today)
        modes = {}
        for qs in (pays, advs):
            for r in qs.values("mode").annotate(v=Sum("amount")):
                modes[r["mode"]] = modes.get(r["mode"], ZERO) + r["v"]
        labels = dict(Payment._meta.get_field("mode").choices)
        out["payment_modes"] = [
            {"mode": k, "label": labels.get(k, k), "amount": v}
            for k, v in sorted(modes.items(), key=lambda kv: -kv[1])
        ]

        # top customers by billing this FY
        top = (
            Invoice.objects.exclude(status="CANCELLED")
            .filter(invoice_date__gte=fy_from)
            .values("customer_id", "customer__name")
            .annotate(billed=Sum("grand_total"), due=Coalesce(Sum("balance_due"), Value(ZERO)))
            .order_by("-billed")[:5]
        )
        out["top_customers"] = [
            {"id": r["customer_id"], "name": r["customer__name"], "billed": r["billed"], "due": r["due"]}
            for r in top
        ]
        out["overdue_invoices"] = [
            {
                "id": i.id,
                "number": i.number,
                "customer": i.customer.name,
                "phone": i.customer.phone,
                "due_date": i.due_date,
                "days": (today - i.due_date).days,
                "balance_due": i.balance_due,
            }
            for i in overdue.select_related("customer").order_by("due_date")[:6]
        ]
        recent = [
            {
                "kind": "payment",
                "id": x.id,
                "number": x.receipt_number,
                "customer": x.customer.name,
                "date": x.date,
                "amount": x.amount,
                "mode": x.get_mode_display(),
                "created": x.created_at,
            }
            for x in Payment.objects.select_related("customer").order_by("-created_at")[:6]
        ]
        from apps.payments.models import AdvancePayment

        recent += [
            {
                "kind": "advance",
                "id": x.id,
                "number": x.receipt_number,
                "customer": x.customer.name,
                "date": x.date,
                "amount": x.amount,
                "mode": x.get_mode_display(),
                "created": x.created_at,
            }
            for x in AdvancePayment.objects.select_related("customer").order_by("-created_at")[:6]
        ]
        recent.sort(key=lambda r: r["created"], reverse=True)
        for r in recent:
            r.pop("created")
        out["recent_receipts"] = recent[:6]
    return out


def _money_in(df, dt):
    pays, advs, refs = receipts_qs(df, dt)
    return _sum(pays) + _sum(advs) - _sum(refs)
