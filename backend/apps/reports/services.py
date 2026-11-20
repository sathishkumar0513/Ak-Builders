"""
Computed reports. Nothing here writes to the database.

Every report returns the same shape, so the React table, the Excel export and the PDF export
are all generic:

    {
      "key": "payments", "title": "Payments received", "subtitle": "01/04/2026 – 12/11/2026",
      "columns": [{"key": "date", "label": "Date", "type": "date"}, ...],
      "rows": [{...}, ...],
      "totals": {"amount": Decimal(...)} | None,      # shown as the last, bold row
      "summary": [{"label": "Total", "value": ..., "type": "money"}, ...],   # KPI tiles
    }

Column types: text, date, money, qty, number, percent.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth

from apps.core.exceptions import BusinessRuleError
from apps.core.models import CompanySettings, PaymentMode
from apps.core.utils import financial_year

ZERO = Decimal("0.00")
QZERO = Decimal("0.000")
BUCKETS = ["Not due", "1–30 days", "31–60 days", "61–90 days", "90+ days"]
IN_TYPES = ("PURCHASE_IN", "SITE_RETURN", "ADJUST_IN", "OPENING")
OUT_TYPES = ("SITE_ISSUE", "SALE_OUT", "ADJUST_OUT")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def fy_start(on=None):
    on = on or date.today()
    m = CompanySettings.load().financial_year_start_month
    return date(on.year if on.month >= m else on.year - 1, m, 1)


def _sum(qs, field="amount"):
    return qs.aggregate(v=Coalesce(Sum(field), Value(ZERO)))["v"]


def _d(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _period(p):
    return f"{_d(p['date_from'])} – {_d(p['date_to'])}"


def col(key, label, type="text"):  # noqa: A002 — mirrors the JSON field name
    return {"key": key, "label": label, "type": type}


def kpi(label, value, type="money"):  # noqa: A002
    return {"label": label, "value": value, "type": type}


def _totals(rows, keys):
    return {k: sum((r.get(k) or ZERO for r in rows), ZERO) for k in keys}


def _pct(part, whole):
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1")) if whole else Decimal("0.0")


def _mode_label(code):
    return dict(PaymentMode.choices).get(code, code)


def _months_between(start, end):
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


# ---------------------------------------------------------------------------
# money in (shared by dashboard and reports)
# ---------------------------------------------------------------------------
def receipts_qs(date_from, date_to):
    """Active payments (not bounced), advances and refunds in a date range."""
    from apps.payments.models import AdvancePayment, AdvanceRefund, Payment

    rng = {"date__gte": date_from, "date__lte": date_to}
    payments = Payment.objects.filter(**rng).exclude(cheque_status=Payment.ChequeStatus.BOUNCED)
    advances = AdvancePayment.objects.filter(**rng)
    refunds = AdvanceRefund.objects.filter(**rng)
    return payments, advances, refunds


def money_received(date_from, date_to):
    payments, advances, refunds = receipts_qs(date_from, date_to)
    return _sum(payments) + _sum(advances) - _sum(refunds)


# ---------------------------------------------------------------------------
# 1. Payments received
# ---------------------------------------------------------------------------
def report_payments(p, user):
    payments, advances, refunds = receipts_qs(p["date_from"], p["date_to"])
    if p.get("customer"):
        payments = payments.filter(customer_id=p["customer"])
        advances = advances.filter(customer_id=p["customer"])
        refunds = refunds.filter(advance__customer_id=p["customer"])
    if p.get("mode"):
        payments, advances, refunds = (q.filter(mode=p["mode"]) for q in (payments, advances, refunds))

    rows = []
    for x in payments.select_related("customer", "invoice", "project"):
        rows.append(
            {
                "date": x.date,
                "number": x.receipt_number,
                "type": "Payment",
                "customer": x.customer.name,
                "against": x.invoice.number if x.invoice_id else (x.project.code if x.project_id else ""),
                "mode": x.get_mode_display(),
                "reference": x.reference_number or x.cheque_number,
                "amount": x.amount,
            }
        )
    for x in advances.select_related("customer", "project"):
        rows.append(
            {
                "date": x.date,
                "number": x.receipt_number,
                "type": "Advance",
                "customer": x.customer.name,
                "against": x.project.code if x.project_id else "",
                "mode": x.get_mode_display(),
                "reference": x.reference_number or x.cheque_number,
                "amount": x.amount,
            }
        )
    for x in refunds.select_related("advance__customer"):
        rows.append(
            {
                "date": x.date,
                "number": x.refund_number,
                "type": "Refund",
                "customer": x.advance.customer.name,
                "against": x.advance.receipt_number,
                "mode": x.get_mode_display(),
                "reference": x.reference_number,
                "amount": -x.amount,
            }
        )
    rows.sort(key=lambda r: (r["date"], r["number"]))

    by_mode = defaultdict(lambda: ZERO)
    for r in rows:
        by_mode[r["mode"]] += r["amount"]
    total = sum((r["amount"] for r in rows), ZERO)
    summary = [kpi("Net received", total), kpi("Receipts", len(rows), "number")]
    summary += [kpi(m, v) for m, v in sorted(by_mode.items(), key=lambda kv: -kv[1])]
    return {
        "title": "Payments received",
        "subtitle": _period(p) + " · bounced cheques excluded, refunds shown as minus",
        "columns": [
            col("date", "Date", "date"),
            col("number", "Receipt no."),
            col("type", "Type"),
            col("customer", "Customer"),
            col("against", "Against"),
            col("mode", "Mode"),
            col("reference", "Reference"),
            col("amount", "Amount", "money"),
        ],
        "rows": rows,
        "totals": {"amount": total},
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# 2. Outstanding & ageing (per invoice)
# ---------------------------------------------------------------------------
def report_outstanding(p, user):
    from apps.invoices.models import Invoice
    from apps.invoices.services import ageing_bucket

    today = p["date_to"] if p["date_to"] < date.today() else date.today()
    qs = (
        Invoice.objects.filter(status__in=[Invoice.Status.UNPAID, Invoice.Status.PARTIAL])
        .select_related("customer", "project")
        .order_by("due_date", "invoice_date", "id")
    )
    if p.get("customer"):
        qs = qs.filter(customer_id=p["customer"])
    rows, buckets = [], {b: ZERO for b in BUCKETS}
    for inv in qs:
        bucket = ageing_bucket(inv, today)
        days = max((today - inv.due_date).days, 0) if inv.due_date else 0
        buckets[bucket] += inv.balance_due
        rows.append(
            {
                "number": inv.number,
                "invoice_date": inv.invoice_date,
                "due_date": inv.due_date,
                "customer": inv.customer.name,
                "phone": inv.customer.phone,
                "project": inv.project.code if inv.project_id else "",
                "grand_total": inv.grand_total,
                "received": inv.amount_paid + inv.advance_adjusted,
                "balance_due": inv.balance_due,
                "days_overdue": days,
                "bucket": bucket,
            }
        )
    totals = _totals(rows, ["grand_total", "received", "balance_due"])
    return {
        "title": "Outstanding & ageing",
        "subtitle": f"Unpaid invoices as on {_d(today)}",
        "columns": [
            col("number", "Invoice"),
            col("invoice_date", "Date", "date"),
            col("due_date", "Due", "date"),
            col("customer", "Customer"),
            col("phone", "Phone"),
            col("project", "Project"),
            col("grand_total", "Invoice total", "money"),
            col("received", "Received", "money"),
            col("balance_due", "Balance", "money"),
            col("days_overdue", "Days overdue", "number"),
            col("bucket", "Ageing"),
        ],
        "rows": rows,
        "totals": totals,
        "summary": [kpi("Total outstanding", totals["balance_due"])]
        + [kpi(b, v) for b, v in buckets.items()],
    }


# ---------------------------------------------------------------------------
# 3. Customer-wise outstanding
# ---------------------------------------------------------------------------
def report_customer_outstanding(p, user):
    from apps.customers.models import Customer
    from apps.invoices.models import Invoice
    from apps.payments.models import AdvancePayment, CustomerLedgerEntry

    inv = Invoice.objects.exclude(status=Invoice.Status.CANCELLED)
    billed = dict(inv.values_list("customer").annotate(v=Sum("grand_total")))
    due = dict(inv.values_list("customer").annotate(v=Sum("balance_due")))
    ledger = {
        r["customer"]: r
        for r in CustomerLedgerEntry.objects.values("customer").annotate(
            d=Coalesce(Sum("debit"), Value(ZERO)), c=Coalesce(Sum("credit"), Value(ZERO))
        )
    }
    adv = defaultdict(lambda: ZERO)
    for a in AdvancePayment.objects.exclude(status=AdvancePayment.Status.REFUNDED):
        adv[a.customer_id] += a.balance
    overdue = dict(
        inv.filter(status__in=[Invoice.Status.UNPAID, Invoice.Status.PARTIAL], due_date__lt=date.today())
        .values_list("customer")
        .annotate(v=Sum("balance_due"))
    )
    rows = []
    for c in Customer.objects.order_by("name"):
        led = ledger.get(c.id)
        if not led and not billed.get(c.id):
            continue
        balance = (led["d"] - led["c"]) if led else ZERO
        rows.append(
            {
                "customer": c.name,
                "phone": c.phone,
                "city": c.city,
                "billed": billed.get(c.id) or ZERO,
                "received": (led["c"] if led else ZERO),
                "advance_balance": adv[c.id],
                "invoice_due": due.get(c.id) or ZERO,
                "overdue": overdue.get(c.id) or ZERO,
                "balance": balance,
            }
        )
    if p.get("only_due"):
        rows = [r for r in rows if r["invoice_due"] > 0]
    rows.sort(key=lambda r: -r["invoice_due"])
    totals = _totals(rows, ["billed", "received", "advance_balance", "invoice_due", "overdue", "balance"])
    return {
        "title": "Customer-wise outstanding",
        "subtitle": f"As on {_d(date.today())} · Ledger balance: + customer owes, − customer has credit",
        "columns": [
            col("customer", "Customer"),
            col("phone", "Phone"),
            col("city", "City"),
            col("billed", "Billed", "money"),
            col("received", "Received", "money"),
            col("advance_balance", "Unused advance", "money"),
            col("invoice_due", "Invoices due", "money"),
            col("overdue", "Overdue", "money"),
            col("balance", "Ledger balance", "money"),
        ],
        "rows": rows,
        "totals": totals,
        "summary": [
            kpi("Invoices due", totals["invoice_due"]),
            kpi("Overdue", totals["overdue"]),
            kpi("Unused advances", totals["advance_balance"]),
            kpi("Customers with dues", sum(1 for r in rows if r["invoice_due"] > 0), "number"),
        ],
    }


# ---------------------------------------------------------------------------
# 4. Customer ledger
# ---------------------------------------------------------------------------
def report_ledger(p, user):
    from apps.customers.models import Customer
    from apps.payments.ledger import statement

    if not p.get("customer"):
        raise BusinessRuleError("Choose a customer.", field="customer")
    customer = Customer.objects.filter(pk=p["customer"]).first()
    if not customer:
        raise BusinessRuleError("Customer not found.", field="customer")
    st = statement(customer, p["date_from"], p["date_to"])
    rows = [
        {
            "date": None,
            "particulars": "Opening balance",
            "reference": "",
            "project": "",
            "debit": None,
            "credit": None,
            "balance": st["opening_balance"],
            "_bold": True,
        }
    ]
    for r in st["rows"]:
        rows.append(
            {
                "date": r["date"],
                "particulars": r["narration"] or r["entry_type_display"],
                "reference": r["reference_number"],
                "project": r["project"] or "",
                "debit": r["debit"] or None,
                "credit": r["credit"] or None,
                "balance": r["balance"],
            }
        )
    closing = rows[-1]["balance"]
    return {
        "title": f"Customer ledger — {customer.name}",
        "subtitle": f"{customer.phone} · {customer.city} · {_period(p)} · balance + = Dr (owes), − = Cr",
        "columns": [
            col("date", "Date", "date"),
            col("particulars", "Particulars"),
            col("reference", "Ref."),
            col("project", "Project"),
            col("debit", "Debit", "money"),
            col("credit", "Credit", "money"),
            col("balance", "Balance", "money"),
        ],
        "rows": rows,
        "totals": {"debit": st["total_debit"], "credit": st["total_credit"], "balance": closing},
        "summary": [
            kpi("Opening", st["opening_balance"]),
            kpi("Debit", st["total_debit"]),
            kpi("Credit", st["total_credit"]),
            kpi("Closing", closing),
        ],
    }


# ---------------------------------------------------------------------------
# 5. Stock summary
# ---------------------------------------------------------------------------
def report_stock(p, user):
    from apps.materials.models import Material, StockMovement

    df, dt = p["date_from"], p["date_to"]
    mats = Material.objects.select_related("category").order_by("category__name", "name")
    if p.get("category"):
        mats = mats.filter(category_id=p["category"])
    if p.get("low_only"):
        mats = mats.filter(stock_quantity__lte=F("reorder_level"))

    moves = StockMovement.objects.filter(date__lte=dt)
    before = {
        r["material"]: r
        for r in moves.filter(date__lt=df)
        .values("material")
        .annotate(
            i=Coalesce(Sum("quantity", filter=Q(movement_type__in=IN_TYPES)), Value(QZERO)),
            o=Coalesce(Sum("quantity", filter=Q(movement_type__in=OUT_TYPES)), Value(QZERO)),
        )
    }
    during = {
        r["material"]: r
        for r in moves.filter(date__gte=df)
        .values("material")
        .annotate(
            i=Coalesce(Sum("quantity", filter=Q(movement_type__in=IN_TYPES)), Value(QZERO)),
            o=Coalesce(Sum("quantity", filter=Q(movement_type__in=OUT_TYPES)), Value(QZERO)),
        )
    }
    show_cost = p.get("_can_see_cost", True)
    rows = []
    for m in mats:
        b, d = before.get(m.id), during.get(m.id)
        opening = (b["i"] - b["o"]) if b else QZERO
        qin, qout = (d["i"], d["o"]) if d else (QZERO, QZERO)
        closing = opening + qin - qout
        row = {
            "material": f"{m.name}{' · ' + m.brand if m.brand else ''}",
            "category": m.category.name,
            "unit": m.get_unit_display(),
            "opening": opening,
            "in": qin,
            "out": qout,
            "closing": closing,
            "current": m.stock_quantity,
            "reorder": m.reorder_level,
            "status": "Low" if m.stock_quantity <= m.reorder_level else "OK",
        }
        if show_cost:
            row["rate"] = m.purchase_price
            row["value"] = (closing * m.purchase_price).quantize(Decimal("0.01"))
        rows.append(row)
    columns = [
        col("material", "Material"),
        col("category", "Category"),
        col("unit", "Unit"),
        col("opening", "Opening", "qty"),
        col("in", "In", "qty"),
        col("out", "Out", "qty"),
        col("closing", "Closing", "qty"),
        col("reorder", "Reorder level", "qty"),
        col("status", "Stock"),
    ]
    summary = [
        kpi("Materials", len(rows), "number"),
        kpi("Low stock now", sum(1 for r in rows if r["status"] == "Low"), "number"),
    ]
    totals = None
    if show_cost:
        columns += [col("rate", "Cost rate", "money"), col("value", "Closing value", "money")]
        totals = _totals(rows, ["value"])
        summary.insert(0, kpi("Closing stock value", totals["value"]))
    return {
        "title": "Stock summary",
        "subtitle": _period(p) + " · In = purchases, site returns, + adjustments · Out = site issues, "
        "sales, − adjustments",
        "columns": columns,
        "rows": rows,
        "totals": totals,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# 6. Material purchases
# ---------------------------------------------------------------------------
def report_purchases(p, user):
    from apps.suppliers.models import Purchase, PurchaseItem

    items = PurchaseItem.objects.filter(
        purchase__purchase_date__gte=p["date_from"], purchase__purchase_date__lte=p["date_to"]
    ).exclude(purchase__status=Purchase.Status.CANCELLED)
    if p.get("supplier"):
        items = items.filter(purchase__supplier_id=p["supplier"])
    if p.get("material"):
        items = items.filter(material_id=p["material"])
    gst = F("cgst_amount") + F("sgst_amount") + F("igst_amount")
    group = p.get("group") or "material"

    if group == "supplier":
        data = (
            items.values("purchase__supplier__name")
            .annotate(
                bills=Count("purchase", distinct=True),
                taxable=Sum("taxable_amount"),
                gst=Sum(gst),
                total=Sum("line_total"),
            )
            .order_by("-total")
        )
        rows = [
            {
                "supplier": r["purchase__supplier__name"],
                "bills": r["bills"],
                "taxable": r["taxable"],
                "gst": r["gst"],
                "total": r["total"],
            }
            for r in data
        ]
        columns = [
            col("supplier", "Supplier"),
            col("bills", "Bills", "number"),
            col("taxable", "Taxable", "money"),
            col("gst", "GST", "money"),
            col("total", "Total", "money"),
        ]
    elif group == "bill":
        rows = [
            {
                "date": i.purchase.purchase_date,
                "po": i.purchase.po_number,
                "bill": i.purchase.supplier_invoice_number,
                "supplier": i.purchase.supplier.name,
                "item": i.description,
                "qty": i.quantity,
                "unit": i.get_unit_display(),
                "rate": i.rate,
                "taxable": i.taxable_amount,
                "gst": i.cgst_amount + i.sgst_amount + i.igst_amount,
                "total": i.line_total,
            }
            for i in items.select_related("purchase__supplier").order_by("purchase__purchase_date", "id")
        ]
        columns = [
            col("date", "Date", "date"),
            col("po", "PO no."),
            col("bill", "Supplier bill"),
            col("supplier", "Supplier"),
            col("item", "Item"),
            col("qty", "Qty", "qty"),
            col("unit", "Unit"),
            col("rate", "Rate", "money"),
            col("taxable", "Taxable", "money"),
            col("gst", "GST", "money"),
            col("total", "Total", "money"),
        ]
    else:
        data = (
            items.values("description", "unit", "material_id")
            .annotate(
                qty=Sum("quantity"),
                taxable=Sum("taxable_amount"),
                gst=Sum(gst),
                total=Sum("line_total"),
                suppliers=Count("purchase__supplier", distinct=True),
            )
            .order_by("-total")
        )
        units = dict(PurchaseItem._meta.get_field("unit").choices)
        rows = []
        for r in data:
            avg = (r["taxable"] / r["qty"]).quantize(Decimal("0.01")) if r["qty"] else ZERO
            rows.append(
                {
                    "item": r["description"],
                    "unit": units.get(r["unit"], r["unit"]),
                    "qty": r["qty"],
                    "avg_rate": avg,
                    "suppliers": r["suppliers"],
                    "taxable": r["taxable"],
                    "gst": r["gst"],
                    "total": r["total"],
                }
            )
        columns = [
            col("item", "Material / item"),
            col("unit", "Unit"),
            col("qty", "Qty", "qty"),
            col("avg_rate", "Avg. rate (excl. GST)", "money"),
            col("suppliers", "Suppliers", "number"),
            col("taxable", "Taxable", "money"),
            col("gst", "GST", "money"),
            col("total", "Total", "money"),
        ]
    totals = _totals(rows, ["taxable", "gst", "total"])
    return {
        "title": "Material purchases",
        "subtitle": _period(p)
        + " · by "
        + {"supplier": "supplier", "bill": "bill line"}.get(group, "material"),
        "columns": columns,
        "rows": rows,
        "totals": totals,
        "summary": [
            kpi("Purchases (incl. GST)", totals["total"]),
            kpi("Taxable", totals["taxable"]),
            kpi("Input GST", totals["gst"]),
        ],
    }


# ---------------------------------------------------------------------------
# 7. Quotation conversion
# ---------------------------------------------------------------------------
def report_quotations(p, user):
    from apps.quotations.models import Quotation

    S = Quotation.Status
    qs = Quotation.objects.filter(
        is_latest=True, quotation_date__gte=p["date_from"], quotation_date__lte=p["date_to"]
    )
    won = [S.APPROVED, S.CONVERTED]
    decided = won + [S.REJECTED, S.EXPIRED]
    rows = []
    data = {
        r["m"]: r
        for r in qs.annotate(m=TruncMonth("quotation_date"))
        .values("m")
        .annotate(
            created=Count("id"),
            won=Count("id", filter=Q(status__in=won)),
            rejected=Count("id", filter=Q(status=S.REJECTED)),
            expired=Count("id", filter=Q(status=S.EXPIRED)),
            open=Count("id", filter=Q(status__in=[S.DRAFT, S.SENT])),
            quoted=Coalesce(Sum("grand_total"), Value(ZERO)),
            won_value=Coalesce(Sum("grand_total", filter=Q(status__in=won)), Value(ZERO)),
        )
    }
    for m in _months_between(p["date_from"], p["date_to"]):
        r = data.get(m)
        if not r:
            continue
        closed = r["won"] + r["rejected"] + r["expired"]
        rows.append(
            {
                "month": m.strftime("%b %Y"),
                "created": r["created"],
                "won": r["won"],
                "rejected": r["rejected"],
                "expired": r["expired"],
                "open": r["open"],
                "rate": _pct(r["won"], closed),
                "quoted": r["quoted"],
                "won_value": r["won_value"],
            }
        )
    agg = qs.aggregate(
        total=Count("id"),
        won=Count("id", filter=Q(status__in=won)),
        decided=Count("id", filter=Q(status__in=decided)),
        quoted=Coalesce(Sum("grand_total"), Value(ZERO)),
        won_value=Coalesce(Sum("grand_total", filter=Q(status__in=won)), Value(ZERO)),
    )
    totals = {k: sum((r[k] for r in rows), 0) for k in ("created", "won", "rejected", "expired", "open")}
    totals.update(
        {"rate": _pct(agg["won"], agg["decided"]), "quoted": agg["quoted"], "won_value": agg["won_value"]}
    )
    return {
        "title": "Quotation conversion",
        "subtitle": _period(p) + " · latest revision of each quotation · rate = won ÷ (won + rejected + "
        "expired)",
        "columns": [
            col("month", "Month"),
            col("created", "Quotations", "number"),
            col("won", "Won", "number"),
            col("rejected", "Rejected", "number"),
            col("expired", "Expired", "number"),
            col("open", "Still open", "number"),
            col("rate", "Conversion %", "percent"),
            col("quoted", "Value quoted", "money"),
            col("won_value", "Value won", "money"),
        ],
        "rows": rows,
        "totals": totals,
        "summary": [
            kpi("Conversion rate", totals["rate"], "percent"),
            kpi("Quotations", agg["total"], "number"),
            kpi("Won", agg["won"], "number"),
            kpi("Value won", agg["won_value"]),
        ],
    }


# ---------------------------------------------------------------------------
# 8. Project profit / loss
# ---------------------------------------------------------------------------
def report_project_pl(p, user):
    from apps.projects.models import Project
    from apps.projects.services import project_summary

    qs = Project.objects.select_related("customer").order_by("-id")
    if p.get("status"):
        qs = qs.filter(status=p["status"])
    else:
        qs = qs.exclude(status=Project.Status.CANCELLED)
    if p.get("customer"):
        qs = qs.filter(customer_id=p["customer"])
    rows = []
    for pr in qs:
        s = project_summary(pr)
        profit = s["received"] - s["total_cost"]
        rows.append(
            {
                "code": pr.code,
                "name": pr.name,
                "customer": pr.customer.name,
                "status": pr.get_status_display(),
                "contract": s["contract_value"],
                "billed": s["billed"],
                "received": s["received"],
                "material": s["material_cost"] + s["direct_purchases"],
                "expenses": s["expenses"],
                "cost": s["total_cost"],
                "profit": profit,
                "expected": s["expected_profit"],
                "margin": _pct(s["expected_profit"], s["contract_value"]),
            }
        )
    totals = _totals(
        rows, ["contract", "billed", "received", "material", "expenses", "cost", "profit", "expected"]
    )
    totals["margin"] = _pct(totals["expected"], totals["contract"])
    return {
        "title": "Project profit / loss",
        "subtitle": "Lifetime figures per project · Cash profit = received − cost so far · "
        "Expected = contract − cost so far",
        "columns": [
            col("code", "Project"),
            col("name", "Name"),
            col("customer", "Customer"),
            col("status", "Status"),
            col("contract", "Contract", "money"),
            col("billed", "Billed", "money"),
            col("received", "Received", "money"),
            col("material", "Material", "money"),
            col("expenses", "Expenses", "money"),
            col("cost", "Total cost", "money"),
            col("profit", "Cash profit", "money"),
            col("expected", "Expected profit", "money"),
            col("margin", "Margin %", "percent"),
        ],
        "rows": rows,
        "totals": totals,
        "summary": [
            kpi("Contract value", totals["contract"]),
            kpi("Cost so far", totals["cost"]),
            kpi("Cash profit", totals["profit"]),
            kpi("Expected margin", totals["margin"], "percent"),
        ],
    }


# ---------------------------------------------------------------------------
# 9. Expenses
# ---------------------------------------------------------------------------
def report_expenses(p, user):
    from apps.expenses.models import Expense

    qs = Expense.objects.filter(date__gte=p["date_from"], date__lte=p["date_to"])
    if p.get("project"):
        qs = qs.filter(project_id=p["project"])
    if p.get("category"):
        qs = qs.filter(category=p["category"])
    group = p.get("group") or "category"
    labels = dict(Expense.Category.choices)
    if group == "project":
        data = qs.values("project__code", "project__name").annotate(n=Count("id"), total=Sum("amount"))
        rows = [
            {
                "project": r["project__code"] or "Office / overhead",
                "name": r["project__name"] or "",
                "count": r["n"],
                "total": r["total"],
            }
            for r in data.order_by("-total")
        ]
        columns = [
            col("project", "Project"),
            col("name", "Name"),
            col("count", "Entries", "number"),
            col("total", "Amount", "money"),
        ]
    elif group == "detail":
        rows = [
            {
                "date": e.date,
                "voucher": e.voucher_number,
                "category": e.get_category_display(),
                "project": e.project.code if e.project_id else "Office",
                "paid_to": e.paid_to,
                "description": e.description,
                "mode": e.get_mode_display(),
                "approved": "Yes" if e.is_approved else "Pending",
                "total": e.amount,
            }
            for e in qs.select_related("project").order_by("date", "id")
        ]
        columns = [
            col("date", "Date", "date"),
            col("voucher", "Voucher"),
            col("category", "Category"),
            col("project", "Project"),
            col("paid_to", "Paid to"),
            col("description", "Description"),
            col("mode", "Mode"),
            col("approved", "Approved"),
            col("total", "Amount", "money"),
        ]
    else:
        data = qs.values("category").annotate(n=Count("id"), total=Sum("amount")).order_by("-total")
        grand = _sum(qs)
        rows = [
            {
                "category": labels.get(r["category"], r["category"]),
                "count": r["n"],
                "total": r["total"],
                "share": _pct(r["total"], grand),
            }
            for r in data
        ]
        columns = [
            col("category", "Category"),
            col("count", "Entries", "number"),
            col("total", "Amount", "money"),
            col("share", "Share %", "percent"),
        ]
    total = _sum(qs)
    return {
        "title": "Expenses",
        "subtitle": _period(p) + " · by " + group,
        "columns": columns,
        "rows": rows,
        "totals": {"total": total},
        "summary": [
            kpi("Total expenses", total),
            kpi("Project expenses", _sum(qs.filter(project__isnull=False))),
            kpi("Office / overhead", _sum(qs.filter(project__isnull=True))),
            kpi("Awaiting approval", qs.filter(approved_at__isnull=True).count(), "number"),
        ],
    }


# ---------------------------------------------------------------------------
# 10. Sales register (GST)
# ---------------------------------------------------------------------------
def report_sales_register(p, user):
    from apps.invoices.models import Invoice

    qs = (
        Invoice.objects.filter(invoice_date__gte=p["date_from"], invoice_date__lte=p["date_to"])
        .exclude(status=Invoice.Status.CANCELLED)
        .select_related("customer")
        .order_by("invoice_date", "number")
    )
    rows = [
        {
            "date": i.invoice_date,
            "number": i.number,
            "customer": i.billing_name,
            "gstin": i.billing_gstin or "Unregistered",
            "pos": i.place_of_supply,
            "taxable": i.taxable_amount,
            "cgst": i.cgst_amount,
            "sgst": i.sgst_amount,
            "igst": i.igst_amount,
            "round_off": i.round_off,
            "total": i.grand_total,
        }
        for i in qs
    ]
    totals = _totals(rows, ["taxable", "cgst", "sgst", "igst", "round_off", "total"])
    return {
        "title": "Sales register (GST)",
        "subtitle": _period(p) + " · cancelled invoices excluded · use for GSTR-1",
        "columns": [
            col("date", "Date", "date"),
            col("number", "Invoice"),
            col("customer", "Billed to"),
            col("gstin", "GSTIN"),
            col("pos", "POS"),
            col("taxable", "Taxable", "money"),
            col("cgst", "CGST", "money"),
            col("sgst", "SGST", "money"),
            col("igst", "IGST", "money"),
            col("round_off", "Round off", "money"),
            col("total", "Invoice value", "money"),
        ],
        "rows": rows,
        "totals": totals,
        "summary": [
            kpi("Taxable value", totals["taxable"]),
            kpi("Output GST", totals["cgst"] + totals["sgst"] + totals["igst"]),
            kpi("Invoice value", totals["total"]),
            kpi("Invoices", len(rows), "number"),
        ],
    }


# ---------------------------------------------------------------------------
# registry — the React report picker is built from this list
# ---------------------------------------------------------------------------
REPORTS = {
    "payments": {
        "fn": report_payments,
        "title": "Payments received",
        "group": "Sales & collections",
        "description": "Payments, advances and refunds by date and mode.",
        "filters": ["dates", "customer", "mode"],
    },
    "outstanding": {
        "fn": report_outstanding,
        "title": "Outstanding & ageing",
        "group": "Sales & collections",
        "description": "Every unpaid invoice with days overdue and ageing bucket.",
        "filters": ["as_on", "customer"],
    },
    "customer-outstanding": {
        "fn": report_customer_outstanding,
        "title": "Customer-wise outstanding",
        "group": "Sales & collections",
        "description": "Billed, received, unused advance and dues per customer.",
        "filters": ["only_due"],
    },
    "ledger": {
        "fn": report_ledger,
        "title": "Customer ledger",
        "group": "Sales & collections",
        "description": "Debit / credit statement with running balance for one customer.",
        "filters": ["dates", "customer!"],
    },
    "sales-register": {
        "fn": report_sales_register,
        "title": "Sales register (GST)",
        "group": "Sales & collections",
        "description": "Invoice-wise taxable value, CGST, SGST and IGST for GST returns.",
        "filters": ["dates"],
    },
    "quotations": {
        "fn": report_quotations,
        "title": "Quotation conversion",
        "group": "Sales & collections",
        "description": "Quotations created, won and lost per month, with conversion rate.",
        "filters": ["dates"],
    },
    "project-pl": {
        "fn": report_project_pl,
        "title": "Project profit / loss",
        "group": "Projects & costs",
        "description": "Contract, billed, received, cost and margin for every project.",
        "filters": ["project_status", "customer"],
    },
    "expenses": {
        "fn": report_expenses,
        "title": "Expenses",
        "group": "Projects & costs",
        "description": "Expenses by category, by project, or entry by entry.",
        "filters": ["dates", "project", "expense_category", "group:category|project|detail"],
    },
    "stock": {
        "fn": report_stock,
        "title": "Stock summary",
        "group": "Stock & purchases",
        "description": "Opening, in, out and closing quantity and value per material.",
        "filters": ["dates", "material_category", "low_only"],
    },
    "purchases": {
        "fn": report_purchases,
        "title": "Material purchases",
        "group": "Stock & purchases",
        "description": "What was bought, from whom and at what average rate.",
        "filters": ["dates", "supplier", "group:material|supplier|bill"],
    },
}


def run_report(key, params, user):
    spec = REPORTS.get(key)
    if not spec:
        raise BusinessRuleError("Unknown report.")
    params.setdefault("date_from", fy_start())
    params.setdefault("date_to", date.today())
    if "as_on" in spec["filters"]:  # single "as on" date: no range needed
        params["date_from"] = min(params["date_from"], params["date_to"])
    if params["date_from"] > params["date_to"]:
        raise BusinessRuleError("'From' date is after 'To' date.", field="date_from")
    result = spec["fn"](params, user)
    result["key"] = key
    result["date_from"] = params["date_from"]
    result["date_to"] = params["date_to"]
    result["financial_year"] = financial_year(params["date_to"])
    return result
