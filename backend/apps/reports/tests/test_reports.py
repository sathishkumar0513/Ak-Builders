from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Role
from apps.customers.models import Customer
from apps.materials.models import MaterialCategory
from apps.materials.services import create_material
from apps.reports.services import REPORTS

pytestmark = pytest.mark.django_db
TODAY = date.today().isoformat()


@pytest.fixture
def money(auth_client):
    """One invoice (₹4,720) partly paid by an advance (₹1,000) and a UPI payment (₹2,000)."""
    client, _ = auth_client(Role.ACCOUNTANT)
    cat = MaterialCategory.objects.create(name="Cement")
    m = create_material(
        data={
            "category": cat,
            "name": "OPC",
            "unit": "bag",
            "purchase_price": 350,
            "selling_price": 400,
            "gst_rate": 18,
            "reorder_level": 150,
        },
        opening_stock=D("100"),
    )
    c = Customer.objects.create(name="Ravi", phone="9876500001", state_code="33")
    client.post(
        "/api/v1/advances/",
        {"customer": c.id, "amount": "1000", "date": TODAY, "mode": "CASH"},
        format="json",
    )
    inv = client.post(
        "/api/v1/invoices/",
        {
            "customer": c.id,
            "invoice_date": TODAY,
            "items": [{"material": m.id, "quantity": "10", "rate": "400"}],
            "deduct_stock": True,
        },
        format="json",
    ).data
    client.post(
        "/api/v1/payments/",
        {
            "customer": c.id,
            "invoice": inv["id"],
            "amount": "2000",
            "date": TODAY,
            "mode": "UPI",
            "reference_number": "U1",
        },
        format="json",
    )
    return {"client": client, "c": c, "inv": inv, "m": m}


def test_dashboard_money_cards(money):
    d = money["client"].get("/api/v1/dashboard/").data
    assert D(d["cards"]["received_fy"]) == D("3000")
    assert D(d["cards"]["outstanding"]) == D("1720")
    assert d["cards"]["low_stock"] == 1
    assert {m["mode"] for m in d["payment_modes"]} == {"CASH", "UPI"}
    assert D(d["monthly"][-1]["billed"]) == D("4720")
    assert len(d["monthly"]) == 12


def test_dashboard_hides_money_from_site_and_sales(auth_client, money):
    for role in (Role.SITE_ENGINEER, Role.SALES):
        client, _ = auth_client(role)
        d = client.get("/api/v1/dashboard/").data
        assert "received_fy" not in d["cards"] and "monthly" not in d and "overdue_invoices" not in d
    sales, _ = auth_client(Role.SALES, username="s2")
    assert "pending_quotations" in sales.get("/api/v1/dashboard/").data["cards"]


@pytest.mark.parametrize("key", [k for k in REPORTS if k != "ledger"])
def test_every_report_runs_and_exports(money, key):
    client = money["client"]
    r = client.get(f"/api/v1/reports/{key}/")
    assert r.status_code == 200, r.data
    assert r.data["columns"] and "rows" in r.data
    for ex, magic in (("xlsx", b"PK"), ("pdf", b"%PDF")):
        f = client.get(f"/api/v1/reports/{key}/?export={ex}")
        assert f.status_code == 200 and f.content.startswith(magic)
        assert "attachment" in f["Content-Disposition"]


def test_report_figures(money):
    client = money["client"]
    pay = client.get("/api/v1/reports/payments/").data
    assert D(pay["totals"]["amount"]) == D("3000") and len(pay["rows"]) == 2
    out = client.get("/api/v1/reports/outstanding/").data
    assert D(out["totals"]["balance_due"]) == D("1720")
    led = client.get(f"/api/v1/reports/ledger/?customer={money['c'].id}").data
    assert D(led["totals"]["balance"]) == D("1720")
    reg = client.get("/api/v1/reports/sales-register/").data
    assert D(reg["totals"]["taxable"]) == D("4000") and D(reg["totals"]["cgst"]) == D("360")
    stock = client.get("/api/v1/reports/stock/?low_only=1").data
    assert len(stock["rows"]) == 1 and D(stock["rows"][0]["closing"]) == D("90")  # invoice deducted 10 bags


def test_report_validation_and_permissions(money, auth_client):
    client = money["client"]
    assert client.get("/api/v1/reports/ledger/").status_code == 400
    assert client.get("/api/v1/reports/payments/?date_from=2026-12-01&date_to=2026-01-01").status_code == 400
    assert client.get("/api/v1/reports/payments/?date_from=nonsense").status_code == 400
    assert client.get("/api/v1/reports/nope/").status_code == 400
    for role in (Role.SITE_ENGINEER, Role.SALES):
        other, _ = auth_client(role)
        assert other.get("/api/v1/reports/payments/").status_code == 403
        assert other.get("/api/v1/reports/").status_code == 403
