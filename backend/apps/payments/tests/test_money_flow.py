from decimal import Decimal as D

import pytest

from apps.accounts.models import Role
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.materials.models import Material, MaterialCategory
from apps.payments import ledger
from apps.payments.models import AdvancePayment, CustomerLedgerEntry, Payment

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):
    cat = MaterialCategory.objects.create(name="Cement")
    cement = Material.objects.create(
        category=cat,
        name="OPC",
        brand="Ramco",
        hsn_code="2523",
        unit="bag",
        purchase_price=350,
        selling_price=400,
        gst_rate=18,
        stock_quantity=100,
    )
    c = Customer.objects.create(name="Ravi", phone="9876500001", state_code="33", email="r@x.com")
    other = Customer.objects.create(name="Mani", phone="9876500002", state_code="33")
    return {"cement": cement, "c": c, "other": other}


def inv_payload(w, qty="10", **kw):  # 10 bags × 400 = 4000 + 18% = 4720
    data = {
        "customer": w["c"].id,
        "invoice_date": "2026-11-01",
        "items": [{"material": w["cement"].id, "quantity": qty, "rate": "400"}],
    }
    data.update(kw)
    return data


def bal(w):
    return ledger.balance(w["c"])


def test_advance_auto_adjusted_then_paid(auth_client, world):
    client, _ = auth_client(Role.ACCOUNTANT)
    adv = client.post(
        "/api/v1/advances/",
        {
            "customer": world["c"].id,
            "amount": "3000",
            "date": "2026-11-01",
            "mode": "UPI",
            "reference_number": "UTR1",
        },
        format="json",
    ).data
    assert adv["receipt_number"].startswith("AK/ADV/") and adv["balance"] == "3000.00"
    assert bal(world) == D("-3000.00")  # customer has money with us

    inv = client.post("/api/v1/invoices/", inv_payload(world, invoice_date="2026-11-04"), format="json")
    assert inv.status_code == 201, inv.data
    inv = inv.data
    assert inv["number"].startswith("AK/2026-27/") or inv["number"].startswith("AK/")
    assert inv["grand_total"] == "4720.00" and inv["advance_adjusted"] == "3000.00"
    assert inv["balance_due"] == "1720.00" and inv["status"] == "PARTIAL"
    assert AdvancePayment.objects.get(pk=adv["id"]).status == "ADJUSTED"
    assert bal(world) == D("1720.00")  # 4720 debit − 3000 credit

    over = client.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "1720.01",
            "date": "2026-11-05",
            "mode": "CASH",
        },
        format="json",
    )
    assert over.status_code == 400 and "more than the balance" in over.data["detail"]
    early = client.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "100",
            "date": "2026-11-03",
            "mode": "CASH",
        },
        format="json",
    )
    assert early.status_code == 400 and "before the invoice date" in early.data["detail"]
    p = client.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "1720",
            "date": "2026-11-05",
            "mode": "CASH",
        },
        format="json",
    )
    assert p.status_code == 201 and p.data["receipt_number"].startswith("AK/RCP/")
    inv2 = client.get(f"/api/v1/invoices/{inv['id']}/").data
    assert inv2["status"] == "PAID" and inv2["balance_due"] == "0.00" and len(inv2["payments"]) == 1
    assert bal(world) == D("0.00")
    st = client.get(f"/api/v1/customers/{world['c'].id}/ledger/").data
    assert [r["entry_type"] for r in st["rows"]] == ["ADVANCE", "INVOICE", "PAYMENT"]
    assert st["closing_balance"] == 0 and st["rows"][1]["balance"] == D("1720.00")


def test_advance_for_project_used_first_and_partial_advance(auth_client, world):
    from apps.projects.models import Project

    client, _ = auth_client(Role.ACCOUNTANT)
    proj = Project.objects.create(
        code="P1", name="Villa", customer=world["c"], site_address="x", contract_value=50000
    )
    general = client.post(
        "/api/v1/advances/",
        {"customer": world["c"].id, "amount": "1000", "date": "2026-11-01", "mode": "CASH"},
        format="json",
    ).data
    project_adv = client.post(
        "/api/v1/advances/",
        {
            "customer": world["c"].id,
            "project": proj.id,
            "amount": "2000",
            "date": "2026-11-02",
            "mode": "CASH",
        },
        format="json",
    ).data
    inv = client.post(
        "/api/v1/invoices/", inv_payload(world, project=proj.id, qty="5"), format="json"
    ).data  # 2360
    assert inv["advance_adjusted"] == "2360.00"
    a1, a2 = AdvancePayment.objects.get(pk=project_adv["id"]), AdvancePayment.objects.get(pk=general["id"])
    assert a1.adjusted_amount == D("2000") and a2.adjusted_amount == D("360") and a2.status == "PARTIAL"


def test_no_auto_adjust_and_manual_adjust_and_undo(auth_client, world):
    client, _ = auth_client(Role.ACCOUNTANT)
    adv = client.post(
        "/api/v1/advances/",
        {"customer": world["c"].id, "amount": "5000", "date": "2026-11-01", "mode": "CASH"},
        format="json",
    ).data
    inv = client.post("/api/v1/invoices/", inv_payload(world, auto_adjust_advance=False), format="json").data
    assert inv["advance_adjusted"] == "0.00"
    r = client.post(
        f"/api/v1/advances/{adv['id']}/adjust/", {"invoice": inv["id"], "amount": "5000"}, format="json"
    )
    assert r.status_code == 400  # more than invoice balance 4720
    r = client.post(
        f"/api/v1/advances/{adv['id']}/adjust/", {"invoice": inv["id"], "amount": "4720"}, format="json"
    )
    assert r.status_code == 200 and r.data["balance"] == "280.00"
    adj_id = r.data["adjustments"][0]["id"]
    assert client.delete(f"/api/v1/advance-adjustments/{adj_id}/").status_code == 403
    admin, _ = auth_client(Role.ADMIN)
    assert admin.delete(f"/api/v1/advance-adjustments/{adj_id}/").status_code == 204
    assert Invoice.objects.get(pk=inv["id"]).balance_due == D("4720.00")


def test_refund_limits_and_ledger(auth_client, world):
    client, _ = auth_client(Role.ACCOUNTANT)
    adv = client.post(
        "/api/v1/advances/",
        {"customer": world["c"].id, "amount": "2000", "date": "2026-11-01", "mode": "CASH"},
        format="json",
    ).data
    assert (
        client.post(
            f"/api/v1/advances/{adv['id']}/refund/",
            {"amount": "2500", "date": "2026-11-03", "mode": "CASH", "reason": "Work cancelled"},
            format="json",
        ).status_code
        == 400
    )
    r = client.post(
        f"/api/v1/advances/{adv['id']}/refund/",
        {"amount": "2000", "date": "2026-11-03", "mode": "BANK", "reason": "Work cancelled"},
        format="json",
    )
    assert (
        r.status_code == 200
        and r.data["status"] == "REFUNDED"
        and r.data["refunds"][0]["refund_number"].startswith("AK/REF/")
    )
    assert bal(world) == D("0.00")
    assert (
        client.get(f"/api/v1/advances/{adv['id']}/refunds/{r.data['refunds'][0]['id']}/pdf/").status_code
        == 200
    )


def test_payment_needs_target_and_matching_customer(auth_client, world):
    client, _ = auth_client(Role.ACCOUNTANT)
    r = client.post(
        "/api/v1/payments/",
        {"customer": world["c"].id, "amount": "100", "date": "2026-11-01", "mode": "CASH"},
        format="json",
    )
    assert r.status_code == 400 and "Advance" in r.data["detail"]
    inv = client.post("/api/v1/invoices/", inv_payload(world), format="json").data
    r = client.post(
        "/api/v1/payments/",
        {
            "customer": world["other"].id,
            "invoice": inv["id"],
            "amount": "100",
            "date": "2026-11-01",
            "mode": "CASH",
        },
        format="json",
    )
    assert r.status_code == 400 and "another customer" in r.data["detail"]
    r = client.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "100",
            "date": "2026-11-01",
            "mode": "CHEQUE",
        },
        format="json",
    )
    assert r.status_code == 400 and "cheque_number" in r.data["errors"]


def test_cheque_bounce_reopens_invoice(auth_client, world):
    client, _ = auth_client(Role.ACCOUNTANT)
    inv = client.post("/api/v1/invoices/", inv_payload(world), format="json").data
    p = client.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "4720",
            "date": "2026-11-02",
            "mode": "CHEQUE",
            "cheque_number": "004512",
            "bank_name": "SBI",
        },
        format="json",
    ).data
    assert p["cheque_status"] == "PENDING"
    assert Invoice.objects.get(pk=inv["id"]).status == "PAID"
    r = client.post(f"/api/v1/payments/{p['id']}/cheque/", {"status": "BOUNCED"}, format="json")
    assert r.status_code == 200 and r.data["cheque_status"] == "BOUNCED"
    i = Invoice.objects.get(pk=inv["id"])
    assert i.status == "UNPAID" and i.balance_due == D("4720.00")
    assert bal(world) == D("4720.00")
    assert CustomerLedgerEntry.objects.filter(entry_type="BOUNCE").count() == 1
    assert (
        client.post(f"/api/v1/payments/{p['id']}/cheque/", {"status": "CLEARED"}, format="json").status_code
        == 400
    )


def test_cancel_payment_and_invoice(auth_client, world):
    acc, _ = auth_client(Role.ACCOUNTANT)
    admin, _ = auth_client(Role.ADMIN)
    adv = acc.post(
        "/api/v1/advances/",
        {"customer": world["c"].id, "amount": "1000", "date": "2026-11-01", "mode": "CASH"},
        format="json",
    ).data
    inv = acc.post("/api/v1/invoices/", inv_payload(world), format="json").data
    p = acc.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "500",
            "date": "2026-11-02",
            "mode": "UPI",
        },
        format="json",
    ).data
    assert (
        acc.post(f"/api/v1/invoices/{inv['id']}/cancel/", {"reason": "x"}, format="json").status_code == 403
    )
    r = admin.post(f"/api/v1/invoices/{inv['id']}/cancel/", {"reason": "Wrong rate"}, format="json")
    assert r.status_code == 400 and "Payments are recorded" in r.data["detail"]
    assert acc.post(f"/api/v1/payments/{p['id']}/cancel/", {"reason": "x"}, format="json").status_code == 403
    assert (
        admin.post(
            f"/api/v1/payments/{p['id']}/cancel/", {"reason": "Entered twice"}, format="json"
        ).status_code
        == 200
    )
    assert not Payment.objects.filter(pk=p["id"]).exists()
    r = admin.post(f"/api/v1/invoices/{inv['id']}/cancel/", {"reason": "Wrong rate"}, format="json")
    assert r.status_code == 200 and r.data["status"] == "CANCELLED" and r.data["advance_adjusted"] == "0.00"
    assert AdvancePayment.objects.get(pk=adv["id"]).balance == D("1000.00")  # advance released
    assert bal(world) == D("-1000.00")  # only the advance remains
    assert CustomerLedgerEntry.objects.filter(entry_type="REVERSAL").count() == 2
    pdf = acc.get(f"/api/v1/invoices/{inv['id']}/pdf/")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_invoice_edit_only_when_unpaid(auth_client, world):
    client, _ = auth_client(Role.ACCOUNTANT)
    inv = client.post("/api/v1/invoices/", inv_payload(world), format="json").data
    r = client.patch(
        f"/api/v1/invoices/{inv['id']}/",
        {"items": [{"material": world["cement"].id, "quantity": "5", "rate": "400"}]},
        format="json",
    )
    assert r.status_code == 200 and r.data["grand_total"] == "2360.00"
    assert bal(world) == D("2360.00")  # ledger follows the edit
    client.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "100",
            "date": "2026-11-02",
            "mode": "UPI",
        },
        format="json",
    )
    assert client.patch(f"/api/v1/invoices/{inv['id']}/", {"notes": "x"}, format="json").status_code == 400


def test_direct_sale_deducts_and_cancel_restores_stock(auth_client, world):
    acc, _ = auth_client(Role.ACCOUNTANT)
    admin, _ = auth_client(Role.ADMIN)
    inv = acc.post("/api/v1/invoices/", inv_payload(world, deduct_stock=True), format="json").data
    world["cement"].refresh_from_db()
    assert world["cement"].stock_quantity == D("90")
    admin.post(f"/api/v1/invoices/{inv['id']}/cancel/", {"reason": "Returned"}, format="json")
    world["cement"].refresh_from_db()
    assert world["cement"].stock_quantity == D("100")


def test_receipts_pdfs_and_overdue(auth_client, world):
    from datetime import date, timedelta

    client, _ = auth_client(Role.ACCOUNTANT)
    adv = client.post(
        "/api/v1/advances/",
        {"customer": world["c"].id, "amount": "100", "date": "2026-11-01", "mode": "CASH"},
        format="json",
    ).data
    assert client.get(f"/api/v1/advances/{adv['id']}/pdf/").content[:4] == b"%PDF"
    inv = client.post("/api/v1/invoices/", inv_payload(world, auto_adjust_advance=False), format="json").data
    p = client.post(
        "/api/v1/payments/",
        {
            "customer": world["c"].id,
            "invoice": inv["id"],
            "amount": "720",
            "date": "2026-11-02",
            "mode": "UPI",
        },
        format="json",
    ).data
    assert client.get(f"/api/v1/payments/{p['id']}/pdf/").content[:4] == b"%PDF"
    Invoice.objects.filter(pk=inv["id"]).update(due_date=date.today() - timedelta(days=40))
    od = client.get("/api/v1/invoices/overdue/").data
    assert od["count"] == 1 and od["results"][0]["bucket"] == "31–60 days" and od["total"] == "4000.00"
    msg = client.get(f"/api/v1/invoices/{inv['id']}/share-text/", {"reminder": "1"}).data["message"]
    assert "₹4,000.00" in msg and "overdue by 40 days" in msg
    assert client.post(f"/api/v1/invoices/{inv['id']}/log-reminder/").status_code == 200
    items = client.get(f"/api/v1/customers/{world['c'].id}/open-items/").data
    assert len(items["invoices"]) == 1 and len(items["advances"]) == 1


def test_money_apis_hidden_from_sales_and_engineers(auth_client):
    for role in (Role.SALES, Role.SITE_ENGINEER):
        client, _ = auth_client(role)
        for url in ("/api/v1/invoices/", "/api/v1/payments/", "/api/v1/advances/"):
            assert client.get(url).status_code == 403
