from decimal import Decimal as D

import pytest

from apps.accounts.models import Role
from apps.core.models import CompanySettings
from apps.materials.models import Material, MaterialCategory, PriceHistory, StockMovement
from apps.suppliers.models import Supplier

pytestmark = pytest.mark.django_db
P = "/api/v1/purchases/"


@pytest.fixture
def setup(db):
    CompanySettings.load()  # state 33
    cat = MaterialCategory.objects.create(name="Steel")
    tmt = Material.objects.create(
        category=cat,
        name="TMT 12mm",
        brand="JSW",
        hsn_code="7214",
        unit="kg",
        purchase_price=60,
        selling_price=68,
        gst_rate=18,
    )
    cement = Material.objects.create(
        category=cat,
        name="OPC",
        brand="Ramco",
        hsn_code="2523",
        unit="bag",
        purchase_price=350,
        selling_price=400,
        gst_rate=18,
    )
    local = Supplier.objects.create(name="Sri Murugan Traders", phone="9443000000", state_code="33")
    kerala = Supplier.objects.create(name="Kerala Steels", phone="9447000000", state_code="32")
    return {"tmt": tmt, "cement": cement, "local": local, "kerala": kerala}


def purchase_payload(s, supplier="local", **kw):
    data = {
        "supplier": s[supplier].id,
        "purchase_date": "2026-11-11",
        "supplier_invoice_number": "SMT/551",
        "transport_charges": "500",
        "items": [
            {"material": s["tmt"].id, "quantity": "1000", "rate": "61", "discount_percent": "1"},
            {"material": s["cement"].id, "quantity": "100", "rate": "355"},
            {
                "item_type": "SERVICE",
                "description": "Unloading",
                "quantity": "1",
                "rate": "800",
                "gst_rate": "18",
            },
        ],
    }
    data.update(kw)
    return data


def test_create_purchase_intra_state_totals(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    r = client.post(P, purchase_payload(setup), format="json")
    assert r.status_code == 201, r.data
    d = r.data
    assert d["po_number"].startswith("AK/PO/2026-27/") and d["status"] == "ORDERED"
    # 61000 − 610 = 60390 ; 35500 ; 800 → taxable 96690 ; GST 18% = 17404.20 split
    assert d["taxable_amount"] == "96690.00" and d["cgst_amount"] == "8702.10" and d["igst_amount"] == "0.00"
    assert d["grand_total"] == "114594.00"  # 96690 + 17404.20 + 500 = 114594.20 → round
    assert d["round_off"] == "-0.20" and d["balance_due"] == "114594.00"
    assert d["items"][0]["description"] == "TMT 12mm JSW" and d["items"][0]["unit"] == "kg"
    assert StockMovement.objects.count() == 0  # not received yet


def test_inter_state_supplier_uses_igst(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    d = client.post(P, purchase_payload(setup, supplier="kerala"), format="json").data
    assert d["is_interstate"] and d["igst_amount"] == "17404.20" and d["cgst_amount"] == "0.00"


def test_partial_then_full_receipt_updates_stock_and_cost(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    d = client.post(P, purchase_payload(setup), format="json").data
    tmt_item, cement_item = d["items"][0], d["items"][1]
    r = client.post(
        f"{P}{d['id']}/receive/", {"lines": [{"item": tmt_item["id"], "quantity": "600"}]}, format="json"
    )
    assert r.status_code == 200 and r.data["status"] == "PARTIAL"
    setup["tmt"].refresh_from_db()
    assert setup["tmt"].stock_quantity == D("600")
    assert setup["tmt"].purchase_price == D("60.39")  # net unit cost after 1% discount
    assert PriceHistory.objects.filter(material=setup["tmt"], reason__contains=d["po_number"]).exists()

    over = client.post(
        f"{P}{d['id']}/receive/", {"lines": [{"item": tmt_item["id"], "quantity": "401"}]}, format="json"
    )
    assert over.status_code == 400 and "at most 400" in over.data["detail"]

    assert (
        client.patch(f"{P}{d['id']}/", {"notes": "x"}, format="json").status_code == 400
    )  # locked after receipt
    r = client.post(
        f"{P}{d['id']}/receive/",
        {
            "lines": [
                {"item": tmt_item["id"], "quantity": "400"},
                {"item": cement_item["id"], "quantity": "100"},
            ]
        },
        format="json",
    )
    assert r.data["status"] == "RECEIVED"
    setup["cement"].refresh_from_db()
    assert setup["cement"].stock_quantity == D("100")
    mv = StockMovement.objects.filter(material=setup["cement"]).get()
    assert mv.movement_type == "PURCHASE_IN" and mv.reference_id == d["id"]


def test_receive_now_on_create(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    d = client.post(P, purchase_payload(setup, receive_now=True), format="json").data
    assert d["status"] == "RECEIVED"
    setup["tmt"].refresh_from_db()
    assert setup["tmt"].stock_quantity == D("1000")


def test_edit_before_receipt_recalculates(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    d = client.post(P, purchase_payload(setup), format="json").data
    r = client.patch(
        f"{P}{d['id']}/",
        {
            "transport_charges": "0",
            "items": [{"material": setup["cement"].id, "quantity": "10", "rate": "350"}],
        },
        format="json",
    )
    assert r.status_code == 200 and r.data["grand_total"] == "4130.00" and len(r.data["items"]) == 1


def test_duplicate_supplier_bill_rejected(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    client.post(P, purchase_payload(setup), format="json")
    r = client.post(P, purchase_payload(setup), format="json")
    assert r.status_code == 400 and "already entered" in r.data["detail"]


def test_payments_and_balances(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    d = client.post(
        P,
        purchase_payload(
            setup,
            transport_charges="0",
            items=[{"material": setup["cement"].id, "quantity": "10", "rate": "350"}],
        ),
        format="json",
    ).data  # 4130
    pay = "/api/v1/supplier-payments/"
    too_much = client.post(
        pay,
        {
            "supplier": setup["local"].id,
            "purchase": d["id"],
            "amount": "5000",
            "date": "2026-11-12",
            "mode": "UPI",
        },
        format="json",
    )
    assert too_much.status_code == 400
    r = client.post(
        pay,
        {
            "supplier": setup["local"].id,
            "purchase": d["id"],
            "amount": "3000",
            "date": "2026-11-12",
            "mode": "UPI",
            "reference_number": "UTR123",
        },
        format="json",
    )
    assert r.status_code == 201 and r.data["voucher_number"].startswith("AK/SP/")
    p = client.get(f"{P}{d['id']}/").data
    assert p["payment_status"] == "PARTIAL" and p["balance_due"] == "1130.00" and len(p["payments"]) == 1
    sup = client.get(f"/api/v1/suppliers/{setup['local'].id}/").data
    assert sup["total_purchases"] == "4130.00" and sup["payable"] == "1130.00"

    wrong = client.post(
        pay,
        {
            "supplier": setup["kerala"].id,
            "purchase": d["id"],
            "amount": "10",
            "date": "2026-11-12",
            "mode": "CASH",
        },
        format="json",
    )
    assert wrong.status_code == 400

    # cancelling a payment (management only) restores the balance
    assert client.delete(f"{pay}{r.data['id']}/").status_code == 403
    admin, _ = auth_client(Role.ADMIN)
    assert admin.delete(f"{pay}{r.data['id']}/").status_code == 204
    assert client.get(f"{P}{d['id']}/").data["balance_due"] == "4130.00"


def test_cancel_rules(auth_client, setup):
    acc, _ = auth_client(Role.ACCOUNTANT)
    admin, _ = auth_client(Role.ADMIN)
    d = acc.post(P, purchase_payload(setup), format="json").data
    assert acc.post(f"{P}{d['id']}/cancel/").status_code == 403
    r = admin.post(f"{P}{d['id']}/cancel/", {"reason": "Wrong supplier"}, format="json")
    assert r.status_code == 200 and r.data["status"] == "CANCELLED" and r.data["balance_due"] == "0.00"
    received = acc.post(
        P, purchase_payload(setup, supplier_invoice_number="B2", receive_now=True), format="json"
    ).data
    assert admin.post(f"{P}{received['id']}/cancel/").status_code == 400
    assert (
        acc.get("/api/v1/suppliers/", {"ordering": "-payable"}).data["results"][0]["payable"]
        == received["grand_total"]
    )


def test_purchases_hidden_from_sales(auth_client, setup):
    client, _ = auth_client(Role.SALES)
    assert client.get(P).status_code == 403
    assert client.get("/api/v1/suppliers/").status_code == 403


def test_null_relations_render_as_null_not_python_repr(auth_client, setup):
    client, _ = auth_client(Role.ACCOUNTANT)
    d = client.post(P, purchase_payload(setup, receive_now=True), format="json").data
    assert d["project_name"] is None
    service_line = [i for i in d["items"] if i["item_type"] == "SERVICE"][0]
    assert service_line["material_name"] is None
    moves = client.get("/api/v1/stock-movements/").data["results"]
    assert all(m["project_name"] is None for m in moves)
